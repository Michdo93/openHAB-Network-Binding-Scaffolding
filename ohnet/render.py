"""Render inventory -> openHAB DSL files with Jinja2."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, StrictUndefined

BUILTIN_TEMPLATES = Path(__file__).parent / "templates"

OUTPUTS = {
    "network.things.j2": "network.things",
    "network.items.j2": "network.items",
    "network.sitemap.j2": "{sitemap_name}.sitemap",
}


def oh_string(value) -> str:
    """Quoted openHAB DSL string (escapes backslash and double quote)."""
    return json.dumps(str(value), ensure_ascii=False)


def make_env(template_dir: Path | None = None) -> Environment:
    loaders = [FileSystemLoader(str(template_dir))] if template_dir else []
    loaders.append(FileSystemLoader(str(BUILTIN_TEMPLATES)))
    env = Environment(loader=ChoiceLoader(loaders), undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
                      autoescape=False)
    env.filters["q"] = oh_string
    return env


def _view(inv: dict) -> dict:
    """Template context: only enabled devices/services, item names precomputed."""
    st = inv["settings"]
    prefix = st["item_prefix"]
    devices = []
    for d in inv["devices"]:
        if not d.get("enabled", True):
            continue
        p = f"{prefix}{d['id']}"
        services = [{**s, "item": f"{p}_{s['id']}", "uid": f"{d['id']}_{s['id']}"}
                    for s in d.get("services") or []]
        devices.append({
            **d,
            "item": p,
            "location": d.get("location") or st["location"],
            "refresh_interval": d.get("refresh_interval") or st["refresh_interval"],
            "services": [s for s in services if s.get("enabled")],
            "review": [s for s in services if not s.get("enabled")],
        })
    sp = inv["speedtest"]
    speedtest = None
    if sp.get("enabled"):
        if not (sp.get("url") and sp.get("file_name")):
            raise ValueError("speedtest.enabled=true benötigt speedtest.url und speedtest.file_name")
        speedtest = {**sp, "item": f"{prefix}Speedtest"}
    return {"settings": st, "devices": devices, "speedtest": speedtest,
            "generated": dt.datetime.now().isoformat(timespec="seconds")}


def render(inv: dict, out_dir: Path, template_dir: Path | None = None) -> list[Path]:
    env = make_env(template_dir)
    ctx = _view(inv)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for tpl, target in OUTPUTS.items():
        path = out_dir / target.format(**inv["settings"])
        path.write_text(env.get_template(tpl).render(**ctx), encoding="utf-8")
        written.append(path)
    return written
