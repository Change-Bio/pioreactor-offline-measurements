#!/bin/bash
set -euo pipefail

systemctl stop pioreactor-offline-server.service 2>/dev/null || true
systemctl disable pioreactor-offline-server.service 2>/dev/null || true
rm -f /etc/systemd/system/pioreactor-offline-server.service
systemctl daemon-reload

rm -f /etc/lighttpd/conf-enabled/53-offline.conf
systemctl reload lighttpd || systemctl restart lighttpd

if command -v pio >/dev/null 2>&1; then
  pio kill mqtt_to_db_streaming || true
  pio run mqtt_to_db_streaming || true
fi
