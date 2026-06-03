# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="pioreactor-offline-measurements",
    version="0.1.0",
    license_files=("LICENSE.txt",),
    description="Web UI at /offline for entering manual/offline lab measurements; publishes via MQTT so mqtt_to_db_streaming persists them.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Noah Sprent",
    author_email="noah@changebio.uk",
    url="https://github.com/Change-Bio/pioreactor-offline-measurements",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "pioreactor_offline_measurements": [
            "additional_config.ini",
            "additional_sql.sql",
            "LEADER_ONLY",
            "post_install.sh",
            "pre_uninstall.sh",
            "static/*",
            "static/**/*",
        ],
    },
    install_requires=[],
    entry_points={
        "pioreactor.plugins": "pioreactor_offline_measurements = pioreactor_offline_measurements"
    },
)
