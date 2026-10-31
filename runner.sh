#!/bin/bash
set -e

# Configuration
NETWORK_RANGE=${1:-"192.168.0.0/24"}

echo "=== Step 1: Discovering Network & Generating Things ==="
python3 discover_things.py "$NETWORK_RANGE"

echo "=== Step 2: Generating Items from Things ==="
python3 generate_items.py

echo "=== Step 3: Generating Sitemap ==="
python3 generate_sitemap.py

echo "=== Scaffolding Complete! ==="
echo "Generated files:"
echo " - network.things"
echo " - network.items"
echo " - network_monitoring.sitemap"
echo "Copy these files into your openHAB configuration directories (e.g., /etc/openhab/things/, items/, sitemaps/)."