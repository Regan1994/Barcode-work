import pytest

from app.db import get_db
from app.services import backup_database, create_batch, create_machine_range, create_model, ensure_barcodes, get_job, parse_payload, restore_database, scan, set_setting, verify_sqlite_backup


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


def test_machine_range_validates_semantics_and_batch_rejects_duplicate_machine(app):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        with pytest.raises(ValueError, match="編號語意必須是 unknown、asset 或 serial"):
            create_machine_range(model_id, "X", 1, 1, 2, "future")

        with pytest.raises(ValueError, match="同一台機台不可重複選取"):
            create_batch(model_id, [machine_ids[0], machine_ids[0]], "multi", "", "", "", 1, "operator")

        assert get_db().execute("SELECT COUNT(*) AS count FROM job_run").fetchone()["count"] == 0


def test_payload_round_trip_and_idempotent_scan(app):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        batch_id, job_ids = create_batch(model_id, [machine_ids[0], machine_ids[2], machine_ids[6]], "multi", "WO-1", "LOT-1", "組裝", 5, "operator")
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
        assert all(get_job(job_id)["status"] == "finished" for job_id in job_ids)
        print_preview = app.test_client().get(f"/batches/{batch_id}/print")
        assert print_preview.status_code == 200
        assert print_preview.data.count(b"barcode-card") == 2


def test_finish_before_start_is_rejected(app):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        batch_id, job_ids = create_batch(model_id, [machine_ids[0]], "range", "", "", "", 1, "operator")
        ensure_barcodes(batch_id)
        finish = get_db().execute("SELECT payload FROM barcode_record WHERE batch_id=? AND barcode_type='FINISH'", (batch_id,)).fetchone()
        assert scan(finish["payload"])["result"] == "invalid"
        assert get_job(job_ids[0])["status"] == "created"


def test_scan_api(client, app):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        batch_id, job_ids = create_batch(model_id, [machine_ids[0]], "multi", "", "", "", 1, "operator")
        ensure_barcodes(batch_id)
        start = get_db().execute("SELECT payload FROM barcode_record WHERE batch_id=? AND barcode_type='START'", (batch_id,)).fetchone()["payload"]
    response = client.post("/api/scan", json={"payload": start})
    assert response.status_code == 200
    assert response.json["result"] == "success"


def test_backup_and_restore_are_verified(app, tmp_path):
    model_id, machine_ids = setup_data(app)
    with app.app_context():
        backup = backup_database(str(tmp_path / "backups"))
        assert verify_sqlite_backup(backup) == backup
        safety = restore_database(backup, app.config["DATABASE"], app.config["BACKUP_DIRECTORY"], "admin")
        assert safety.is_file()

