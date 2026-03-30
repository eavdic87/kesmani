"""
Trade journal module for KešMani.

Persists trade journal entries to data/journal.json and provides
CRUD helpers used by the journal dashboard page.

Entry schema:
  {
    "id": "abc12345",
    "trade_id": "optional-position-id",
    "ticker": "NVDA",
    "date": "2026-03-30",
    "setup_type": "breakout",
    "notes": "Strong volume breakout above resistance.",
    "emotions": "confident",
    "tags": ["momentum", "earnings-play"],
    "screenshot_path": null
  }

Valid setup_type values:
  breakout | pullback | reversal | earnings_play | swing | scalp
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

JOURNAL_FILE = DATA_DIR / "journal.json"

VALID_SETUP_TYPES = frozenset(
    ["breakout", "pullback", "reversal", "earnings_play", "swing", "scalp"]
)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_journal() -> list[dict]:
    """Load journal entries from JSON, returning an empty list if missing."""
    if not JOURNAL_FILE.exists():
        return []
    try:
        with open(JOURNAL_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as exc:
        logger.error("Failed to load journal: %s", exc)
        return []


def _save_journal(entries: list[dict]) -> None:
    """Persist journal entries to JSON."""
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL_FILE, "w") as f:
        json.dump(entries, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_journal_entry(
    ticker: str,
    notes: str,
    setup_type: str = "swing",
    emotions: str = "",
    tags: list[str] | None = None,
    trade_id: Optional[str] = None,
    screenshot_path: Optional[str] = None,
) -> dict:
    """
    Add a new journal entry.

    Parameters
    ----------
    ticker:
        Equity symbol this entry relates to.
    notes:
        Free-text trade notes (rationale, observations, lessons learned).
    setup_type:
        One of: breakout, pullback, reversal, earnings_play, swing, scalp.
    emotions:
        Self-reported emotional state (e.g. "confident", "anxious", "FOMO").
    tags:
        Optional list of free-form tags.
    trade_id:
        Optional ID linking to an open/closed position in tracker.py.
    screenshot_path:
        Optional filesystem path or URL to a chart screenshot.

    Returns
    -------
    The newly created journal entry dict.
    """
    if setup_type not in VALID_SETUP_TYPES:
        logger.warning("Unknown setup_type '%s'. Using 'swing'.", setup_type)
        setup_type = "swing"

    entry: dict = {
        "id": _generate_id(),
        "trade_id": trade_id,
        "ticker": ticker.upper(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "setup_type": setup_type,
        "notes": notes,
        "emotions": emotions,
        "tags": tags or [],
        "screenshot_path": screenshot_path,
    }

    entries = _load_journal()
    entries.append(entry)
    _save_journal(entries)
    logger.info("Journal entry added for %s (%s)", ticker, setup_type)
    return entry


def get_journal_entries(
    ticker: Optional[str] = None,
    date_from: Optional[str] = None,
    setup_type: Optional[str] = None,
) -> list[dict]:
    """
    Return journal entries, optionally filtered.

    Parameters
    ----------
    ticker:
        If provided, only return entries for this ticker (case-insensitive).
    date_from:
        ISO 8601 date string (e.g. "2026-01-01").  Only entries on or after
        this date are returned.
    setup_type:
        If provided, only return entries with this setup type.

    Returns
    -------
    List of entry dicts, newest first.
    """
    entries = _load_journal()

    if ticker:
        entries = [e for e in entries if e.get("ticker", "").upper() == ticker.upper()]

    if date_from:
        entries = [e for e in entries if e.get("date", "") >= date_from]

    if setup_type:
        entries = [e for e in entries if e.get("setup_type") == setup_type]

    return sorted(entries, key=lambda e: e.get("date", ""), reverse=True)


def delete_journal_entry(entry_id: str) -> bool:
    """
    Delete a journal entry by ID.

    Returns
    -------
    True if found and deleted, False otherwise.
    """
    entries = _load_journal()
    original_len = len(entries)
    entries = [e for e in entries if e.get("id") != entry_id]
    if len(entries) < original_len:
        _save_journal(entries)
        return True
    return False


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _generate_id() -> str:
    """Generate a short unique ID."""
    import uuid
    return str(uuid.uuid4())[:8]
