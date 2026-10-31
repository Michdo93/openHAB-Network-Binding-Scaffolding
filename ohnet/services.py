"""Port -> service classification.

``KNOWN_SERVICES`` are enabled by default. Any other open port lands in the
inventory with ``enabled: false`` so it can be reviewed manually.
"""

from __future__ import annotations

from .naming import sanitize

# port: (id, label)
KNOWN_SERVICES: dict[int, tuple[str, str]] = {
    21: ("ftp", "FTP"),
    22: ("ssh", "SSH"),
    23: ("telnet", "Telnet"),
    53: ("dns", "DNS"),
    80: ("http", "HTTP"),
    139: ("netbios", "NetBIOS"),
    443: ("https", "HTTPS"),
    445: ("smb", "SMB"),
    548: ("afp", "AFP"),
    554: ("rtsp", "RTSP"),
    631: ("ipp", "IPP"),
    1883: ("mqtt", "MQTT"),
    3306: ("mysql", "MySQL"),
    3389: ("rdp", "RDP"),
    5000: ("http_5000", "HTTP (Flask/UPnP)"),
    5432: ("postgres", "PostgreSQL"),
    5900: ("vnc", "VNC"),
    5985: ("winrm", "WinRM"),
    5986: ("winrm_s", "WinRM (TLS)"),
    8006: ("proxmox", "Proxmox"),
    8080: ("http_alt", "HTTP alt"),
    8083: ("websockets", "WebSockets"),
    8123: ("homeassistant", "Home Assistant"),
    8443: ("https_alt", "HTTPS alt"),
    8883: ("mqtts", "MQTT (TLS)"),
    9100: ("jetdirect", "Drucker (JetDirect)"),
}


def classify(port: int, nmap_name: str | None = None) -> dict:
    """Return the inventory entry for an open TCP port."""
    if port in KNOWN_SERVICES:
        sid, label = KNOWN_SERVICES[port]
        return {"id": sid, "port": port, "label": label, "enabled": True}
    if nmap_name and nmap_name not in ("unknown", "tcpwrapped"):
        sid = sanitize(f"{nmap_name}_{port}", fallback_prefix="svc")
        label = nmap_name
    else:
        sid, label = f"port_{port}", "Unbekannt"
    return {"id": sid, "port": port, "label": label, "enabled": False}
