"""Privacy guard for LLM requests (INITIAL.md rule 3: no raw PII to the LLM).

Payloads sent to the LLM must identify students by pseudonymous id only (e.g. ``S-0042``).
:func:`assert_no_pii` is the last line of defence: it serializes the full request and refuses
to send it if any forbidden term (student full name, admission number) appears anywhere.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["PIIViolationError", "assert_no_pii", "forbidden_terms", "serialize_payload"]

MIN_TERM_LENGTH = 2


class PIIViolationError(ValueError):
    """Raised when an LLM payload contains personally identifying information."""


def serialize_payload(payload: Any) -> str:
    """Deterministic text form of a payload (strings are used as-is)."""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def forbidden_terms(
    names: Iterable[str | None], admission_numbers: Iterable[str | None]
) -> set[str]:
    """Build the forbidden-term set from student names and admission numbers."""
    terms: set[str] = set()
    for value in (*names, *admission_numbers):
        if value is None:
            continue
        cleaned = " ".join(value.split())
        if len(cleaned) >= MIN_TERM_LENGTH:
            terms.add(cleaned)
    return terms


def _pattern(term: str) -> re.Pattern[str]:
    # Whitespace inside a name may be any run of whitespace; the term must not be glued to
    # other word characters (so "Sai Rao" does not match inside "Sai Raoul" but does match
    # "Sai  Rao," or "...\"Sai Rao\"...").
    parts = [re.escape(p) for p in term.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def assert_no_pii(payload: Any, forbidden: Iterable[str]) -> None:
    """Raise :class:`PIIViolationError` if any forbidden term occurs in the serialized payload.

    Matching is case-insensitive and whitespace-tolerant. The error message never echoes the
    offending value (it would end up in logs).
    """
    text = serialize_payload(payload)
    hits = 0
    for term in forbidden:
        term = term.strip()
        if len(term) < MIN_TERM_LENGTH:
            continue
        if _pattern(term).search(text):
            hits += 1
    if hits:
        logger.error("Blocked LLM request: %d forbidden PII term(s) found in payload", hits)
        raise PIIViolationError(
            f"LLM payload contains {hits} forbidden personal identifier(s); request blocked"
        )
