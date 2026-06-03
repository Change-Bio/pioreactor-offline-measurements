#!/bin/bash
set -euo pipefail

# Install systemd unit for the offline-measurements HTTP server
cat > /etc/systemd/system/pioreactor-offline-server.service << 'EOF'
[Unit]
Description=Pioreactor Offline Measurements Server
After=network.target

[Service]
Type=simple
User=pioreactor
Group=www-data
ExecStart=/opt/pioreactor/venv/bin/python -m pioreactor_offline_measurements.offline_server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pioreactor-offline-server.service
systemctl restart pioreactor-offline-server.service

# Lighttpd reverse-proxy /offline -> 127.0.0.1:8191
cat > /etc/lighttpd/conf-enabled/53-offline.conf << 'LCONF'
server.modules += ("mod_proxy")

$HTTP["url"] == "/offline" {
  url.redirect = ("" => "/offline/")
}

$HTTP["url"] =~ "^/offline/" {
  proxy.server = ("" => (("host" => "127.0.0.1", "port" => 8191)))
  proxy.header = ("map-urlpath" => ("/offline/" => "/"))
}
LCONF

systemctl reload lighttpd || systemctl restart lighttpd

# Restart mqtt_to_db_streaming so it picks up the new parsers registered
# at plugin import time. Tolerate failures (e.g. job not running yet on a
# fresh leader): the next boot/start will pick them up.
if command -v pio >/dev/null 2>&1; then
  pio kill mqtt_to_db_streaming || true
  pio run mqtt_to_db_streaming || true
fi
