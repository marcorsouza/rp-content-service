"""Text cleanup helpers for external content feeds."""
from __future__ import annotations

import html
import re


def clean_external_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_title_source(title: str) -> tuple[str, str | None]:
    clean_title = clean_external_text(title)
    match = re.match(r"^(?P<title>.+?)\s+-\s+(?P<source>[^-]{3,80})$", clean_title)
    if not match:
        return clean_title, None
    return match.group("title").strip(), match.group("source").strip()
