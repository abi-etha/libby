import json
import threading
from pathlib import Path
from datetime import datetime

_write_lock = threading.Lock()


class JSONLogger:
    """
    Thread-safe structured JSONL logger.
    Each log entry is a single JSON object written on its own line.
    """

    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, record: dict):
        """Internal: write a single JSON record to file."""
        record["timestamp"] = datetime.utcnow().isoformat() + "Z"

        with _write_lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ---------------------------------------------------------
    # PUBLIC LOGGING METHODS
    # ---------------------------------------------------------

    def log_extractor_event(self, pdf_path, page_number, extractor, success, failed_extractors):
        self._write({
            "event": "extractor_event",
            "pdf": str(pdf_path),
            "page": page_number,
            "extractor": extractor,
            "success": success,
            "failed_extractors": failed_extractors,
        })

    def log_extractor_failure(self, pdf_path, page_number, failed_extractors):
        self._write({
            "event": "extractor_failure",
            "pdf": str(pdf_path),
            "page": page_number,
            "failed_extractors": failed_extractors,
        })

    def log_vendor_detection(self, pdf_path, vendor, page_number):
        self._write({
            "event": "vendor_detected",
            "pdf": str(pdf_path),
            "vendor": vendor,
            "page": page_number,
        })

    def log_statement_result(self, pdf_path, filename, vendor, date, index, confidence, used_fallback):
        self._write({
            "event": "statement_processed",
            "pdf": str(pdf_path),
            "output_filename": filename,
            "vendor": vendor,
            "date": date,
            "index": index,
            "confidence": confidence,
            "used_fallback": used_fallback,
        })

    def log_error(self, file, message):
        self._write({
            "event": "error",
            "file": file,
            "message": message,
        })

    def log_pdf_detected(self, file, event_type):
        self._write({
            "event": "pdf_detected",
            "file": file,
            "type": event_type,
        })

    def log_pdf_saved(self, file):
        self._write({
            "event": "pdf_saved",
            "file": file,
        })
