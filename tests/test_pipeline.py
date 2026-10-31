import copy
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ohnet import inventory
from ohnet.discovery import parse_nmap_xml, ports_args
from ohnet.naming import ip_id, sanitize, unique
from ohnet.render import render
from ohnet.validate import validate, validate_dir

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def hosts():
    return parse_nmap_xml(ET.parse(FIX / "scan.xml").getroot())


@pytest.fixture
def inv(hosts):
    inv, added, _ = inventory.merge(inventory.empty(), hosts)
    assert added == 4
    return inv


# ---------- naming ----------
@pytest.mark.parametrize("raw,expected", [
    ("My-NAS", "my_nas"), ("pi.hole", "pi_hole"), ("3dprinter", "h_3dprinter"),
    ("--weird__name!!", "weird_name"), ("", "h"),
])
def test_sanitize(raw, expected):
    assert sanitize(raw) == expected


def test_ip_id_and_unique():
    assert ip_id("192.168.1.5") == "ip_192_168_1_5"
    assert ip_id("fe80::1") == "ip_fe80_1"
    taken = {"nas"}
    assert unique("nas", taken) == "nas_2" and unique("nas", taken) == "nas_3"


def test_ports_args(tmp_path):
    assert ports_args("all") == ["-p-"]
    assert ports_args("top:200", tmp_path / "missing") == ["--top-ports", "200"]   # fallback
    svc = tmp_path / "nmap-services"
    svc.write_text("# x\nhttp\t80/tcp\t0.48\ntelnet\t23/tcp\t0.22\nfoo\t4444/tcp\t0.0001\ndomain\t53/udp\t0.9\n")
    flag, spec = ports_args("top:2", svc)
    ports = {int(x) for x in spec.removeprefix("T:").split(",")}
    assert flag == "-p" and {80, 23, 1883, 8123} <= ports and 4444 not in ports and 53 in ports  # 53 via KNOWN
    assert ports_args("22,80,8000-8100") == ["-p", "22,80,8000-8100"]
    with pytest.raises(ValueError):
        ports_args("22; rm -rf /")


def test_missing_nmap(monkeypatch):
    import ohnet.discovery as d
    monkeypatch.setattr(d.shutil, "which", lambda _: None)
    with pytest.raises(d.DiscoveryError, match="nmap"):
        d.discover(["127.0.0.1"], log=lambda *_: None)


# ---------- discovery parsing ----------
def test_parse(hosts):
    assert [h.ip for h in hosts] == ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.13"]
    nas = hosts[0]
    assert nas.mac == "aa:bb:cc:00:00:10" and nas.vendor == "Synology"
    assert [s["port"] for s in nas.services] == [22, 443, 9999]          # closed 81 ignored
    assert [s["enabled"] for s in nas.services] == [True, True, False]   # unknown -> review
    assert hosts[2].hostname is None and hosts[2].services == []


# ---------- inventory ----------
def test_ids_unique_and_no_prefix_collapse(inv):
    """v1 grouped by uid.split('_')[0] -> 'my-nas' und 'my-pc' landeten beide in g_my."""
    ids = [d["id"] for d in inv["devices"]]
    assert sorted(ids) == ["ip_192_168_1_12", "my_nas", "my_nas_2", "my_pc"]


def test_merge_keeps_manual_edits(inv, hosts):
    nas = next(d for d in inv["devices"] if d["ip"] == "192.168.1.10")
    nas["label"], nas["id"] = "Synology DS920+", "nas"
    nas["services"][2]["enabled"] = True
    offline = {"id": "printer", "label": "Drucker", "address": "drucker.lan", "ip": "192.168.1.50",
               "mac": None, "enabled": True, "services": []}
    inv["devices"].append(offline)

    hosts[0].ip = "192.168.1.20"                       # DHCP gave the NAS a new IP; MAC matches
    inv2, added, updated = inventory.merge(copy.deepcopy(inv), hosts)
    assert added == 0 and updated == 4
    nas2 = next(d for d in inv2["devices"] if d["id"] == "nas")
    assert nas2["label"] == "Synology DS920+" and nas2["ip"] == nas2["address"] == "192.168.1.20"
    assert nas2["services"][2]["enabled"] is True
    assert any(d["id"] == "printer" for d in inv2["devices"])   # offline device not dropped


