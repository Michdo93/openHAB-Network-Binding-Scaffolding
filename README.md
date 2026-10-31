# openHAB Network Binding Scaffolding

This repository provides automated scaffolding scripts to discover network hosts and services using `nmap`, `nc`, `ping`, and `arp`, and automatically generate corresponding openHAB **Things**, **Items**, and **Sitemaps** for the **Network Binding**.

## Requirements

Ensure the following tools are installed on your management or openHAB host:

* Python 3
* `nmap`
* `netcat` (`nc`)
* `arp`

## Pipeline Scripts

1. **`discover_things.py`**: Scans the provided IP range, performs ping & arp checks, resolves hostnames (sanitizing them to `_`), scans open ports, classifies services, and outputs `network.things` (commenting out unrecognized ports for manual review).
2. **`generate_items.py`**: Reads `network.things`, creates a Group Item per device (`g_<device>`), and automatically maps all channels (`online`, `latency`, `lastseen`, `open`, `time`) as well as local speedtest channels.
3. **`generate_sitemap.py`**: Builds an interactive sitemap (`network_monitoring.sitemap`) incorporating device frames and the requested Speedtest Charts and controls.
4. **`run_all.sh`**: Master wrapper script executing the entire workflow sequentially.

## Usage

Run the master script with your target network range:

```
chmod +x runner.sh
./runner.sh 192.168.1.0/24
```

After completion, copy the generated `.things`, `.items`, and `.sitemap` files directly into your openHAB configuration directories.
