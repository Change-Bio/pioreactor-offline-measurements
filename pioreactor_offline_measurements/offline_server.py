"""HTTP server for the /offline form. Reads schema RO from SQLite; writes
go through MQTT so mqtt_to_db_streaming can persist.

Run with: python -m pioreactor_offline_measurements.offline_server
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pioreactor.config import config
from pioreactor.pubsub import publish
from pioreactor.whoami import get_unit_name

STATIC_DIR = Path(__file__).parent / "static"
PORT = int(config.get("offline_measurements", "server_port", fallback="8191"))
DB_PATH = config.get("storage", "database")

TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _allowed_tables() -> list[str]:
    raw = config.get("offline_measurements", "allowed_tables", fallback="")
    return [t.strip() for t in raw.split(",") if t.strip()]


def _ro_connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5.0)


def _table_info(table: str) -> list[dict]:
    if not TABLE_NAME_RE.match(table):
        raise ValueError(f"bad table name: {table!r}")
    with _ro_connect() as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [
        {"name": r[1], "type": r[2], "notnull": r[3], "dflt_value": r[4], "pk": r[5]}
        for r in rows
    ]


def _experiments() -> list[str]:
    with _ro_connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT experiment FROM experiments ORDER BY created_at DESC"
        ).fetchall()]


def _coerce(value, sql_type: str):
    t = (sql_type or "").upper()
    if value is None or value == "":
        return None
    if "INT" in t:
        return int(value)
    if any(k in t for k in ("REAL", "FLOAT", "DOUB", "NUMERIC", "DECIMAL")):
        return float(value)
    if "TIMESTAMP" in t or "DATETIME" in t or "DATE" in t:
        s = str(value)
        # accept trailing Z
        s = s[:-1] + "+00:00" if s.endswith("Z") else s
        datetime.fromisoformat(s)  # validation only
        return s
    return str(value)


def _build_row(table: str, raw_values: dict) -> dict:
    cols = _table_info(table)
    if not cols:
        raise ValueError(f"unknown table {table!r}")
    col_by_name = {c["name"]: c for c in cols}
    row: dict = {}
    errors: list[str] = []

    # type-coerce provided values
    for name, val in raw_values.items():
        if name not in col_by_name:
            continue  # forgiving: drop unknown keys
        try:
            coerced = _coerce(val, col_by_name[name]["type"])
        except (ValueError, TypeError) as e:
            errors.append(f"column {name}: {e}")
            continue
        if coerced is not None:
            row[name] = coerced

    # inject defaults
    if "timestamp" in col_by_name and "timestamp" not in row:
        row["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if "pioreactor_unit" in col_by_name and "pioreactor_unit" not in row:
        row["pioreactor_unit"] = get_unit_name()

    # OD channel-4 / 180-deg convention (matches the manual-entry KB note)
    if table == "od_readings":
        row.setdefault("angle", 180)
        row.setdefault("channel", 4)

    # required-cols check (skip pk, defaulted, and topic-derived experiment)
    for c in cols:
        if c["pk"]:
            continue
        if not c["notnull"] or c["dflt_value"] is not None:
            continue
        if c["name"] == "experiment":
            continue  # mqtt parser injects from topic
        if c["name"] not in row:
            errors.append(f"column {c['name']}: required")

    if errors:
        raise ValueError("; ".join(errors))

    return row


def _publish_row(table: str, experiment: str, unit: str, row: dict) -> None:
    # row must NOT contain experiment/unit -- the parser injects them from topic.
    payload = {k: v for k, v in row.items() if k not in ("experiment", "pioreactor_unit")}
    topic = f"pioreactor/{unit}/{experiment}/offline_measurements/{table}"
    publish(topic, json.dumps(payload), qos=2, retain=False)


def _publish_log(table: str, experiment: str, unit: str, row: dict) -> None:
    log = {
        "timestamp": row.get("timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
        "message": f"Manual entry into {table}: {json.dumps({k: v for k, v in row.items() if k not in ('experiment','pioreactor_unit','timestamp')})}",
        "task": "offline_measurements",
        "level": "INFO",
        "source": "ui",
    }
    topic = f"pioreactor/{unit}/{experiment}/logs/offline_measurements"
    publish(topic, json.dumps(log), qos=1, retain=False)


class OfflineHandler(SimpleHTTPRequestHandler):
    server_version = "OfflineMeasurements/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/tables":
            return self._json_response(_allowed_tables())

        if path == "/api/experiments":
            try:
                return self._json_response(_experiments())
            except sqlite3.Error as e:
                return self._json_response({"error": str(e)}, status=500)

        if path == "/api/schema":
            qs = parse_qs(parsed.query)
            table = qs.get("table", [""])[0]
            if table not in _allowed_tables():
                return self._json_response({"error": "table not allowed"}, status=400)
            try:
                return self._json_response(_table_info(table))
            except (ValueError, sqlite3.Error) as e:
                return self._json_response({"error": str(e)}, status=400)

        # static files
        if path == "/":
            path = "/index.html"
        static_path = STATIC_DIR / path.lstrip("/")
        if static_path.is_file() and STATIC_DIR.resolve() in static_path.resolve().parents:
            return self._serve_file(static_path)

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/api/insert":
            return self.send_error(HTTPStatus.NOT_FOUND)

        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as e:
            return self._json_response({"error": f"bad json: {e}"}, status=400)

        table = body.get("table")
        values = body.get("values") or {}
        if table not in _allowed_tables():
            return self._json_response({"error": "table not allowed"}, status=400)
        experiment = values.get("experiment")
        if not experiment:
            return self._json_response({"error": "experiment required"}, status=400)

        try:
            row = _build_row(table, values)
        except ValueError as e:
            return self._json_response({"error": str(e)}, status=400)

        unit = row.get("pioreactor_unit") or get_unit_name()

        try:
            _publish_row(table, experiment, unit, row)
            _publish_log(table, experiment, unit, row)
        except Exception as e:
            return self._json_response({"error": f"publish failed: {e}"}, status=502)

        return self._json_response({"ok": True, "table": table, "row": row})

    # helpers (mirrors camera_server.py)

    def _serve_file(self, path: Path) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", self._guess_type(path))
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def _json_response(self, data, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _guess_type(self, path: Path) -> str:
        return {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }.get(path.suffix.lower(), "application/octet-stream")

    def log_message(self, format, *args):  # silence default access logging
        return


def main() -> None:
    server = HTTPServer(("0.0.0.0", PORT), OfflineHandler)
    print(f"Offline measurements server listening on :{PORT}, db={DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
