# core/transaction_extractor.py
#
# Extracts transactions from bank and credit card statement pages.
# Handles multiple real-world statement formats.

import re
import csv
import io
from typing import List, Dict, Optional
from core.image_extractor import PageResult


# ── Amount patterns ────────────────────────────────────────────────────────

# Matches: $1,234.56  or  -$1,234.56  or  1,234.56  or  (1,234.56)
AMOUNT_PATTERN = re.compile(r"\(?\$?([\d,]+\.\d{2})\)?")

# Amount at end of line
AMOUNT_EOL = re.compile(r"-?\$?([\d,]+\.\d{2})\s*$")

# Full line with: DATE DESCRIPTION AMOUNT [BALANCE]
# e.g. "01/15/2025   HEB Grocery #0482   57.65   4,742.35"
TABLE_ROW = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})\s*(?:([\d,]+\.\d{2}))?\s*$"
)

# Date at start of line
TXN_DATE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4})\*?")

# Lines to always skip
SKIP_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"^payments?\s+amount",
        r"^new charges?\s+amount",
        r"^fees?\s+amount",
        r"^total\s+",
        r"^summary",
        r"^detail",
        r"^\*indicates",
        r"^card ending",
        r"^continued on",
        r"^closing date",
        r"^payment due",
        r"^previous balance",
        r"^opening balance",
        r"^payments?/credits?",
        r"^new balance",
        r"^days in billing",
        r"^interest charge",
        r"^your annual",
        r"^cash advances",
        r"^\(v\) variable",
        r"^transactions? dated",
        r"^from\s+to\s+",
        r"^total fees",
        r"^total interest",
        r"^membership rewards",
        r"^foreign\s+spend",
        r"^date\s+description",  # table header
        r"^date\s+transaction",  # table header
        r"^\s*$",
    ]
]


def normalize_date(raw: str) -> str:
    """Convert MM/DD/YY or MM/DD/YYYY to YYYY-MM-DD."""
    parts = raw.replace("*", "").strip().split("/")
    if len(parts) != 3:
        return raw
    month, day, year = parts
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def clean_merchant(raw: str) -> str:
    """Clean up merchant name."""
    # Remove running balance suffix like "| $4,742.35"
    raw = re.sub(r"\s*\|\s*\$?[\d,]+\.\d{2}\s*$", "", raw)
    # Remove trailing phone numbers
    raw = re.sub(r"\s+\d{3}-\d{3}-\d{4}\s*$", "", raw)
    # Remove long numeric codes at end
    raw = re.sub(r"\s+\d{9,}\s*$", "", raw)
    # Collapse multiple spaces
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def should_skip(line: str) -> bool:
    stripped = line.strip()
    for pattern in SKIP_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def extract_transactions_from_text(text: str, vendor: str, statement_date: str) -> List[Dict]:
    """
    Parse raw text from a statement page into transaction rows.
    Tries table format first, falls back to line-by-line parsing.
    """
    transactions = []
    lines = [l for l in text.split("\n") if l.strip()]

    # ── Try table row format first ─────────────────────────────────────────
    # Format: DATE  DESCRIPTION  AMOUNT  [BALANCE]
    table_hits = 0
    for line in lines:
        m = TABLE_ROW.match(line.strip())
        if m:
            table_hits += 1

    if table_hits >= 3:
        # This looks like a table-format statement
        transactions = _parse_table_format(lines, vendor, statement_date)
        if transactions:
            return transactions

    # ── Fall back to line-by-line parsing ─────────────────────────────────
    return _parse_line_format(lines, vendor, statement_date)


