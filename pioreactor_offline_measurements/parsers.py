"""Registers a generic MQTT -> SQLite parser for each table in
[offline_measurements] allowed_tables. The web server (offline_server.py)
publishes JSON rows to pioreactor/<unit>/<exp>/offline_measurements/<table>;
mqtt_to_db_streaming dispatches them through the parser below and INSERTs
into <table>.

Side effect at import: `register_all()` runs unconditionally. This file is
imported by the package __init__, so any leader process that loads installed
plugins (notably mqtt_to_db_streaming) registers these mappings.
"""
from __future__ import annotations

from msgspec.json import decode as msgspec_loads

from pioreactor.background_jobs.leader.mqtt_to_db_streaming import (
    TopicToParserToTable,
    register_source_to_sink,
)
from pioreactor.config import config

TOPIC_PREFIX = "pioreactor/+/+/offline_measurements"


def _unit_and_experiment(topic: str) -> tuple[str, str]:
    parts = topic.split("/")
    return parts[1], parts[2]


def make_parser(table: str):
    def parse(topic: str, payload: bytes) -> dict:
        unit, experiment = _unit_and_experiment(topic)
        row = msgspec_loads(payload)
        # experiment/unit always come from the topic; never trust the payload here.
        row["experiment"] = experiment
        row["pioreactor_unit"] = unit
        return row

    parse.__name__ = f"parse_offline_{table}"
    return parse


def _allowed_tables() -> list[str]:
    raw = config.get("offline_measurements", "allowed_tables", fallback="")
    return [t.strip() for t in raw.split(",") if t.strip()]


def register_all() -> None:
    for table in _allowed_tables():
        register_source_to_sink(
            TopicToParserToTable(
                f"{TOPIC_PREFIX}/{table}",
                make_parser(table),
                table,
            )
        )


register_all()
