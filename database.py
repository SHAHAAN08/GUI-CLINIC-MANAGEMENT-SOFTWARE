"""Database helper (the module your auth.py / clinic.py import).
Reads connection settings from config.json and creates the schema from main.sql if missing.
"""
import json
import os

import mysql.connector

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for key in ("host", "user", "password"):
            cfg[key]
    except (OSError, ValueError, KeyError) as e:
        raise RuntimeError(f"Could not read config.json ({e}). It needs: host, user, password, database.")
    cfg.setdefault("database", "CLINIC")
    return cfg


def _args(cfg):
    args = {k: cfg[k] for k in ("host", "user", "password")}
    if "port" in cfg:
        args["port"] = int(cfg["port"])
    return args


def get_connection():
    cfg = load_config()
    return mysql.connector.connect(database=cfg["database"], **_args(cfg))


DDL = [
    """CREATE TABLE IF NOT EXISTS users (
        user_id INT AUTO_INCREMENT PRIMARY KEY,
        clinic_name VARCHAR(150) NOT NULL,
        username VARCHAR(100) NOT NULL UNIQUE,
        email VARCHAR(150) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS doctors (
        doctor_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        name VARCHAR(100) NOT NULL,
        phone VARCHAR(20),
        gender VARCHAR(10),
        specialization VARCHAR(100) NOT NULL,
        fees DECIMAL(10,2) NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS patients (
        patient_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        name VARCHAR(100) NOT NULL,
        phone VARCHAR(20),
        age INT,
        concern VARCHAR(100) NOT NULL,
        doctor_id INT NOT NULL,
        fees DECIMAL(10,2) NOT NULL DEFAULT 0.00,
        regtimestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
    )""",
]


def ensure_schema():
    """Create the database and tables (same as main.sql) if they don't exist yet."""
    cfg = load_config()
    name = cfg["database"]

    boot = mysql.connector.connect(**_args(cfg))
    boot.cursor().execute(f"CREATE DATABASE IF NOT EXISTS `{name}`")
    boot.close()

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=%s AND UPPER(TABLE_NAME)='PATIENTS'", (name,))
        cols = {c[0].lower() for c in cur.fetchall()}
        if cols and "user_id" not in cols:
            raise RuntimeError(
                f"The database '{name}' still has the OLD single-clinic PATIENTS table.\n\n"
                "Either change \"database\" in config.json to a new name (e.g. CLINIC_MULTI), "
                "or run  DROP TABLE PATIENTS;  in MySQL, then start the app again.")
        for ddl in DDL:
            cur.execute(ddl)
        conn.commit()
    finally:
        cur.close()
        conn.close()
