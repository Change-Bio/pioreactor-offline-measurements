# pioreactor-offline-measurements

A Pioreactor leader plugin that serves a small web page at
`https://<leader>/offline` for entering manual / offline lab measurements
(CDW, spectrophotometer OD, etc.) into the leader's SQLite DB.

## How it works

The plugin runs its own `http.server` on a configurable port (default 8191).
Lighttpd reverse-proxies `/offline/*` to it (a new
`/etc/lighttpd/conf-enabled/53-offline.conf` is dropped during install,
mirroring how the `pioreactor-camera` plugin exposes `/camera`).

Writes are **not** done directly to SQLite. The form POST publishes a JSON row
to `pioreactor/<unit>/<exp>/offline_measurements/<table>` over MQTT;
`mqtt_to_db_streaming` (with a generic parser registered by this plugin) does
the INSERT. An INFO-level log is also published to
`pioreactor/<unit>/<exp>/logs/offline_measurements` so the entry appears in
the UI Logs panel.

## Config

`additional_config.ini` adds a section:

```ini
[offline_measurements]
server_port=8191
allowed_tables=cdw_readings,od_readings,growth_rates,temperature_readings
```

`allowed_tables` is a comma-separated whitelist. Anything not in this list is
hidden from the form and rejected by the `/api/insert` endpoint.

## Install

On the leader, over SSH (env exports needed; see the `ssh-env-vars.md` KB
note):

```bash
ssh pioreactor@<leader> 'set -a; source /etc/pioreactor.env; set +a; \
  pip install /path/to/pioreactor-offline-measurements && \
  pio plugins install pioreactor-offline-measurements'
```

`pio plugins install` runs `post_install.sh`, which installs the systemd unit
and lighttpd snippet and restarts `mqtt_to_db_streaming` so it picks up the
new parsers.
