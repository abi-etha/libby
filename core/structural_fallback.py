# core/structural_fallback.py

from typing import List, Tuple
from core.vendor_fingerprint import VENDORS
from core.image_extractor import PageResult


def structural_split(pages: List[PageResult], vendor: str = "UNKNOWN") -> List[Tuple[int, List[PageResult]]]:
    """
    Structural fallback splitter.
    Groups pages into fixed-size chunks based on vendor rules.
    Returns a list of (index, [PageResult]) tuples.
    """

    # 1. Determine chunk size
    if vendor in VENDORS and "structural_chunk" in VENDORS[vendor]:
        chunk = VENDORS[vendor]["structural_chunk"]
    else:
        chunk = 1  # default fallback

    statements = []
    index = 1

    # 2. Chunk pages deterministically
    for i in range(0, len(pages), chunk):
        group = pages[i:i + chunk]

        # Safety: ensure group contains only PageResult objects
        group = [p for p in group if isinstance(p, PageResult)]

        statements.append((index, group))
        index += 1

    return statements