def _parse_table_format(lines: List[str], vendor: str, statement_date: str) -> List[Dict]:
    """Parse statements where each transaction is a single table row."""
    transactions = []

    for line in lines:
        stripped = line.strip()
        if not stripped or should_skip(stripped):
            continue

        m = TABLE_ROW.match(stripped)
        if not m:
            continue

        date_raw    = m.group(1)
        description = m.group(2).strip()
        amount_str  = m.group(3).replace(",", "")

        # Clean up description — remove any balance info
        description = clean_merchant(description)
        if not description:
            continue

        try:
            amount = float(amount_str)
        except ValueError:
            continue

        is_payment = "payment" in description.lower() or "credit" in description.lower()

        transactions.append({
            "date":           normalize_date(date_raw),
            "merchant":       description,
            "amount":         amount,
            "is_payment":     is_payment,
            "memo_lines":     [],
            "statement_date": statement_date,
            "vendor":         vendor,
        })

    return transactions


def _parse_line_format(lines: List[str], vendor: str, statement_date: str) -> List[Dict]:
    """Parse statements where transactions may span multiple lines."""
    transactions = []
    current_txn = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if should_skip(stripped):
            continue

        date_match   = TXN_DATE.match(stripped)
        amount_match = AMOUNT_EOL.search(stripped)

        if date_match:
            if current_txn:
                transactions.append(current_txn)

            date_raw  = date_match.group(1)
            remainder = stripped[len(date_raw):].strip().lstrip("*").strip()

            amount = None
            merchant_raw = remainder

            if amount_match:
                amount_str   = amount_match.group(1).replace(",", "")
                amount       = float(amount_str)
                merchant_raw = AMOUNT_EOL.sub("", remainder).strip()

            merchant_raw = clean_merchant(merchant_raw)

            is_payment = (
                "payment" in merchant_raw.lower() or
                "credit" in merchant_raw.lower()
            )

            current_txn = {
                "date":           normalize_date(date_raw),
                "merchant":       merchant_raw,
                "amount":         amount,
                "is_payment":     is_payment,
                "memo_lines":     [],
                "statement_date": statement_date,
                "vendor":         vendor,
            }

        elif current_txn is not None:
            if amount_match and current_txn["amount"] is None:
                amount_str = amount_match.group(1).replace(",", "")
                current_txn["amount"] = float(amount_str)
                detail = AMOUNT_EOL.sub("", stripped).strip()
                detail = clean_merchant(detail)
                if detail and not should_skip(detail):
                    if not current_txn["merchant"]:
                        current_txn["merchant"] = detail
                    else:
                        current_txn["memo_lines"].append(detail)
            elif not should_skip(stripped):
                current_txn["memo_lines"].append(stripped)

    if current_txn:
        transactions.append(current_txn)

    # Filter out anything without an amount
    return [t for t in transactions if t["amount"] is not None]


def extract_transactions(pages: List[PageResult], vendor: str, statement_date: str) -> List[Dict]:
    """Extract transactions from all pages of a statement."""
    all_transactions = []
    for page in pages:
        if page.text:
            txns = extract_transactions_from_text(page.text, vendor, statement_date)
            all_transactions.extend(txns)

    # Deduplicate — same date + merchant + amount
    seen = set()
    unique = []
    for t in all_transactions:
        key = (t["date"], t["merchant"][:40], round(t["amount"], 2))
        if key not in seen:
            seen.add(key)
            unique.append(t)

    print(f"TRANSACTIONS: {len(unique)} found for {vendor} {statement_date}")
    return unique


def transactions_to_csv(transactions: List[Dict], vendor: str) -> str:
    """
    Convert transaction list to QuickBooks-compatible CSV string.
    Format: Date, Description, Amount, Memo, Account
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Description", "Amount", "Memo", "Account"])

    for t in transactions:
        amount = t["amount"]
        if t.get("is_payment"):
            amount = -abs(amount)
        else:
            amount = abs(amount)

        memo     = " | ".join(t["memo_lines"]) if t["memo_lines"] else ""
        merchant = t["merchant"] or "UNKNOWN"

        writer.writerow([
            t["date"],
            merchant,
            f"{amount:.2f}",
            memo,
            vendor,
        ])

    return output.getvalue()
