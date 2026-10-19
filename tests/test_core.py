import sqlite3

import pytest

from app import create_app as build_app
from app.db import get_db
from app.services import backup_database, create_assembly_worker, create_batch, create_machine_range, create_model, ensure_barcodes, format_duration, get_job, machine_ids_from_numbers, parse_payload, restore_database, scan, set_setting, status_label, verify_sqlite_backup


def setup_data(app):
    with app.app_context():
        model_id = create_model("HR-255", "HR255")
        machine_ids = create_machine_range(model_id, "E", 1, 10, 2, "unknown")
        return model_id, machine_ids


def test_machine_range_and_unknown_semantics(app):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        rows = get_db().execute("SELECT display_no,number_semantics FROM machine_master ORDER BY number_value").fetchall()
        assert len(machine_ids) == 10
        assert [r["display_no"] for r in rows] == [f"E-{i:02d}" for i in range(1, 11)]
        assert {r["number_semantics"] for r in rows} == {"unknown"}


def test_machine_range_validates_semantics(app):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        with pytest.raises(ValueError, match="編號語意必須是 unknown、asset 或 serial"):
            create_machine_range(model_id, "X", 1, 1, 2, "future")

        assert get_db().execute("SELECT COUNT(*) AS count FROM job_run").fetchone()["count"] == 0


def test_manual_machine_numbers_validate_selection_and_reject_invalid_values(app):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        assert machine_ids_from_numbers(model_id, " 01, 03, 06 ") == [machine_ids[0], machine_ids[2], machine_ids[5]]
        for invalid in ("01,01", "01,99", "01,,02", "E-01"):
            with pytest.raises(ValueError):
                machine_ids_from_numbers(model_id, invalid)
        assert get_db().execute("SELECT COUNT(*) AS count FROM production_batch").fetchone()["count"] == 0


def test_manual_machine_numbers_reject_other_model_and_inactive_machines(app):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        other_model = create_model("FAR-210", "FAR210")
        other_machine = create_machine_range(other_model, "F", 1, 1, 2)[0]
        get_db().execute("UPDATE machine_master SET is_active=0 WHERE id=?", (machine_ids[1],))
        get_db().commit()
        for number in ("F-01", "E-02"):
            with pytest.raises(ValueError, match="機台不存在、未啟用或不屬於所選機型"):
                machine_ids_from_numbers(model_id, number)
        assert other_machine


def test_job_create_manual_selection_creates_expected_batch(client, app):
    model_id, _ = setup_data(app)
    with app.app_context():
        create_assembly_worker("operator")
    form = client.get(f"/jobs/new?model_id={model_id}")
    assert form.status_code == 200
    form_text = form.get_data(as_text=True)
    assert "起始流水號" in form_text
    assert "本批台數" in form_text
    for removed in ("工單號", "產品批號", "製程", "計畫數量", "機台數字"):
        assert removed not in form_text
    response = client.post("/jobs", data={
        "model_id": str(model_id),
        "manufacturing_year": "2026",
        "starting_number": "10",
        "product_count": "10",
        "operator_name": "operator",
    })
    assert response.status_code == 302
    with app.app_context():
        jobs = get_db().execute("SELECT product_serial,machine_id,planned_qty,manufacturing_year FROM job_run ORDER BY id").fetchall()
        assert [row["product_serial"] for row in jobs] == [f"E27-{i}" for i in range(10, 20)]
        assert all(row["machine_id"] is None and row["planned_qty"] is None and row["manufacturing_year"] == 2026 for row in jobs)


def test_job_create_invalid_manual_selection_does_not_create_partial_batch(client, app):
    model_id, _ = setup_data(app)
    response = client.post("/jobs", data={
        "model_id": str(model_id),
        "manufacturing_year": "2026",
        "starting_number": "1",
        "product_count": "0",
        "operator_name": "operator",
    })
    assert response.status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM production_batch").fetchone()[0] == 0
        assert get_db().execute("SELECT COUNT(*) FROM job_run").fetchone()[0] == 0


def test_product_serial_duplicate_is_rejected_without_partial_batch(app):
    model_id, _ = setup_data(app)
    with app.app_context():
        create_batch(model_id, 2026, 10, 2, "operator")
        with pytest.raises(ValueError, match="製號已存在"):
            create_batch(model_id, 2026, 11, 2, "operator")
        assert get_db().execute("SELECT COUNT(*) FROM production_batch").fetchone()[0] == 1
        assert get_db().execute("SELECT COUNT(*) FROM job_run").fetchone()[0] == 2


