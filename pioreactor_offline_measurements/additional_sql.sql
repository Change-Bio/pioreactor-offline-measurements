CREATE TABLE IF NOT EXISTS airflow_readings (
    experiment TEXT NOT NULL,
    pioreactor_unit TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    airflow_lpm REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS airflow_readings_experiment_idx
    ON airflow_readings (experiment, timestamp);
