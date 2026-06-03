#!/bin/bash
set -euo pipefail

sudo systemctl stop pioreactor-offline-server.service 2>/dev/null || true
sudo systemctl disable pioreactor-offline-server.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/pioreactor-offline-server.service
sudo systemctl daemon-reload

sudo rm -f /etc/lighttpd/conf-enabled/53-offline.conf
sudo systemctl reload lighttpd || sudo systemctl restart lighttpd

if command -v pio >/dev/null 2>&1; then
  pio kill mqtt_to_db_streaming || true
  pio run mqtt_to_db_streaming || true
fi