def test_model_prefix_mapping_and_year_marker(app):
    with app.app_context():
        examples = (("HR-255", "HR255", "E"), ("RC-255", "RC255", "ER"), ("AR-210", "AR210", "C"), ("RC-210", "RC210", "CR"))
        for name, code, prefix in examples:
            model_id = create_model(name, code)
            batch_id, _ = create_batch(model_id, 2026, 1, 1, "operator")
            assert get_db().execute("SELECT product_serial FROM job_run WHERE batch_id=?", (batch_id,)).fetchone()[0] == f"{prefix}27-01"


def test_report_filter_print_and_export_use_product_serial(client, app, tmp_path):
    from app.services import export_xlsx, query_report
    from openpyxl import load_workbook

    model_id, _ = setup_data(app)
    with app.app_context():
        batch_id, _ = create_batch(model_id, 2026, 10, 2, "operator")
        ensure_barcodes(batch_id)
        rows = query_report({"machine_no": "E27-11"})
        assert len(rows) == 1 and rows[0]["product_serial"] == "E27-11"
        output = tmp_path / "report.xlsx"
        export_xlsx(query_report({}), output)
        workbook = load_workbook(output, read_only=True)
        assert workbook["明細"]["E2"].value in {"E27-10", "E27-11"}
        assert workbook["依機型彙總"]["C2"].value == 2

    preview = client.get(f"/batches/{batch_id}/print").get_data(as_text=True)
    assert "E27-10" in preview and "E27-11" in preview
    assert "2 台產品" in preview


def test_v3_migration_preserves_legacy_job_and_foreign_keys(tmp_path):
    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(path)
    legacy.executescript("""
        CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_migrations VALUES(1,'old');
        INSERT INTO schema_migrations VALUES(2,'old');
        CREATE TABLE model_master(id INTEGER PRIMARY KEY, model_name TEXT NOT NULL, model_code TEXT NOT NULL UNIQUE, description TEXT, sort_order INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE machine_master(id INTEGER PRIMARY KEY, model_id INTEGER NOT NULL REFERENCES model_master(id), display_no TEXT NOT NULL, number_prefix TEXT, number_value INTEGER, number_width INTEGER, number_semantics TEXT NOT NULL DEFAULT 'unknown', is_active INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(model_id,display_no));
        CREATE TABLE production_batch(id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL UNIQUE, batch_no TEXT NOT NULL UNIQUE, selection_mode TEXT NOT NULL, work_order_no TEXT, product_lot_no TEXT, process_name TEXT, operator_name TEXT NOT NULL, created_at TEXT NOT NULL, cancelled_at TEXT, cancelled_by TEXT);
        CREATE TABLE job_run(id INTEGER PRIMARY KEY, job_run_id TEXT NOT NULL UNIQUE, batch_id TEXT NOT NULL REFERENCES production_batch(batch_id), model_id INTEGER NOT NULL REFERENCES model_master(id), machine_id INTEGER NOT NULL REFERENCES machine_master(id), model_name_snapshot TEXT NOT NULL, model_code_snapshot TEXT NOT NULL, machine_no_snapshot TEXT NOT NULL, number_semantics_snapshot TEXT NOT NULL DEFAULT 'unknown', work_order_no TEXT, product_lot_no TEXT, process_name TEXT, planned_qty INTEGER NOT NULL CHECK(planned_qty>0), actual_qty INTEGER, status TEXT NOT NULL DEFAULT 'created', started_at TEXT, finished_at TEXT, operator_name TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        INSERT INTO model_master VALUES(1,'HR-255','HR255',NULL,0,1,'old','old');
        INSERT INTO machine_master VALUES(1,1,'E-01','E',1,2,'unknown',1,0,'old','old');
        INSERT INTO production_batch VALUES(1,'legacy-batch','B-OLD','manual','WO-OLD',NULL,NULL,'old-user','old',NULL,NULL);
        INSERT INTO job_run VALUES(1,'legacy-job','legacy-batch',1,1,'HR-255','HR255','E-01','unknown','WO-OLD',NULL,NULL,5,3,'finished','start-old','finish-old','old-user','old','old');
    """)
    legacy.commit()
    legacy.close()

    app = build_app({"TESTING": True, "DATABASE": str(path), "BACKUP_DIRECTORY": str(tmp_path / "backups"), "SECRET_KEY": "test"})
    with app.app_context():
        old = get_db().execute("SELECT * FROM job_run WHERE job_run_id='legacy-job'").fetchone()
        assert old["machine_no_snapshot"] == "E-01"
        assert old["planned_qty"] == 5 and old["actual_qty"] == 3
        assert old["product_serial"] is None and old["machine_id"] == 1
        assert get_db().execute("SELECT serial_prefix FROM model_master WHERE id=1").fetchone()[0] == "E"
        assert get_db().execute("PRAGMA foreign_key_check").fetchall() == []
        assert next(row["notnull"] for row in get_db().execute("PRAGMA table_info(job_run)") if row["name"] == "machine_id") == 0


