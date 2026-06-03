__plugin_name__ = "Offline Measurements"
__plugin_summary__ = "Web page at /offline for entering manual lab measurements; publishes via MQTT for mqtt_to_db_streaming to persist."
__plugin_version__ = "0.1.0"
__plugin_author__ = "Noah Sprent"
__plugin_homepage__ = "https://github.com/Change-Bio/pioreactor-offline-measurements"

from . import parsers  # noqa: F401  (import-time side effect: registers MQTT->DB parsers)
