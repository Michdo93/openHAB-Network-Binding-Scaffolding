"""Identifier helpers for openHAB Thing UIDs and Item names."""

from __future__ import annotations

import re

_INVALID = re.compile(r"[^a-z0-9_]")
_MULTI_US = re.compile(r"_+")


def sanitize(name: str, fallback_prefix: str = "h") -> str:
    """Turn an arbitrary name into a valid openHAB identifier.

    Result matches ``[a-z][a-z0-9_]*`` and is therefore valid both as a Thing UID
    segment and as part of an Item name.
    """
    s = name.strip().lower().replace("-", "_").replace(".", "_")
    s = _INVALID.sub("", s)
    s = _MULTI_US.sub("_", s).strip("_")
    if not s or not s[0].isalpha():
        s = f"{fallback_prefix}_{s}".rstrip("_")
    return s


def ip_id(ip: str) -> str:
    """ID for hosts without reverse DNS: 192.168.1.5 -> ip_192_168_1_5."""
    return "ip_" + _MULTI_US.sub("_", _INVALID.sub("_", ip.lower())).strip("_")


def unique(base: str, taken: set[str]) -> str:
    """Return ``base`` or ``base_2``, ``base_3`` ... not yet in ``taken``; registers it."""
    candidate, n = base, 2
    while candidate in taken:
        candidate = f"{base}_{n}"
        n += 1
    taken.add(candidate)
    return candidate
