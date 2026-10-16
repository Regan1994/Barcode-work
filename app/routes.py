import tempfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for

from .barcode import code128_svg
from .db import get_db
from .services import ALLOWED_SEMANTICS, backup_database, correct_actual_qty, create_batch, create_machine, create_machine_range, create_model, ensure_barcodes, export_xlsx, get_batch, get_job, get_setting, list_machines, list_models, parse_payload, query_report, restore_database, scan, set_setting, update_machine, update_model

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    stats = get_db().execute("SELECT status, COUNT(*) AS count FROM job_run GROUP BY status").fetchall()
    return render_template("index.html", stats=stats)


@bp.route("/models", methods=["GET", "POST"])
def models():
    if request.method == "POST":
        try:
            create_model(request.form.get("model_name"), request.form.get("model_code"), request.form.get("description", ""), request.form.get("operator_name", "admin"))
            flash("機型已建立", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("models.html", models=list_models())


@bp.post("/models/<int:model_id>/update")
def model_update(model_id):
    try:
        update_model(model_id, request.form.get("model_name"), request.form.get("model_code"), request.form.get("description", ""), request.form.get("is_active") == "1", request.form.get("operator_name", "admin"))
        flash("機型已更新", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.models"))


@bp.route("/machines", methods=["GET", "POST"])
def machines():
    models = list_models()
    if request.method == "POST":
        try:
            model_id = int(request.form["model_id"])
            semantics = request.form.get("number_semantics") or "unknown"
            if request.form.get("create_mode") == "range":
                create_machine_range(model_id, request.form["prefix"], int(request.form["start"]), int(request.form["end"]), int(request.form["width"]), semantics, request.form.get("operator_name", "admin"))
            else:
                create_machine(model_id, request.form["display_no"], request.form.get("prefix", ""), None, None, semantics, request.form.get("operator_name", "admin"))
            flash("機台已建立", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "error")
    model_id = request.args.get("model_id")
    return render_template("machines.html", models=models, machines=list_machines(model_id), selected_model=model_id, semantics=ALLOWED_SEMANTICS)


@bp.post("/machines/<int:machine_id>/update")
def machine_update(machine_id):
    try:
        update_machine(machine_id, request.form.get("display_no"), request.form.get("number_semantics"), request.form.get("is_active") == "1", request.form.get("operator_name", "admin"))
        flash("機台已更新", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.machines", model_id=request.form.get("model_id")))


@bp.get("/jobs/new")
def job_new():
    model_id = request.args.get("model_id")
    return render_template("job_new.html", models=list_models(True), machines=list_machines(model_id, True) if model_id else [], selected_model=model_id)


@bp.post("/jobs")
def job_create():
    try:
        model_id = int(request.form["model_id"])
        selection_mode = request.form.get("selection_mode", "multi")
        if selection_mode == "range":
            available = list_machines(model_id, True)
            start_id, end_id = int(request.form["range_start"]), int(request.form["range_end"])
            positions = {row["id"]: index for index, row in enumerate(available)}
            if start_id not in positions or end_id not in positions or positions[start_id] > positions[end_id]:
                raise ValueError("連續範圍起點不可大於終點，且必須在同一機型啟用清單中")
            machine_ids = [row["id"] for row in available[positions[start_id]:positions[end_id] + 1]]
        else:
            machine_ids = [int(x) for x in request.form.getlist("machine_ids")]
        batch_id, _ = create_batch(model_id, machine_ids, selection_mode, request.form.get("work_order_no", ""), request.form.get("product_lot_no", ""), request.form.get("process_name", ""), request.form.get("planned_qty"), request.form.get("operator_name", ""))
        ensure_barcodes(batch_id)
        return redirect(url_for("main.print_batch", batch_id=batch_id))
    except (ValueError, KeyError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.job_new", model_id=request.form.get("model_id")))


@bp.get("/batches/<batch_id>/print")
def print_batch(batch_id):
    batch = get_batch(batch_id)
    if not batch:
        return "找不到批次", 404
    jobs = ensure_barcodes(batch_id)
    records = get_db().execute("SELECT * FROM barcode_record WHERE batch_id=? OR job_run_id IN (SELECT job_run_id FROM job_run WHERE batch_id=?) ORDER BY barcode_scope, barcode_type, job_run_id", (batch_id, batch_id)).fetchall()
    return render_template("print_batch.html", batch=batch, jobs=jobs, records=records, code128_svg=code128_svg)


@bp.route("/scan", methods=["GET", "POST"])
def scan_page():
    result = None
    if request.method == "POST":
        result = scan(request.form.get("payload", ""), request.form.get("operator_name", "scanner"))
    return render_template("scan.html", result=result)


@bp.post("/api/scan")
def api_scan():
    result = scan(request.json.get("payload", "") if request.is_json else request.form.get("payload", ""), request.json.get("operator_name", "scanner") if request.is_json else request.form.get("operator_name", "scanner"))
    return jsonify(result), 200 if result["result"] in {"success", "duplicate"} else 400


@bp.route("/reports", methods=["GET", "POST"])
def reports():
    filters = request.form.to_dict() if request.method == "POST" else request.args.to_dict()
    rows = query_report(filters)
    return render_template("reports.html", rows=rows, filters=filters)


@bp.post("/reports/export")
def reports_export():
    filters = request.form.to_dict()
    rows = query_report(filters)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    export_xlsx(rows, tmp.name)
    filename = "INTJR_報工報表_" + datetime.now().strftime("%Y%m%d_%H%M") + ".xlsx"
    return send_file(tmp.name, as_attachment=True, download_name=filename)


@bp.post("/jobs/<job_run_id>/quantity")
def quantity_update(job_run_id):
    try:
        correct_actual_qty(job_run_id, request.form.get("actual_qty"), request.form.get("operator_name", "admin"))
        flash("完成量已更正並寫入稽核紀錄", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.reports"))


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        try:
            set_setting("number_semantics", request.form.get("number_semantics", "unknown"), request.form.get("operator_name", "admin"))
            set_setting("batch_scan_mode", request.form.get("batch_scan_mode", "batch"), request.form.get("operator_name", "admin"))
            flash("設定已保存；未確認語意仍可維持 unknown", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("settings.html", number_semantics=get_setting("number_semantics", "unknown"), batch_scan_mode=get_setting("batch_scan_mode", "batch"), semantics=ALLOWED_SEMANTICS)


@bp.post("/backup")
def backup():
    try:
        target = backup_database(current_app.config["BACKUP_DIRECTORY"])
        flash(f"備份完成：{target.name}", "success")
    except Exception as exc:
        flash(f"備份失敗：{exc}", "error")
    return redirect(url_for("main.index"))


@bp.post("/restore")
def restore():
    source = request.form.get("source_path", "").strip()
    try:
        restore_database(source, current_app.config["DATABASE"], current_app.config["BACKUP_DIRECTORY"], request.form.get("operator_name", "admin"))
        flash("還原完成，請重新啟動應用程式以重新建立資料庫連線", "success")
    except Exception as exc:
        flash(f"還原失敗：{exc}", "error")
    return redirect(url_for("main.settings"))

