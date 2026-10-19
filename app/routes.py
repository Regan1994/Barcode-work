import tempfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for

from .barcode import code128_svg
from .db import get_db
from .services import ALLOWED_SEMANTICS, backup_database, correct_actual_qty, create_assembly_worker, create_batch, create_machine, create_machine_range, create_model, ensure_barcodes, export_xlsx, get_assembly_worker, get_batch, get_job, get_setting, list_assembly_workers, list_machines, list_models, parse_payload, query_report, restore_database, scan, set_assembly_worker_active, set_setting, update_machine, update_model

bp = Blueprint("main", __name__)


def render_home(scan_result=None):
    stats = get_db().execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN status IN ('created','started') THEN 1 ELSE 0 END), 0) AS incomplete,
            COALESCE(SUM(CASE WHEN status='finished' THEN 1 ELSE 0 END), 0) AS finished,
            COALESCE(SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END), 0) AS cancelled
        FROM job_run
        """
    ).fetchone()
    cards = [
        {"label": "未完成", "count": stats["incomplete"], "filter": "incomplete"},
        {"label": "已完成", "count": stats["finished"], "filter": "finished"},
        {"label": "已取消", "count": stats["cancelled"], "filter": "cancelled"},
    ]
    return render_template("index.html", stats=cards, scan_result=scan_result)


@bp.route("/", methods=["GET", "POST"])
def index():
    result = scan(request.form.get("payload", ""), "scanner") if request.method == "POST" else None
    return render_home(result)


@bp.route("/models", methods=["GET", "POST"])
def models():
    if request.method == "POST":
        try:
            create_model(request.form.get("model_name"), request.form.get("model_code"), request.form.get("description", ""), request.form.get("operator_name", "admin"), request.form.get("serial_prefix"))
            flash("機型已建立", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("models.html", models=list_models())


@bp.post("/models/<int:model_id>/update")
def model_update(model_id):
    try:
        update_model(model_id, request.form.get("model_name"), request.form.get("model_code"), request.form.get("description", ""), request.form.get("is_active") == "1", request.form.get("operator_name", "admin"), request.form.get("serial_prefix"))
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


@bp.route("/assembly-workers", methods=["GET", "POST"])
def assembly_workers():
    if request.method == "POST":
        try:
            create_assembly_worker(request.form.get("name"), request.form.get("changed_by", "admin"))
            flash("組裝人員已新增", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("assembly_workers.html", workers=list_assembly_workers())


@bp.post("/assembly-workers/<int:worker_id>/status")
def assembly_worker_status(worker_id):
    try:
        set_assembly_worker_active(worker_id, request.form.get("is_active") == "1", request.form.get("changed_by", "admin"))
        flash("組裝人員狀態已更新", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.assembly_workers"))


@bp.get("/jobs/new")
def job_new():
    model_id = request.args.get("model_id")
    return render_template("job_new.html", models=list_models(True), workers=list_assembly_workers(True), selected_model=model_id, current_year=datetime.now().year)


@bp.post("/jobs")
def job_create():
    try:
        model_id = int(request.form["model_id"])
        worker = get_assembly_worker(request.form.get("operator_name", ""))
        if not worker:
            raise ValueError("請先選擇有效的組裝人員；如清單沒有該人員，請先新增組裝人員")
        batch_id, _ = create_batch(model_id, request.form.get("manufacturing_year"), request.form.get("starting_number"), request.form.get("product_count"), worker["name"])
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
    if request.method == "POST":
        return render_home(scan(request.form.get("payload", ""), "scanner"))
    return redirect(url_for("main.index"))


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

