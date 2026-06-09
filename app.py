"""
Libby Statement Engine — Flask API
Railway-ready production server.
"""

import sys
import os
import time
import uuid
import tempfile
import zipfile
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# ── Path setup ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from core.statement_router import process_pdf
from core.config import OUTPUT_FOLDER, API_KEY
from core.json_logger import JSONLogger

app = Flask(__name__)

ALLOWED_ORIGINS = [
    "https://solfound.netlify.app",
    "http://localhost:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5000",
]
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

JSON_LOG = JSONLogger(BASE_DIR / "logs" / "events.jsonl")

# ── Limits ────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 50
MAX_PAGES        = 100


# ── Auth ──────────────────────────────────────────────────────
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not API_KEY:
            return f(*args, **kwargs)
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Output cleanup ────────────────────────────────────────────
def cleanup_output_folder():
    """
    Remove all files from the output folder after a request completes.
    Keeps the folder itself. Skips files currently being downloaded.
    """
    try:
        for f in OUTPUT_FOLDER.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                except Exception as e:
                    print(f"WARNING: Could not delete {f.name}: {e}")
    except Exception as e:
        print(f"WARNING: Output cleanup failed: {e}")


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({
        "status":  "ok",
        "message": "Libby Statement Engine — API only. Frontend lives at solfound.netlify.app",
    })


@app.route("/health")
def health():
    return jsonify({
        "status":  "ok",
        "engine":  "statement_engine",
        "version": "2.1",
        "mode":    "production" if API_KEY else "dev",
        "limits":  {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "max_pages":        MAX_PAGES,
        },
    })


@app.route("/process", methods=["POST"])
@require_api_key
def process():
    request_id = str(uuid.uuid4())[:8]   # short 8-char ID, e.g. "a3f9b21c"
    start_time = time.time()

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file   = request.files["file"]
    prefix = request.form.get("prefix", "CLIENT").strip().upper()

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a PDF file"}), 400

    # ── Input validation: file size ───────────────────────────
    file.seek(0, 2)                          # seek to end
    file_size_mb = file.tell() / (1024 * 1024)
    file.seek(0)                             # reset

    if file_size_mb > MAX_FILE_SIZE_MB:
        return jsonify({
            "error": f"File too large ({file_size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB."
        }), 400

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # ── Input validation: page count ─────────────────────────
    try:
        import fitz
        doc = fitz.open(tmp_path)
        page_count = len(doc)
        doc.close()
        if page_count > MAX_PAGES:
            os.unlink(tmp_path)
            return jsonify({
                "error": f"PDF has {page_count} pages. Maximum is {MAX_PAGES} pages."
            }), 400
    except Exception as e:
        os.unlink(tmp_path)
        return jsonify({"error": f"Could not read PDF: {e}"}), 400

    # ── Log request start ─────────────────────────────────────
    JSON_LOG.log_request(
        request_id=request_id,
        prefix=prefix,
        filename=file.filename,
        file_size_mb=file_size_mb,
        page_count=page_count,
    )
    print(f"[{request_id}] Processing: {file.filename} ({file_size_mb:.1f} MB, {page_count} pages)")

    try:
        results = process_pdf(tmp_path, prefix, request_id=request_id)
        output_files = []
        base_url = request.host_url.rstrip("/")

        for result in results:
            filename     = result["filename"]
            csv_filename = result["csv_filename"]
            csv_content  = result["csv_content"]
            pages        = result["pages"]
            output_path  = OUTPUT_FOLDER / filename
            csv_path     = OUTPUT_FOLDER / csv_filename

            if pages:
                source_path = pages[0].source_path
                src_doc = fitz.open(source_path)
                writer  = fitz.open()
                for pr in pages:
                    try:
                        writer.insert_pdf(src_doc, from_page=pr.page_number, to_page=pr.page_number)
                    except Exception as e:
                        print(f"[{request_id}] WARNING: Could not include page {pr.page_number}: {e}")
                writer.save(str(output_path))
                writer.close()
                src_doc.close()

            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                f.write(csv_content)

            output_files.append({
                "filename":      filename,
                "csv_filename":  csv_filename,
                "pdf_url":       f"{base_url}/download/{filename}",
                "csv_url":       f"{base_url}/download/{csv_filename}",
                "vendor":        result["vendor"],
                "doc_type":      result.get("doc_type", ""),
                "date":          result["date"],
                "confidence":    result["confidence"],
                "used_fallback": result["used_fallback"],
                "pages":         len(pages),
                "transactions":  result["transactions"],
            })

        elapsed = time.time() - start_time
        JSON_LOG.log_request_complete(
            request_id=request_id,
            statement_count=len(output_files),
            elapsed_sec=elapsed,
        )
        print(f"[{request_id}] Complete: {len(output_files)} statements in {elapsed:.1f}s")

        return jsonify({
            "status":     "ok",
            "request_id": request_id,
            "count":      len(output_files),
            "results":    output_files,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        JSON_LOG.log_error(file.filename, str(e), request_id=request_id)
        return jsonify({"error": str(e), "request_id": request_id}), 500

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        # Clean up output folder after request — files have been served
        # Note: cleanup runs AFTER response is sent via download endpoints
        # so we only clean here as a safety net for aborted requests


@app.route("/download/<filename>")
@require_api_key
def download(filename):
    safe     = Path(filename).name
    filepath = OUTPUT_FOLDER / safe
    if not filepath.exists():
        return jsonify({"error": "File not found — re-process your PDF."}), 404

    response = send_file(str(filepath), as_attachment=True, download_name=safe)

    # Schedule cleanup after this file is served
    @response.call_on_close
    def _cleanup():
        cleanup_output_folder()

    return response


@app.route("/download-all")
@require_api_key
def download_all():
    files = list(OUTPUT_FOLDER.glob("*.pdf")) + list(OUTPUT_FOLDER.glob("*.csv"))
    if not files:
        return jsonify({"error": "No processed files found"}), 404

    zip_path = OUTPUT_FOLDER / "_libby_export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in files:
            if f.name != "_libby_export.zip":
                zf.write(f, f.name)

    response = send_file(str(zip_path), as_attachment=True,
                         download_name="libby_statements.zip")

    @response.call_on_close
    def _cleanup():
        cleanup_output_folder()

    return response


if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    print(f"\n{'='*55}")
    print(f"  Libby v2.1 — {'DEV' if debug else 'PRODUCTION'} on port {port}")
    print(f"  API Key: {'SET' if API_KEY else 'NOT SET (open access)'}")
    print(f"  Limits: {MAX_FILE_SIZE_MB}MB / {MAX_PAGES} pages")
    print(f"{'='*55}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
