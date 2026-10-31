"""Static checks for generated .things/.items/.sitemap files.

Not a full Xtext parser, but catches what actually broke v1: wrong channel
IDs, wrong item types, missing required Thing parameters, dangling item or
group references, duplicate names and unbalanced braces.
"""

from __future__ import annotations

import re
from pathlib import Path

# Extracted from org.openhab.binding.network OH-INF/thing/thing-types.xml
# (checked against it by tests/test_spec.py).
SPEC: dict[str, dict] = {
    "pingdevice": {
        "channels": {"online": "Switch", "latency": "Number:Time", "lastseen": "DateTime"},
        "required": {"hostname"},
        "params": {"hostname", "macAddress", "refreshInterval", "retry", "timeout",
                   "networkInterfaceNames", "useIOSWakeUp", "useArpPing", "useIcmpPing"},
    },
    "servicedevice": {
        "channels": {"online": "Switch", "latency": "Number:Time", "lastseen": "DateTime"},
        "required": {"hostname", "port"},
        "params": {"hostname", "port", "macAddress", "retry", "timeout", "refreshInterval",
                   "networkInterfaceNames"},
    },
    "httpdevice": {
        "channels": {"online": "Switch", "httpStatus": "Number", "latency": "Number:Time",
                     "lastseen": "DateTime"},
        "required": {"url"},
        "params": {"url", "treatRedirectAsError", "treatClientErrorAsError", "retry", "timeout",
                   "refreshInterval"},
    },
    "speedtest": {
        "channels": {"isRunning": "Switch", "progress": "Number:Dimensionless",
                     "rateUp": "Number:DataTransferRate", "rateDown": "Number:DataTransferRate",
                     "testStart": "DateTime", "testEnd": "DateTime"},
        "required": {"url", "fileName"},
        "params": {"refreshInterval", "initialDelay", "uploadSize", "url", "fileName", "maxTimeout"},
    },
}

_THING = re.compile(r'^\s*Thing\s+network:(\w+):([\w-]+)\s+(?:"(?:[^"\\]|\\.)*"\s+)?(?:@\s*"(?:[^"\\]|\\.)*"\s+)?\[(.*)\]\s*$')
_PARAM = re.compile(r'(\w+)\s*=')
_ITEM = re.compile(r'^\s*(Group(?::[\w:]+(?:\([^)]*\))?)?|Switch|Number(?::\w+)?|DateTime|String|Contact|Dimmer)\s+(\w+)\b(.*)$')
_GROUPS = re.compile(r'\(([\w\s,]+)\)\s*(?:\[|\{|$)')
_CHANNEL = re.compile(r'channel="network:(\w+):([\w-]+):(\w+)"')
_ITEMREF = re.compile(r'\bitem=(\w+)')
_VISREF = re.compile(r'(?:visibility|valuecolor|labelcolor|iconcolor)=\[([^\]]*)\]')


def _strip_strings(line: str) -> str:
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)


def _code_lines(text: str):
    for no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s and not s.startswith("//"):
            yield no, line


def validate(things: str, items: str, sitemap: str) -> list[str]:
    errors: list[str] = []

    # --- things
    uids: dict[str, str] = {}
    for no, line in _code_lines(things):
        m = _THING.match(line)
        if not m:
            errors.append(f"things:{no}: nicht erkannte Thing-Definition: {line.strip()}")
            continue
        ttype, tid, params = m.groups()
        if ttype not in SPEC:
            errors.append(f"things:{no}: unbekannter Thing-Typ network:{ttype}")
            continue
        if tid in uids:
            errors.append(f"things:{no}: doppelte Thing-UID {tid}")
        uids[tid] = ttype
        given = set(_PARAM.findall(_strip_strings(params)))
        for p in sorted(SPEC[ttype]["required"] - given):
            errors.append(f"things:{no}: Pflichtparameter '{p}' fehlt (network:{ttype}:{tid})")
        for p in sorted(given - SPEC[ttype]["params"]):
            errors.append(f"things:{no}: unbekannter Parameter '{p}' für network:{ttype}")

    # --- items
    names: dict[str, str] = {}
    group_refs: list[tuple[int, str]] = []
    for no, line in _code_lines(items):
        m = _ITEM.match(line)
        if not m:
            errors.append(f"items:{no}: nicht erkannte Item-Definition: {line.strip()}")
            continue
        itype, name, rest = m.groups()
        if name in names:
            errors.append(f"items:{no}: doppelter Item-Name {name}")
        names[name] = itype
        rest_ns = _strip_strings(rest)
        g = _GROUPS.search(rest_ns.split("{")[0])
        if g:
            group_refs += [(no, x.strip()) for x in g.group(1).split(",") if x.strip()]
        for ttype, tid, ch in _CHANNEL.findall(rest):
            if uids.get(tid) != ttype:
                errors.append(f"items:{no}: Channel verweist auf fehlendes Thing network:{ttype}:{tid}")
            expected = SPEC.get(ttype, {}).get("channels", {}).get(ch)
            if expected is None:
                errors.append(f"items:{no}: Channel '{ch}' existiert nicht für network:{ttype}")
            elif expected != itype:
                errors.append(f"items:{no}: {name} ist {itype}, Channel {ch} erwartet {expected}")
        if rest_ns.count("{") != rest_ns.count("}"):
            errors.append(f"items:{no}: unbalancierte Klammern")
    for no, g in group_refs:
        if not names.get(g, "").startswith("Group"):
            errors.append(f"items:{no}: Gruppe {g} ist nicht definiert")

    # --- sitemap
    depth = 0
    for no, line in _code_lines(sitemap):
        s = _strip_strings(line)
        depth += s.count("{") - s.count("}")
        if depth < 0:
            errors.append(f"sitemap:{no}: schließende Klammer ohne öffnende")
            depth = 0
        refs = _ITEMREF.findall(s)
        for vis in _VISREF.findall(line):
            refs += re.findall(r'(\w+)\s*(?:==|!=|>=|<=|>|<)', vis)
        for r in refs:
            if r not in names:
                errors.append(f"sitemap:{no}: Item {r} ist nicht definiert")
        if re.match(r'^\s*Frame\b', s) and "{" not in s:
            errors.append(f"sitemap:{no}: Frame ohne Block")
    if depth:
        errors.append(f"sitemap: {depth} nicht geschlossene Klammer(n)")
    if not re.match(r'^\s*sitemap\s+\w+', sitemap.lstrip()):
        errors.append("sitemap: fehlende 'sitemap <name>'-Deklaration")

    return errors


def validate_dir(out_dir: Path, sitemap_name: str) -> list[str]:
    read = lambda n: (out_dir / n).read_text(encoding="utf-8")
    return validate(read("network.things"), read("network.items"), read(f"{sitemap_name}.sitemap"))
