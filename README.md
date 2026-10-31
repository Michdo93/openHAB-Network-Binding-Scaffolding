# openHAB Network Binding Scaffolding

Discovers hosts and open TCP services with `nmap` and generates ready-to-use
openHAB **Things**, **Items** and a **Sitemap** for the
[Network Binding](https://www.openhab.org/addons/bindings/network/) (openHAB 4/5).

```
nmap ──► inventory.yaml ──► Jinja2 templates ──► out/network.things
          (editable)                               out/network.items
                                                   out/network.sitemap ──► validation
```

## Requirements

* Python ≥ 3.9 with `Jinja2` and `PyYAML` (`pip install -r requirements.txt`; `runner.sh` creates a venv automatically)
* `nmap`
* optional: `iproute2` (`ip neigh`) or `net-tools` (`arp`) to fill in MAC addresses when nmap runs unprivileged

Run as root (or with `sudo`) to get MAC addresses and vendors directly from nmap.
MAC addresses end up as `macAddress` on the ping Things, enabling the binding's Wake-on-LAN actions.

## Quick start

```bash
chmod +x runner.sh   # once
./runner.sh 192.168.1.0/24
# with speedtest and persistence-backed charts
./runner.sh 192.168.1.0/24 --speedtest-url https://bouygues.testdebit.info/ --speedtest-file 10M.iso --chart-service rrd4j
```

Then copy `out/network.things`, `out/network.items` and `out/network.sitemap`
to `$OPENHAB_CONF/things/`, `items/` and `sitemaps/`.

## Workflow

```bash
python3 scaffold.py discover 192.168.1.0/24      # scan, create/merge inventory.yaml
$EDITOR inventory.yaml                           # rename, enable/disable devices & services
python3 scaffold.py render                       # generate + validate
```

* **Known services** (SSH, HTTP(S), MQTT, SMB, RDP, Proxmox, Home Assistant, …, see `ohnet/services.py`)
  are enabled; every other open port is added with `enabled: false` and shows up as a
  `// REVIEW` comment in the `.things` file.
* **Re-running `discover` merges**: devices are matched by MAC (then IP), manual edits
  (`id`, `label`, `location`, `enabled`, `address`) are kept, IP changes are followed,
  and devices that are offline during the scan are not removed.
* `address` is what the Thing pings. It defaults to the IP; set a DNS name for DHCP clients.

### Options

| Option | Default | Meaning |
|---|---|---|
| `--ports` | `top:1000` | `top:N` (nmap top N **plus** all known service ports, e.g. 1883, 8123, 8006), `all`, or `22,80,8000-8100` |
| `-sV`, `--service-detection` | off | nmap version detection → better names for unknown ports (slower) |
| `--exclude` | – | hosts to skip |
| `--timing` | `4` | nmap `-T` |
| `--speedtest-url`, `--speedtest-file` | – | enables the speedtest Thing (both are mandatory for the binding) |
| `--item-prefix` | `Net_` | prefix for all generated item names |
| `--chart-service` | default persistence | e.g. `rrd4j`, `influxdb` |
| `--no-charts` | – | omit `Chart` elements |
| `--templates DIR` | – | directory with your own `*.j2` templates (see below) |
| `-i`, `-o` | `inventory.yaml`, `out/` | inventory file / output directory |

Render options are persisted into the `settings:` block of the inventory.

## Generated model

Per device:

| Item | Type | Channel | Semantic tags |
|---|---|---|---|
| `Net_<id>` | Group | – | `NetworkAppliance` |
| `Net_<id>_Online` | Switch | `pingdevice:online` | `Status` |
| `Net_<id>_Latency` | Number:Time | `pingdevice:latency` | `Measurement`, `Duration` |
| `Net_<id>_LastSeen` | DateTime | `pingdevice:lastseen` | `Status`, `Timestamp` |
| `Net_<id>_<svc>_Online` / `_Latency` | Switch / Number:Time | `servicedevice:online` / `latency` | as above |

`Net_gOnline` (`Group:Switch:OR(ON,OFF)`) shows the number of online devices.
The speedtest uses the binding channels `isRunning`, `progress`, `rateDown`, `rateUp`, `testStart`, `testEnd`.

## Custom templates

Templates live in `ohnet/templates/`. Copy one of them to your own directory,
change it, and pass `--templates DIR`; templates you don't override fall back to the
built-in ones. Available context: `settings`, `devices` (with `item`, `services`,
`review`), `speedtest`, `generated`, filter `q` (quoted/escaped openHAB string).

## Validation & tests

`scaffold.py render` validates the output statically: channel IDs and item types against the
Network Binding spec, required Thing parameters, unknown parameters, undefined groups/items in
items and sitemap, duplicates and brace balance. Run it standalone with `scaffold.py validate`.

```bash
pip install pytest
pytest
# additionally check the embedded spec against the binding's thing-types.xml
OHNET_THING_TYPES=/path/to/thing-types.xml pytest
```
