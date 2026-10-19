import sqlite3
from datetime import datetime, timezone

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    model_code TEXT NOT NULL UNIQUE,
    serial_prefix TEXT NOT NULL DEFAULT '',
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assembly_worker (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machine_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL REFERENCES model_master(id),
    display_no TEXT NOT NULL,
    number_prefix TEXT,
    number_value INTEGER,
    number_width INTEGER,
    number_semantics TEXT NOT NULL DEFAULT 'unknown' CHECK(number_semantics IN ('unknown','asset','serial')),
    is_active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(model_id, display_no)
);

CREATE TABLE IF NOT EXISTS production_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL UNIQUE,
    batch_no TEXT NOT NULL UNIQUE,
    selection_mode TEXT NOT NULL,
    work_order_no TEXT,
    product_lot_no TEXT,
    process_name TEXT,
    operator_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    cancelled_at TEXT,
    cancelled_by TEXT
);

CREATE TABLE IF NOT EXISTS job_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_run_id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES production_batch(batch_id),
    model_id INTEGER NOT NULL REFERENCES model_master(id),
    machine_id INTEGER REFERENCES machine_master(id),
    product_serial TEXT,
    manufacturing_year INTEGER,
    model_name_snapshot TEXT NOT NULL,
    model_code_snapshot TEXT NOT NULL,
    machine_no_snapshot TEXT NOT NULL,
    number_semantics_snapshot TEXT NOT NULL DEFAULT 'unknown',
    work_order_no TEXT,
    product_lot_no TEXT,
    process_name TEXT,
    planned_qty INTEGER CHECK(planned_qty > 0),
    actual_qty INTEGER,
    status TEXT NOT NULL DEFAULT 'created' CHECK(status IN ('created','started','finished','cancelled')),
    started_at TEXT,
    finished_at TEXT,
    operator_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS barcode_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_run_id TEXT REFERENCES job_run(job_run_id),
    batch_id TEXT REFERENCES production_batch(batch_id),
    barcode_scope TEXT NOT NULL DEFAULT 'job_run' CHECK(barcode_scope IN ('job_run','batch')),
    barcode_type TEXT NOT NULL CHECK(barcode_type IN ('START','FINISH')),
    payload TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE(job_run_id, barcode_type),
    UNIQUE(batch_id, barcode_type)
);

CREATE TABLE IF NOT EXISTS scan_event (
    event_id TEXT PRIMARY KEY,
    payload TEXT,
    barcode_type TEXT,
    job_run_id TEXT,
    result TEXT NOT NULL,
    message TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    operator_name TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details TEXT,
    operator_name TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_run_status ON job_run(status);
CREATE INDEX IF NOT EXISTS idx_job_run_created_at ON job_run(created_at);
CREATE INDEX IF NOT EXISTS idx_job_run_model ON job_run(model_code_snapshot);
CREATE INDEX IF NOT EXISTS idx_job_run_machine ON job_run(machine_no_snapshot);
CREATE INDEX IF NOT EXISTS idx_scan_event_time ON scan_event(scanned_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_time ON audit_log(created_at);
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    needs_batch_mode_migration = db.execute("SELECT 1 FROM schema_migrations WHERE version=2").fetchone() is None
    columns = {row["name"] for row in db.execute("PRAGMA table_info(barcode_record)").fetchall()}
    if "batch_id" not in columns:
        db.execute("ALTER TABLE barcode_record RENAME TO barcode_record_v1")
        db.execute("""
            CREATE TABLE barcode_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_run_id TEXT REFERENCES job_run(job_run_id),
                batch_id TEXT REFERENCES production_batch(batch_id),
                barcode_scope TEXT NOT NULL DEFAULT 'job_run' CHECK(barcode_scope IN ('job_run','batch')),
                barcode_type TEXT NOT NULL CHECK(barcode_type IN ('START','FINISH')),
                payload TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                UNIQUE(job_run_id, barcode_type),
                UNIQUE(batch_id, barcode_type)
            )
        """)
        db.execute("INSERT INTO barcode_record(id,job_run_id,barcode_type,payload,created_at) SELECT id,job_run_id,barcode_type,payload,created_at FROM barcode_record_v1")
        db.execute("DROP TABLE barcode_record_v1")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_barcode_batch_type ON barcode_record(batch_id, barcode_type)")
    db.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)", (1, utc_now()))
    db.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)", (2, utc_now()))
    db.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)", (4, utc_now()))
    migrate_product_serials(db)
    if needs_batch_mode_migration:
        db.execute("UPDATE app_settings SET value='batch', updated_at=? WHERE key='batch_scan_mode'", (utc_now(),))
    db.execute(
        "INSERT OR IGNORE INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)",
        ("number_semantics", "unknown", utc_now()),
    )
    db.execute(
        "INSERT OR IGNORE INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)",
        ("batch_scan_mode", "batch", utc_now()),
    )
    db.commit()


