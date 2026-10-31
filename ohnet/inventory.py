"""Editable YAML inventory between discovery and rendering.

Re-running discovery merges into an existing inventory: manual edits
(id, label, location, enabled, address ...) are kept, devices that are
offline during the scan are not dropped.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from .discovery import Host
from .naming import ip_id, sanitize, unique

DEFAULT_SETTINGS = {
    "item_prefix": "Net_",          # avoids collisions with existing items
    "location": "Netzwerk",         # Thing location
    "refresh_interval": 60000,      # ms, pingdevice/servicedevice
    "sitemap_name": "network",
    "sitemap_label": "Netzwerk-Monitoring",
    "chart_service": None,          # e.g. "rrd4j" / "influxdb"; None = default persistence
    "charts": True,
}

DEFAULT_SPEEDTEST = {
    "enabled": False,
    "url": None,                    # required by the binding
    "file_name": None,              # required by the binding
    "refresh_interval": 20,         # MINUTES (binding unit!)
    "initial_delay": 5,
    "location": "Internet",
}


def empty() -> dict:
    return {"version": 1, "settings": dict(DEFAULT_SETTINGS),
            "speedtest": dict(DEFAULT_SPEEDTEST), "devices": []}


def load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    inv = empty()
    inv["settings"].update(data.get("settings") or {})
    inv["speedtest"].update(data.get("speedtest") or {})
    inv["devices"] = data.get("devices") or []
    return inv


def save(inv: dict, path: Path) -> None:
    header = ("# openHAB Network Binding Scaffolding – Inventory\n"
              "# Frei editierbar: id/label/location/enabled pro Gerät und Dienst.\n"
              "# Erneutes 'discover' behält diese Änderungen bei.\n")
    inv = {**inv, "generated": dt.datetime.now().isoformat(timespec="seconds")}
    path.write_text(header + yaml.safe_dump(inv, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _device_from_host(h: Host, taken: set[str]) -> dict:
    short = h.hostname.split(".")[0] if h.hostname else None
    did = unique(sanitize(short) if short else ip_id(h.ip), taken)
    return {
        "id": did,
        "label": short or h.ip,
        "address": h.ip,
        "ip": h.ip,
        "mac": h.mac,
        "vendor": h.vendor,
        "hostname": h.hostname,
        "enabled": True,
        "services": [dict(s) for s in h.services],
    }


def _merge_services(old: list[dict], new: list[dict]) -> list[dict]:
    by_port = {s["port"]: s for s in old}
    for s in new:
        by_port.setdefault(s["port"], s)       # keep manual edits of known ports
    taken: set[str] = set()
    result = []
    for s in sorted(by_port.values(), key=lambda x: x["port"]):
        s["id"] = unique(sanitize(str(s["id"]), "svc"), taken)
        result.append(s)
    return result


def merge(inv: dict, hosts: list[Host]) -> tuple[dict, int, int]:
    """Merge scan results into ``inv``. Returns (inv, added, updated)."""
    devices = inv["devices"]
    taken = {d["id"] for d in devices}
    by_mac = {d["mac"].lower(): d for d in devices if d.get("mac")}
    by_ip = {d["ip"]: d for d in devices if d.get("ip")}
    added = updated = 0
    for h in hosts:
        d = (by_mac.get(h.mac) if h.mac else None) or by_ip.get(h.ip)
        if d is None:
            d = _device_from_host(h, taken)
            devices.append(d)
            added += 1
            continue
        if d.get("address") == d.get("ip"):     # follow IP changes unless address was edited
            d["address"] = h.ip
        d["ip"] = h.ip
        d["mac"] = d.get("mac") or h.mac
        d["vendor"] = d.get("vendor") or h.vendor
        d["hostname"] = h.hostname or d.get("hostname")
        d["services"] = _merge_services(d.get("services") or [], h.services)
        updated += 1
    devices.sort(key=lambda d: d["id"])
    return inv, added, updated
