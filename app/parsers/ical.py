"""iCal parser for race event discovery.

Supports any site that exports events in iCal/ICS format,
including WordPress The Events Calendar plugin (?ical=1).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# iCal property value with optional parameters, e.g. "DTSTART;TZID=America/Sao_Paulo:20260601T080000"
_PROP_RE = re.compile(r"^([A-Z\-]+)(?:;[^:]+)?:(.*)$")


def _unfold(text: str) -> list[str]:
    """Join continuation lines (RFC 5545 §3.1)."""
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return value.replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n").replace("\\N", "\n").replace("\\\\", "\\")


def _parse_dt(raw: str) -> datetime | None:
    value = raw.split(":")[-1].strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            dt = datetime.strptime(value, fmt)
            if value.endswith("Z"):
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _parse_events(ical_text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in _unfold(ical_text):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
        elif current is not None:
            m = _PROP_RE.match(line)
            if m:
                key, val = m.group(1), _unescape(m.group(2))
                current.setdefault(key, val)  # keep first occurrence

    return events


def _city_from_location(location: str) -> str | None:
    """Best-effort city extraction from iCal LOCATION string."""
    parts = [p.strip() for p in location.split(",")]
    # Typical formats: "Venue, City, State" or "City, State, Country"
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else None


async def fetch_races(
    source_name: str,
    ical_url: str,
    default_state: str | None,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Fetch and parse an iCal feed, returning a list of race dicts."""
    try:
        response = await client.get(ical_url, follow_redirects=True, timeout=20)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Erro ao buscar iCal {ical_url}: {exc}") from exc

    events = _parse_events(response.text)
    logger.info("iCal %s: %d eventos encontrados", source_name, len(events))

    races: list[dict] = []
    for event in events:
        title = event.get("SUMMARY", "").strip()
        if not title:
            continue

        location = event.get("LOCATION", "").strip()
        event_date = _parse_dt(event.get("DTSTART", "")) if event.get("DTSTART") else None
        link = event.get("URL", "").strip() or ical_url

        races.append(
            {
                "title": title,
                "sourceUrl": link,
                "sourceName": source_name,
                "eventDate": event_date,
                "state": default_state,
                "city": _city_from_location(location) if location else None,
                "location": location or None,
                "rawPayload": dict(event),
            }
        )

    return races
