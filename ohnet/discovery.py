"""Network discovery via nmap (XML output, no shell, no text scraping)."""

from __future__ import annotations

import ipaddress
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .services import KNOWN_SERVICES, classify


class DiscoveryError(RuntimeError):
    pass


@dataclass
class Host:
    ip: str
    hostname: str | None = None
    mac: str | None = None
    vendor: str | None = None
    services: list[dict] = field(default_factory=list)


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise DiscoveryError(f"'{tool}' nicht gefunden – bitte installieren (z. B. apt install {tool}).")
    return path


def _run_nmap(args: list[str], timeout: int) -> ET.Element:
    cmd = [_require("nmap"), *args, "-oX", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise DiscoveryError(f"nmap-Timeout nach {timeout}s: {' '.join(cmd)}") from e
    if res.returncode != 0:
        raise DiscoveryError(f"nmap fehlgeschlagen ({res.returncode}): {res.stderr.strip()}")
    try:
        return ET.fromstring(res.stdout)
    except ET.ParseError as e:
        raise DiscoveryError(f"nmap-XML nicht lesbar: {e}") from e


def parse_nmap_xml(root: ET.Element) -> list[Host]:
    """Extract hosts (state up) with address, MAC, vendor, PTR name and open TCP ports."""
    hosts: list[Host] = []
    for h in root.iter("host"):
        status = h.find("status")
        if status is None or status.get("state") != "up":
            continue
        ip = mac = vendor = None
        for addr in h.findall("address"):
            if addr.get("addrtype") in ("ipv4", "ipv6"):
                ip = addr.get("addr")
            elif addr.get("addrtype") == "mac":
                mac = addr.get("addr", "").lower() or None
                vendor = addr.get("vendor")
        if not ip:
            continue
        hostname = None
        for hn in h.iter("hostname"):
            if hn.get("type") in ("PTR", "user") and hn.get("name"):
                hostname = hn.get("name")
                break
        services = []
        for port in h.iter("port"):
            state = port.find("state")
            if port.get("protocol") != "tcp" or state is None or state.get("state") != "open":
                continue
            svc = port.find("service")
            services.append(classify(int(port.get("portid")), svc.get("name") if svc is not None else None))
        hosts.append(Host(ip=ip, hostname=hostname, mac=mac, vendor=vendor,
                          services=sorted(services, key=lambda s: s["port"])))
    return hosts


_NEIGH_RE = re.compile(r"^(\S+)\s.*\blladdr\s+([0-9a-f:]{17})", re.I)
_ARP_RE = re.compile(r"\((\S+)\)\s+at\s+([0-9a-f:]{17})", re.I)


def neighbor_macs() -> dict[str, str]:
    """IP -> MAC from the kernel neighbour table (needed when nmap runs unprivileged)."""
    for tool, args, rx in (("ip", ["neigh", "show"], _NEIGH_RE), ("arp", ["-an"], _ARP_RE)):
        path = shutil.which(tool)
        if not path:
            continue
        out = subprocess.run([path, *args], capture_output=True, text=True, check=False).stdout
        return {m.group(1): m.group(2).lower() for m in map(rx.search, out.splitlines()) if m}
    return {}


NMAP_SERVICES = [Path("/usr/share/nmap/nmap-services"), Path("/usr/local/share/nmap/nmap-services"),
                 Path("/opt/homebrew/share/nmap/nmap-services")]


def top_tcp_ports(n: int, services_file: Path | None = None) -> list[int] | None:
    """Top-N TCP ports by frequency from nmap-services (same source as --top-ports)."""
    f = services_file or next((p for p in NMAP_SERVICES if p.exists()), None)
    if not f or not f.exists():
        return None
    entries = []
    for line in f.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3 and not line.startswith("#") and parts[1].endswith("/tcp"):
            entries.append((float(parts[2]), int(parts[1].split("/")[0])))
    return [p for _, p in sorted(entries, reverse=True)[:n]]


def ports_args(ports: str, services_file: Path | None = None) -> list[str]:
    """'top:1000' | 'all' | '22,80,443' -> nmap arguments.

    top:N = nmap's Top-N **plus** all KNOWN_SERVICES ports (1883/MQTT, 8123, 8006 …
    are not in nmap's Top-1000).
    """
    if ports == "all":
        return ["-p-"]
    if ports.startswith("top:"):
        n = int(ports[4:])
        top = top_tcp_ports(n, services_file)
        if top is None:
            return ["--top-ports", str(n)]
        return ["-p", "T:" + ",".join(map(str, sorted(set(top) | set(KNOWN_SERVICES))))]
    if re.fullmatch(r"[0-9,\-]+", ports):
        return ["-p", ports]
    raise ValueError(f"Ungültige Port-Angabe: {ports!r}")


def discover(targets: list[str], *, exclude: list[str] | None = None, ports: str = "top:1000",
             service_detection: bool = False, timing: int = 4, timeout: int = 3600,
             log=print) -> list[Host]:
    for t in targets:  # fail fast on typos; hostnames are passed through to nmap
        try:
            ipaddress.ip_network(t, strict=False)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9.\-]+", t):
                raise DiscoveryError(f"Ungültiges Ziel: {t!r}")
    ipv6 = any(":" in t for t in targets)
    common = [f"-T{timing}"] + (["-6"] if ipv6 else []) + (["--exclude", ",".join(exclude)] if exclude else [])

    log(f"[*] Host-Discovery: {' '.join(targets)}")
    live = parse_nmap_xml(_run_nmap(["-sn", *common, *targets], timeout))
    log(f"[+] {len(live)} Hosts online")
    if not live:
        return []

    log(f"[*] Port-Scan ({ports}{', mit -sV' if service_detection else ''}) auf {len(live)} Hosts …")
    scan_args = ["-Pn", "--open", *ports_args(ports), *(["-sV"] if service_detection else []), *common]
    scanned = {h.ip: h for h in parse_nmap_xml(_run_nmap([*scan_args, *[h.ip for h in live]], timeout))}

    neigh = neighbor_macs()
    for h in live:
        s = scanned.get(h.ip)
        if s:
            h.services = s.services
            h.hostname = h.hostname or s.hostname
            h.mac, h.vendor = h.mac or s.mac, h.vendor or s.vendor
        h.mac = h.mac or neigh.get(h.ip)
        log(f"    {h.ip:<15} {h.hostname or '-':<28} {h.mac or '-':<17} "
            f"Ports: {', '.join(str(x['port']) for x in h.services) or '-'}")
    return live
