import json
import threading
from pathlib import Path
from datetime import datetime

_write_lock = threading.Lock()


class JSONLogger:
    """
    Thread-safe structured JSONL logger.
    Each log entry is a single JSON object written on its own line.
    Supports optional request_id for tracing a full processing run.
    """

    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, record: dict):
        record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        with _write_lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ── Public logging methods ─────────────────────────────────────────────

    def log_extractor_event(self, pdf_path, page_number, extractor, success,
                            failed_extractors, request_id=None):
        self._write({
            "event":             "extractor_event",
            "request_id":        request_id,
            "pdf":               str(pdf_path),
            "page":              page_number,
            "extractor":         extractor,
            "success":           success,
            "failed_extractors": failed_extractors,
        })

    def log_extractor_failure(self, pdf_path, page_number, failed_extractors,
                              request_id=None):
        self._write({
            "event":             "extractor_failure",
            "request_id":        request_id,
            "pdf":               str(pdf_path),
            "page":              page_number,
            "failed_extractors": failed_extractors,
        })

    def log_vendor_detection(self, pdf_path, vendor, page_number, request_id=None):
        self._write({
            "event":      "vendor_detected",
            "request_id": request_id,
            "pdf":        str(pdf_path),
            "vendor":     vendor,
            "page":       page_number,
        })

    def log_statement_result(self, pdf_path, filename, vendor, date, index,
                             confidence, used_fallback, request_id=None):
        self._write({
            "event":           "statement_processed",
            "request_id":      request_id,
            "pdf":             str(pdf_path),
            "output_filename": filename,
            "vendor":          vendor,
            "date":            date,
            "index":           index,
            "confidence":      confidence,
            "used_fallback":   used_fallback,
        })

    def log_request(self, request_id, prefix, filename, file_size_mb, page_count):
        """Log the start of a processing request."""
        self._write({
            "event":         "request_start",
            "request_id":    request_id,
            "prefix":        prefix,
            "filename":      filename,
            "file_size_mb":  round(file_size_mb, 2),
            "page_count":    page_count,
        })

    def log_request_complete(self, request_id, statement_count, elapsed_sec):
        """Log the completion of a processing request."""
        self._write({
            "event":           "request_complete",
            "request_id":      request_id,
            "statement_count": statement_count,
            "elapsed_sec":     round(elapsed_sec, 2),
        })

    def log_error(self, file, message, request_id=None):
        self._write({
            "event":      "error",
            "request_id": request_id,
            "file":       file,
            "message":    message,
        })

    def log_pdf_detected(self, file, event_type, request_id=None):
        self._write({
            "event":      "pdf_detected",
            "request_id": request_id,
            "file":       file,
            "type":       event_type,
        })

    def log_pdf_saved(self, file, request_id=None):
        self._write({
            "event":      "pdf_saved",
            "request_id": request_id,
            "file":       file,
        })
