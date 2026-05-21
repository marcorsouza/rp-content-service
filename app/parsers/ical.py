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

# Brazilian state full names → abbreviation
_BR_STATE_MAP: dict[str, str] = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM",
    "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF", "Espírito Santo": "ES",
    "Goiás": "GO", "Maranhão": "MA", "Mato Grosso": "MT", "Mato Grosso do Sul": "MS",
    "Minas Gerais": "MG", "Pará": "PA", "Paraíba": "PB", "Paraná": "PR",
    "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
    "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC",
    "São Paulo": "SP", "Sergipe": "SE", "Tocantins": "TO",
}
_BR_STATE_ABBR: frozenset[str] = frozenset(_BR_STATE_MAP.values())


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


def _extract_city_state(location: str) -> tuple[str | None, str | None]:
    """
    Extract (city, state_abbr) from an iCal LOCATION string.

    Handles formats produced by WordPress "The Events Calendar" plugin:
      "Venue, Street, Number, City, Full State Name, ZIP, Country"
      "Venue, City, ST, ZIP, Country"
      "City, ST, Brasil"
    Returns (city, state_abbreviation) — either may be None.
    """
    parts = [p.strip() for p in location.split(",")]
    city: str | None = None
    state: str | None = None

    for i, part in enumerate(parts):
        # Match full state name (e.g. "Rio Grande do Sul")
        if part in _BR_STATE_MAP:
            state = _BR_STATE_MAP[part]
            city = parts[i - 1] if i > 0 else None
            break

        upper = part.upper()

        # Match bare abbreviation (e.g. "RS")
        if upper in _BR_STATE_ABBR:
            state = upper
            city = parts[i - 1] if i > 0 else None
            break

        # Match abbreviation followed by ZIP (e.g. "RS 90030-000" or "RS90030000")
        for abbr in _BR_STATE_ABBR:
            if upper.startswith(abbr + " ") or upper.startswith(abbr + "-") or re.match(rf"^{abbr}\d", upper):
                state = abbr
                city = parts[i - 1] if i > 0 else None
                break
        if state:
            break

    # Fallback: second-to-last part (skip common country strings)
    if not city:
        candidates = [p for p in parts if p.lower() not in ("brasil", "brazil", "br", "")]
        city = candidates[-2] if len(candidates) >= 2 else (candidates[-1] if candidates else None)

    return city, state


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

        city, state = _extract_city_state(location) if location else (None, None)

        races.append(
            {
                "title": title,
                "sourceUrl": link,
                "sourceName": source_name,
                "eventDate": event_date,
                "state": state or default_state,
                "city": city,
                "location": location or None,
                "rawPayload": dict(event),
            }
        )

    return races
