# core/transaction_extractor.py
#
# Extracts transactions from statement pages and returns
# rows formatted for QuickBooks CSV import.
#
# Handles:
#   - Standard single-line transactions
#   - Multi-line transactions (airlines, hotels, etc.)
#   - Payments and credits (negative amounts)
#   - Fees

import re
import csv
import io
from typing import List, Dict, Optional
from core.image_extractor import PageResult


# ── Date pattern for transaction lines ────────────────────────────────────
# Matches: 01/15/20  or  01/15/2020
TXN_DATE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4})\*?")

# Amount at end of line: $1,234.56  or  -$1,234.56  or  1,234.56
TXN_AMOUNT = re.compile(r"-?\$?([\d,]+\.\d{2})\s*$")

# Lines to skip — not transactions
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
        r"^continued on reverse",
        r"^closing date",
        r"^payment due",
        r"^previous balance",
        r"^payments?/credits?",
        r"^new balance",
        r"^days in billing",
        r"^interest charge",
        r"^your annual",
        r"^cash advances",
        r"^\(v\) variable",
        r"^transactions? dated",
        r"^from\s+to\s+",
        r"^2020 fees",
        r"^2019 fees",
        r"^total fees",
        r"^total interest",
        r"^membership rewards",
        r"^foreign\s+spend",
        r"^\s*$",
    ]
]

# Known section headers that signal we're in transaction territory
SECTION_HEADERS = [
    "payments and credits",
    "new charges",
    "fees",
]


def normalize_date(raw: str) -> str:
    """Convert MM/DD/YY or MM/DD/YYYY to YYYY-MM-DD for QuickBooks."""
    parts = raw.replace("*", "").strip().split("/")
    if len(parts) != 3:
        return raw
    month, day, year = parts
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def clean_merchant(raw: str) -> str:
    """Clean up merchant name — remove extra codes and numbers."""
    # Remove trailing phone numbers like 210-342-8728
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
    Returns list of dicts ready for CSV output.
    """
    transactions = []
    lines = text.split("\n")

    current_txn = None
    in_transaction_section = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Detect section headers
        lower = stripped.lower()
        if any(h in lower for h in SECTION_HEADERS):
            in_transaction_section = True
            continue

        if should_skip(stripped):
            continue

        # Check if line starts with a date — new transaction
        date_match = TXN_DATE.match(stripped)
        amount_match = TXN_AMOUNT.search(stripped)

        if date_match:
            # Save previous transaction if we have one
            if current_txn:
                transactions.append(current_txn)

            date_raw = date_match.group(1)
            remainder = stripped[len(date_raw):].strip().lstrip("*").strip()

            # Extract amount if on same line
            amount = None
            merchant_raw = remainder
            if amount_match:
                amount_str = amount_match.group(1).replace(",", "")
                amount = float(amount_str)
                merchant_raw = TXN_AMOUNT.sub("", remainder).strip()

            # Check if this is a payment (negative)
            is_payment = "-" in stripped[:stripped.index(date_raw) + len(date_raw) + 5] or \
                         "payment" in merchant_raw.lower() or \
                         "credit" in merchant_raw.lower()

            current_txn = {
                "date":          normalize_date(date_raw),
                "merchant":      clean_merchant(merchant_raw),
                "amount":        amount,
                "is_payment":    is_payment,
                "memo_lines":    [],
                "statement_date": statement_date,
                "vendor":        vendor,
            }

        elif current_txn is not None:
            # Continuation line — could be merchant detail or amount
            if amount_match and current_txn["amount"] is None:
                amount_str = amount_match.group(1).replace(",", "")
                current_txn["amount"] = float(amount_str)
                # If merchant is still empty, this line before amount is it
                detail = TXN_AMOUNT.sub("", stripped).strip()
                if detail and not should_skip(detail):
                    if not current_txn["merchant"]:
                        current_txn["merchant"] = clean_merchant(detail)
                    else:
                        current_txn["memo_lines"].append(detail)
            elif not should_skip(stripped):
                # Extra detail lines — keep as memo
                current_txn["memo_lines"].append(stripped)

    # Don't forget the last transaction
    if current_txn:
        transactions.append(current_txn)

    # Filter out anything without a real amount
    transactions = [t for t in transactions if t["amount"] is not None]

    return transactions


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
        key = (t["date"], t["merchant"][:30], t["amount"])
        if key not in seen:
            seen.add(key)
            unique.append(t)

    print(f"TRANSACTIONS: {len(unique)} found for {vendor} {statement_date}")
    return unique


def transactions_to_csv(transactions: List[Dict], vendor: str) -> str:
    """
    Convert transaction list to QuickBooks-compatible CSV string.

    QuickBooks Online import format:
    Date, Description, Amount, Memo, Account
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # QuickBooks compatible header
    writer.writerow(["Date", "Description", "Amount", "Memo", "Account"])

    for t in transactions:
        amount = t["amount"]
        # Payments are negative (money coming in), charges are positive
        if t.get("is_payment"):
            amount = -abs(amount)
        else:
            amount = abs(amount)

        memo = " | ".join(t["memo_lines"]) if t["memo_lines"] else ""
        merchant = t["merchant"] or "UNKNOWN MERCHANT"

        writer.writerow([
            t["date"],
            merchant,
            f"{amount:.2f}",
            memo,
            vendor,
        ])

    return output.getvalue()