def test_inventory_roundtrip(inv, tmp_path):
    p = tmp_path / "inv.yaml"
    inventory.save(inv, p)
    assert inventory.load(p)["devices"] == inv["devices"]


# ---------- rendering + validation ----------
def _render(inv, tmp_path, **settings):
    inv["settings"].update(settings)
    render(inv, tmp_path)
    return {p.name: p.read_text() for p in tmp_path.iterdir()}


def test_render_validates(inv, tmp_path):
    inv["speedtest"].update(enabled=True, url="https://example.org/", file_name="10M.iso")
    out = _render(inv, tmp_path, chart_service="rrd4j")
    assert validate_dir(tmp_path, "network") == []
    t = out["network.things"]
    assert 'macAddress="aa:bb:cc:00:00:10"' in t
    assert "network:servicedevice:my_nas_ssh" in t
    assert "// REVIEW" in t and "port=9999" not in t
    assert "refreshInterval=20" in t                 # speedtest in minutes
    i = out["network.items"]
    assert ":online\"" in i and ":open\"" not in i and ":time\"" not in i
    assert 'service="rrd4j"' in out["network.sitemap"]


def test_disabled_device_and_no_speedtest(inv, tmp_path):
    inv["devices"][0]["enabled"] = False
    out = _render(inv, tmp_path, charts=False)
    assert validate_dir(tmp_path, "network") == []
    assert inv["devices"][0]["id"] not in out["network.things"]
    assert "speedtest" not in out["network.things"] and "Chart" not in out["network.sitemap"]


def test_speedtest_requires_url(inv, tmp_path):
    inv["speedtest"]["enabled"] = True
    with pytest.raises(ValueError):
        render(inv, tmp_path)


def test_label_escaping(inv, tmp_path):
    inv["devices"][0]["label"] = 'Büro "Server" \\ 1'
    out = _render(inv, tmp_path)
    assert '"Büro \\"Server\\" \\\\ 1"' in out["network.things"]
    assert validate_dir(tmp_path, "network") == []


def test_custom_template_dir(inv, tmp_path):
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    (tpl / "network.sitemap.j2").write_text("sitemap custom label=\"X\" {\n}\n")
    render(inv, tmp_path / "out", tpl)
    assert (tmp_path / "out" / "network.sitemap").read_text().startswith("sitemap custom")
    assert "pingdevice" in (tmp_path / "out" / "network.things").read_text()   # builtin fallback


# ---------- validator catches the v1 bugs ----------
V1_THINGS = '''Thing network:pingdevice:localhost "Ping" @ "Network" [ hostname="127.0.0.1", refreshInterval=60000 ]
Thing network:servicedevice:localhost_mqtt "S" @ "Network" [ hostname="127.0.0.1", port=1883 ]
Thing network:speedtest:local "Speedtest" @ "Internet" [ refreshInterval=3600000 ]
'''
V1_ITEMS = '''Group g_localhost "Device" <computer> (Network)
Switch localhost_mqtt_open "Open [%s]" (g_localhost) { channel="network:servicedevice:localhost_mqtt:open" }
Number Speedtest_Progress "P" (gSpeedtest) { channel="network:speedtest:local:progress" }
'''
V1_SITEMAP = '''sitemap network_monitoring label="Network Monitoring"
{
    Frame label="Labor" {
        Text item=g_localhost {
            Frame label="Erkannte Dienste"
        }
    }
    Frame label="Down" {
        Chart item=Speedtest_ResultDown period=D visibility=[sys_chart_period==0]
    }
}
'''


def test_validator_flags_v1_output():
    errs = "\n".join(validate(V1_THINGS, V1_ITEMS, V1_SITEMAP))
    for needle in ["'url' fehlt", "'fileName' fehlt", "Channel 'open' existiert nicht",
                   "Gruppe Network ist nicht definiert", "Gruppe gSpeedtest ist nicht definiert",
                   "erwartet Number:Dimensionless", "Frame ohne Block",
                   "Item Speedtest_ResultDown ist nicht definiert", "Item sys_chart_period ist nicht definiert"]:
        assert needle in errs, needle
