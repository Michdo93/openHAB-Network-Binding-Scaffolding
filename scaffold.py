#!/usr/bin/env python3
"""openHAB Network Binding Scaffolding – CLI.

  scaffold.py discover 192.168.1.0/24          # nmap -> inventory.yaml (merge)
  scaffold.py render                           # inventory.yaml -> out/*.things/.items/.sitemap
  scaffold.py validate                         # statische Prüfung der Ausgabe
  scaffold.py run 192.168.1.0/24               # alles in einem
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ohnet import __version__, inventory
from ohnet.discovery import DiscoveryError, discover
from ohnet.render import render
from ohnet.validate import validate_dir


def cmd_discover(a) -> int:
    inv = inventory.load(a.inventory) if a.inventory.exists() else inventory.empty()
    if a.speedtest_url or a.speedtest_file:
        inv["speedtest"].update(enabled=True, url=a.speedtest_url or inv["speedtest"]["url"],
                                file_name=a.speedtest_file or inv["speedtest"]["file_name"])
    hosts = discover(a.targets, exclude=a.exclude, ports=a.ports,
                     service_detection=a.service_detection, timing=a.timing)
    inv, added, updated = inventory.merge(inv, hosts)
    inventory.save(inv, a.inventory)
    review = sum(1 for d in inv["devices"] for s in d.get("services") or [] if not s.get("enabled"))
    print(f"[+] {a.inventory}: {added} neu, {updated} aktualisiert, {len(inv['devices'])} gesamt"
          f"{f', {review} Dienste zur Prüfung (enabled: false)' if review else ''}")
    return 0


def _apply_overrides(inv: dict, a) -> bool:
    """CLI-Render-Optionen ins Inventory übernehmen (persistiert, damit Re-Renders konsistent sind)."""
    changed = False
    for key in ("item_prefix", "chart_service", "sitemap_name"):
        val = getattr(a, key, None)
        if val is not None:
            inv["settings"][key], changed = val, True
    if getattr(a, "no_charts", False):
        inv["settings"]["charts"], changed = False, True
    return changed


def cmd_render(a) -> int:
    if not a.inventory.exists():
        print(f"[-] {a.inventory} fehlt – zuerst 'discover' ausführen.", file=sys.stderr)
        return 1
    inv = inventory.load(a.inventory)
    if _apply_overrides(inv, a):
        inventory.save(inv, a.inventory)
    for p in render(inv, a.out, a.templates):
        print(f"[+] {p}")
    return cmd_validate(a, inv)


def cmd_validate(a, inv: dict | None = None) -> int:
    inv = inv or inventory.load(a.inventory)
    errors = validate_dir(a.out, inv["settings"]["sitemap_name"])
    for e in errors:
        print(f"[!] {e}", file=sys.stderr)
    print("[+] Validierung OK" if not errors else f"[-] {len(errors)} Fehler")
    return 1 if errors else 0


def cmd_run(a) -> int:
    return cmd_discover(a) or cmd_render(a)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("-i", "--inventory", type=Path, default=Path("inventory.yaml"))
    ap.add_argument("-o", "--out", type=Path, default=Path("out"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def disc_args(p):
        p.add_argument("targets", nargs="+", help="CIDR, IP-Bereich oder Host (nmap-Syntax)")
        p.add_argument("--exclude", nargs="*", default=None, help="auszuschließende Hosts")
        p.add_argument("--ports", default="top:1000", help="top:N | all | 22,80,8000-8100 (Default top:1000)")
        p.add_argument("--service-detection", "-sV", action="store_true", help="nmap -sV (langsamer, bessere Namen)")
        p.add_argument("--timing", type=int, choices=range(0, 6), default=4, help="nmap -T (Default 4)")
        p.add_argument("--speedtest-url", help="aktiviert den Speedtest-Thing (Pflicht: url + file)")
        p.add_argument("--speedtest-file", help="Download-Datei auf dem Speedtest-Server")

    def render_args(p):
        p.add_argument("--templates", type=Path, help="eigenes Template-Verzeichnis (überschreibt einzelne Templates)")
        p.add_argument("--item-prefix")
        p.add_argument("--chart-service", help="Persistence-Service für Charts, z. B. rrd4j oder influxdb")
        p.add_argument("--sitemap-name")
        p.add_argument("--no-charts", action="store_true")

    disc_args(p := sub.add_parser("discover", help="Netz scannen, Inventory anlegen/aktualisieren"))
    p.set_defaults(fn=cmd_discover)
    render_args(p := sub.add_parser("render", help="Inventory -> openHAB-Dateien"))
    p.set_defaults(fn=cmd_render)
    sub.add_parser("validate", help="generierte Dateien prüfen").set_defaults(fn=cmd_validate)
    p = sub.add_parser("run", help="discover + render + validate")
    disc_args(p), render_args(p)
    p.set_defaults(fn=cmd_run)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (DiscoveryError, ValueError) as e:
        print(f"[-] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
