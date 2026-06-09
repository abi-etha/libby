"""
Libby Statement Engine — Flask API
Railway-ready production server.
"""

import sys
import os
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

app = Flask(__name__)

ALLOWED_ORIGINS = [
    "https://solfound.netlify.app",
    "http://localhost:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://127.0.0.1:5000",
]
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})


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


@app.route("/")
def index():
    return jsonify({"status": "ok", "message": "Libby Statement Engine — API only. Frontend lives at solfound.netlify.app"})


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "engine": "statement_engine",
        "version": "2.0",
        "mode": "production" if API_KEY else "dev",
    })


@app.route("/process", methods=["POST"])
@require_api_key
def process():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file   = request.files["file"]
    prefix = request.form.get("prefix", "CLIENT").strip().upper()

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a PDF file"}), 400

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        results = process_pdf(tmp_path, prefix)
        output_files = []
        base_url = request.host_url.rstrip("/")

        for result in results:
            filename     = result["filename"]
            csv_filename = result["csv_filename"]
            csv_content  = result["csv_content"]
            pages        = result["pages"]
            output_path  = OUTPUT_FOLDER / filename
            csv_path     = OUTPUT_FOLDER / csv_filename

            import fitz
            if pages:
                source_path = pages[0].source_path
                src_doc = fitz.open(source_path)
                writer  = fitz.open()
                for pr in pages:
                    try:
                        writer.insert_pdf(src_doc, from_page=pr.page_number, to_page=pr.page_number)
                    except Exception as e:
                        print(f"WARNING: Could not include page {pr.page_number}: {e}")
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
                "date":          result["date"],
                "confidence":    result["confidence"],
                "used_fallback": result["used_fallback"],
                "pages":         len(pages),
                "transactions":  result["transactions"],
            })

        return jsonify({"status": "ok", "count": len(output_files), "results": output_files})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.route("/download/<filename>")
@require_api_key
def download(filename):
    safe     = Path(filename).name
    filepath = OUTPUT_FOLDER / safe
    if not filepath.exists():
        return jsonify({"error": "File not found — re-process your PDF."}), 404
    return send_file(str(filepath), as_attachment=True, download_name=safe)


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
    return send_file(str(zip_path), as_attachment=True, download_name="libby_statements.zip")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    print(f"\n{'='*55}")
    print(f"  Libby — {'DEV' if debug else 'PRODUCTION'} on port {port}")
    print(f"  API Key: {'SET' if API_KEY else 'NOT SET (open access)'}")
    print(f"{'='*55}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
