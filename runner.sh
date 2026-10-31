#!/usr/bin/env bash
# Komfort-Wrapper: venv anlegen (einmalig) und kompletten Lauf starten.
#   ./runner.sh 192.168.1.0/24 [weitere scaffold.py-run-Optionen]
set -euo pipefail
cd "$(dirname "$0")"

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <netz/cidr> [Optionen]   (z. B. $0 192.168.1.0/24 --chart-service rrd4j)" >&2
    exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/python scaffold.py run "$@"
