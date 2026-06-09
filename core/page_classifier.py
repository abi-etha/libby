# core/page_classifier.py
#
# Classifies each page into a document type based on keyword scoring.
# Document types determine downstream parsing behavior.
#
# Types:
#   bank_statement   - checking/savings account statements
#   credit_statement - credit card statements
#   utility_bill     - electric, water, gas, internet, phone bills
#   invoice          - vendor invoices / bills for services
#   receipt          - purchase receipts
#   check            - paper checks
#   paystub          - payroll / earnings statements
#   tax_doc          - tax forms (W2, 1099, etc.)
#   other            - anything else

import re
from typing import List
from core.image_extractor import PageResult

# ── Keyword sets per doc type ──────────────────────────────────────────────
# Order matters — more specific types come first
DOC_TYPE_KEYWORDS = {
    "check": [
        "pay to the order of",
        "memo",
        "void",
        "authorized signature",
        "routing number",
        "check number",
        "negotiable",
        "non-negotiable",
    ],
    "paystub": [
        "earnings statement",
        "pay stub",
        "paystub",
        "gross pay",
        "net pay",
        "ytd earnings",
        "federal withholding",
        "fica",
        "social security tax",
        "medicare tax",
        "pay period",
        "hours worked",
        "regular earnings",
        "overtime",
    ],
    "tax_doc": [
        "form w-2",
        "form 1099",
        "form 1040",
        "schedule c",
        "schedule e",
        "department of the treasury",
        "internal revenue service",
        "employer identification number",
        "ein:",
        "wages, tips",
        "taxable wages",
        "federal income tax withheld",
        "social security wages",
    ],
    "receipt": [
        "receipt",
        "thank you for your purchase",
        "thank you for shopping",
        "subtotal",
        "sales tax",
        "items sold",
        "cashier",
        "transaction id",
        "authorization",
        "approved",
        "change due",
        "card type",
        "store #",
    ],
    "invoice": [
        "invoice",
        "invoice number",
        "invoice #",
        "invoice date",
        "bill to",
        "ship to",
        "purchase order",
        "po number",
        "due date",
        "net 30",
        "net 60",
        "remit to",
        "payment terms",
        "line items",
        "qty",
        "unit price",
        "subtotal",
    ],
    "credit_statement": [
        "credit card",
        "credit account",
        "minimum payment due",
        "minimum payment",
        "new charges",
        "new balance",
        "closing date",
        "payment due date",
        "credit limit",
        "available credit",
        "cash advance",
        "rewards",
        "membership rewards",
        "points earned",
        "annual percentage rate",
        "apr",
        "revolving",
    ],
    "bank_statement": [
        "account summary",
        "account number",
        "routing number",
        "opening balance",
        "closing balance",
        "beginning balance",
        "ending balance",
        "deposits",
        "withdrawals",
        "direct deposit",
        "overdraft",
        "available balance",
        "statement period",
        "statement date",
        "checking account",
        "savings account",
        "monthly service fee",
    ],
    "utility_bill": [
        "account number",
        "service address",
        "amount due",
        "due date",
        "kwh",
        "kilowatt",
        "therms",
        "gallons used",
        "water usage",
        "electric service",
        "gas service",
        "internet service",
        "cable service",
        "wireless",
        "data usage",
        "billing period",
        "previous balance",
        "current charges",
    ],
}

# How many keyword hits to consider a strong match
STRONG_MATCH_THRESHOLD = 3


def classify_page(page: PageResult) -> str:
    """
    Score a single page against all doc type keyword sets.
    Returns the best matching doc type, or 'other'.
    """
    if not page.text:
        return "other"

    text_lower = page.text.lower()

    scores = {doc_type: 0 for doc_type in DOC_TYPE_KEYWORDS}

    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                scores[doc_type] += 1

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score == 0:
        return "other"

    return best_type


def classify_pages(pages: List[PageResult]) -> List[str]:
    """Classify a list of pages, returning a doc type per page."""
    return [classify_page(p) for p in pages]


def majority_doc_type(pages: List[PageResult]) -> str:
    """
    For a group of pages, return the most common doc type.
    Used to label a multi-page statement.
    """
    if not pages:
        return "other"

    types = classify_pages(pages)
    counts = {}
    for t in types:
        counts[t] = counts.get(t, 0) + 1

    return max(counts, key=counts.get)


def needs_csv(doc_type: str) -> bool:
    """Returns True if this doc type should generate a CSV."""
    return doc_type in ("bank_statement", "credit_statement")


# Human-readable short labels for filenames
DOC_TYPE_LABELS = {
    "bank_statement":   "BANK",
    "credit_statement": "CREDIT",
    "utility_bill":     "UTIL",
    "invoice":          "INV",
    "receipt":          "RCPT",
    "check":            "CHK",
    "paystub":          "PAY",
    "tax_doc":          "TAX",
    "other":            "DOC",
}


def doc_type_label(doc_type: str) -> str:
    return DOC_TYPE_LABELS.get(doc_type, "DOC")