def migrate_product_serials(db):
    if db.execute("SELECT 1 FROM schema_migrations WHERE version=3").fetchone():
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_job_run_product_serial ON job_run(product_serial) WHERE product_serial IS NOT NULL")
        return

    model_columns = {row["name"] for row in db.execute("PRAGMA table_info(model_master)")}
    if "serial_prefix" not in model_columns:
        db.execute("ALTER TABLE model_master ADD COLUMN serial_prefix TEXT NOT NULL DEFAULT ''")
    prefixes = {"HR255": "E", "RC255": "ER", "AR210": "C", "AR170": "B", "RC210": "CR"}
    for model in db.execute("SELECT id,model_name,model_code FROM model_master").fetchall():
        keys = ["".join(ch for ch in value.upper() if ch.isalnum()) for value in (model["model_code"], model["model_name"]) if value]
        prefix = next((prefixes[key] for key in keys if key in prefixes), None)
        if prefix:
            db.execute("UPDATE model_master SET serial_prefix=? WHERE id=? AND serial_prefix=''", (prefix, model["id"]))

    job_columns = {row["name"] for row in db.execute("PRAGMA table_info(job_run)")}
    machine_id_required = next((row["notnull"] for row in db.execute("PRAGMA table_info(job_run)") if row["name"] == "machine_id"), 0)
    if "product_serial" not in job_columns or "manufacturing_year" not in job_columns or machine_id_required:
        db.commit()
        db.execute("PRAGMA foreign_keys=OFF")
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""
                CREATE TABLE job_run_v3 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_run_id TEXT NOT NULL UNIQUE,
                    batch_id TEXT NOT NULL REFERENCES production_batch(batch_id),
                    model_id INTEGER NOT NULL REFERENCES model_master(id),
                    machine_id INTEGER REFERENCES machine_master(id),
                    product_serial TEXT,
                    manufacturing_year INTEGER,
                    model_name_snapshot TEXT NOT NULL,
                    model_code_snapshot TEXT NOT NULL,
                    machine_no_snapshot TEXT NOT NULL,
                    number_semantics_snapshot TEXT NOT NULL DEFAULT 'unknown',
                    work_order_no TEXT,
                    product_lot_no TEXT,
                    process_name TEXT,
                    planned_qty INTEGER CHECK(planned_qty > 0),
                    actual_qty INTEGER,
                    status TEXT NOT NULL DEFAULT 'created' CHECK(status IN ('created','started','finished','cancelled')),
                    started_at TEXT,
                    finished_at TEXT,
                    operator_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            new_columns = ",".join(name for name in ("id", "job_run_id", "batch_id", "model_id", "machine_id", "product_serial", "manufacturing_year", "model_name_snapshot", "model_code_snapshot", "machine_no_snapshot", "number_semantics_snapshot", "work_order_no", "product_lot_no", "process_name", "planned_qty", "actual_qty", "status", "started_at", "finished_at", "operator_name", "created_at", "updated_at") if name in job_columns or name in {"product_serial", "manufacturing_year"})
            select_columns = ",".join(name if name in job_columns else "NULL" for name in new_columns.split(","))
            db.execute(f"INSERT INTO job_run_v3({new_columns}) SELECT {select_columns} FROM job_run")
            db.execute("DROP TABLE job_run")
            db.execute("ALTER TABLE job_run_v3 RENAME TO job_run")
            db.execute("CREATE INDEX idx_job_run_status ON job_run(status)")
            db.execute("CREATE INDEX idx_job_run_created_at ON job_run(created_at)")
            db.execute("CREATE INDEX idx_job_run_model ON job_run(model_code_snapshot)")
            db.execute("CREATE INDEX idx_job_run_machine ON job_run(machine_no_snapshot)")
            db.execute("CREATE UNIQUE INDEX uq_job_run_product_serial ON job_run(product_serial) WHERE product_serial IS NOT NULL")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.execute("PRAGMA foreign_keys=ON")
    db.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(3,?)", (utc_now(),))
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_job_run_product_serial ON job_run(product_serial) WHERE product_serial IS NOT NULL")