def test_payload_round_trip_and_idempotent_scan(app):
    model_id, _ = setup_data(app)
    with app.app_context():
        batch_id, job_ids = create_batch(model_id, 2026, 3, 3, "operator")
        ensure_barcodes(batch_id)
        records = get_db().execute("SELECT * FROM barcode_record WHERE batch_id=? ORDER BY barcode_type", (batch_id,)).fetchall()
        assert len(records) == 2
        assert all(len(record["payload"]) == 15 for record in records)
        start = next(record for record in records if record["barcode_type"] == "START")
        finish = next(record for record in records if record["barcode_type"] == "FINISH")
        parsed = parse_payload(start["payload"])
        assert parsed["type"] == "START"
        assert parsed["scope"] == "batch"
        assert scan(start["payload"])["result"] == "success"
        assert scan(start["payload"])["result"] == "duplicate"
        assert scan(finish["payload"])["result"] == "success"
        assert scan(finish["payload"])["result"] == "duplicate"
        assert all(get_job(job_id)["status"] == "finished" and get_job(job_id)["actual_qty"] is None for job_id in job_ids)
        print_preview = app.test_client().get(f"/batches/{batch_id}/print")
        assert print_preview.status_code == 200
        assert print_preview.data.count(b"barcode-card") == 2


def test_finish_before_start_is_rejected(app):
    model_id, _ = setup_data(app)
    with app.app_context():
        batch_id, job_ids = create_batch(model_id, 2026, 1, 1, "operator")
        ensure_barcodes(batch_id)
        finish = get_db().execute("SELECT payload FROM barcode_record WHERE batch_id=? AND barcode_type='FINISH'", (batch_id,)).fetchone()
        assert scan(finish["payload"])["result"] == "invalid"
        assert get_job(job_ids[0])["status"] == "created"


def test_scan_api(client, app):
    model_id, _ = setup_data(app)
    with app.app_context():
        batch_id, job_ids = create_batch(model_id, 2026, 1, 1, "operator")
        ensure_barcodes(batch_id)
        start = get_db().execute("SELECT payload FROM barcode_record WHERE batch_id=? AND barcode_type='START'", (batch_id,)).fetchone()["payload"]
    response = client.post("/api/scan", json={"payload": start})
    assert response.status_code == 200
    assert response.json["result"] == "success"


def test_dashboard_status_cards_and_report_duration(client, app):
    model_id, _ = setup_data(app)
    with app.app_context():
        batch_id, _ = create_batch(model_id, 2026, 1, 1, "operator")
        ensure_barcodes(batch_id)
        start = get_db().execute("SELECT payload FROM barcode_record WHERE batch_id=? AND barcode_type='START'", (batch_id,)).fetchone()["payload"]

        assert status_label("created") == "未完成"
        assert status_label("finished") == "已完成"
        assert format_duration(None, None, "created") == "-"
        assert format_duration("2026-10-16T08:00:00+00:00", "2026-10-17T09:05:06+00:00", "finished") == "1日 01:05:06"

    home = client.get("/")
    assert home.status_code == 200
    assert b"href=\"/reports?status_group=incomplete\"" in home.data
    home_text = home.get_data(as_text=True)
    assert "未完成" in home_text
    assert "已完成" in home_text

    incomplete = client.get("/reports?status_group=incomplete")
    assert incomplete.status_code == 200
    assert "E27-01" in incomplete.get_data(as_text=True)
    assert "未完成" in incomplete.get_data(as_text=True)

    with app.app_context():
        assert scan(start)["result"] == "success"
    started = client.get("/reports?status_group=incomplete")
    assert "進行中" in started.get_data(as_text=True)


def test_report_status_group_filters_created_and_finished(client, app):
    model_id, _ = setup_data(app)
    with app.app_context():
        batch_id, _ = create_batch(model_id, 2026, 1, 1, "operator")
        ensure_barcodes(batch_id)
        records = get_db().execute("SELECT barcode_type,payload FROM barcode_record WHERE batch_id=?", (batch_id,)).fetchall()
        payloads = {row["barcode_type"]: row["payload"] for row in records}
        assert scan(payloads["START"])["result"] == "success"
        assert scan(payloads["FINISH"])["result"] == "success"

    assert "無資料" in client.get("/reports?status_group=incomplete").get_data(as_text=True)
    finished = client.get("/reports?status_group=finished")
    assert "已完成" in finished.get_data(as_text=True)
    assert "E27-01" in finished.get_data(as_text=True)


def test_backup_and_restore_are_verified(app, tmp_path):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        backup = backup_database(str(tmp_path / "backups"))
        assert verify_sqlite_backup(backup) == backup
        safety = restore_database(backup, app.config["DATABASE"], app.config["BACKUP_DIRECTORY"], "admin")
        assert safety.is_file()

