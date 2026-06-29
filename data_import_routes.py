"""Tenant-facing UI routes for bulk data import hub, module pages, audit log, and migration wizard."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from accounts_import_service import (
    customer_import_template,
    save_customer_import,
    validate_customer_import,
    vendor_import_template,
    save_vendor_import,
    validate_vendor_import,
)
from boq_import_service import boq_import_template, save_boq_import, validate_boq_import
from bulk_import_service import parse_upload, validation_result
from data_import_registry import get_module_info, modules_by_category
from import_audit_service import (
    ensure_import_audit_schema,
    list_import_audit,
    log_import,
    rollback_import,
)


MIGRATION_WIZARD_STEPS = [
    {"step": 1, "title": "Company Details", "description": "Confirm company profile and regional settings."},
    {"step": 2, "title": "Create Admin User", "description": "Set up the primary administrator account."},
    {"step": 3, "title": "Import Masters", "description": "Customers, vendors, employees, materials, equipment."},
    {"step": 4, "title": "Import Transactions", "description": "BOQ, projects, purchase, sales, receipts, payments, bank."},
    {"step": 5, "title": "Validation", "description": "Review import audit log and fix errors."},
    {"step": 6, "title": "Finish Migration", "description": "Complete migration and go live."},
]


def _wizard_state_key(user_id) -> str:
    return f"migration_wizard_{user_id or 0}"


def register_data_import_routes(
    app,
    *,
    login_required,
    get_db,
    generate_boq_number,
    generate_client_code,
    create_approval_request,
    insert_boq_lines,
    record_pending_checker,
    boq_units,
):
    app_helpers = {
        "generate_boq_number": generate_boq_number,
        "generate_client_code": generate_client_code,
        "create_approval_request": create_approval_request,
        "insert_boq_lines": insert_boq_lines,
        "record_pending_checker": record_pending_checker,
    }

    def _prepare(db):
        ensure_import_audit_schema(db)

    @app.route("/data-import")
    @login_required
    def data_import_hub():
        db = get_db()
        _prepare(db)
        logs = list_import_audit(db, limit=10)
        return render_template(
            "data_import/hub.html",
            categories=modules_by_category(),
            recent_logs=logs,
        )

    @app.route("/data-import/audit-log")
    @login_required
    def data_import_audit_log():
        db = get_db()
        _prepare(db)
        logs = list_import_audit(db, limit=200)
        return render_template("data_import/audit_log.html", logs=logs)

    @app.route("/data-import/audit-log/<int:audit_id>/rollback", methods=["POST"])
    @login_required
    def data_import_rollback(audit_id: int):
        db = get_db()
        _prepare(db)
        username = session.get("username", "")
        try:
            result = rollback_import(db, audit_id, rolled_back_by=username)
            db.commit()
            flash(result.get("message", "Import rolled back."))
        except ValueError as exc:
            db.rollback()
            flash(str(exc), "warning")
        return redirect(url_for("data_import_audit_log"))

    @app.route("/data-import/migration-wizard", methods=["GET", "POST"])
    @login_required
    def data_import_migration_wizard():
        db = get_db()
        _prepare(db)
        user_id = session.get("user_id")
        state_key = _wizard_state_key(user_id)
        wizard_data = session.get(state_key, {"step": 1, "data": {}})
        if request.method == "POST":
            action = request.form.get("wizard_action", "next")
            step = request.form.get("step", type=int) or wizard_data.get("step", 1)
            data = wizard_data.get("data", {})
            data["company_name"] = request.form.get("company_name", data.get("company_name", ""))
            data["admin_username"] = request.form.get("admin_username", data.get("admin_username", ""))
            data["admin_email"] = request.form.get("admin_email", data.get("admin_email", ""))
            data["masters_done"] = request.form.get("masters_done") == "on"
            data["transactions_done"] = request.form.get("transactions_done") == "on"
            if action == "back" and step > 1:
                step -= 1
            elif action == "next" and step < 6:
                step += 1
            elif action == "finish":
                step = 6
                data["completed"] = True
            session[state_key] = {"step": step, "data": data}
            session.modified = True
            flash("Migration wizard progress saved.")
            return redirect(url_for("data_import_migration_wizard", step=step))
        step = request.args.get("step", type=int) or wizard_data.get("step", 1)
        step = max(1, min(6, step))
        return render_template(
            "data_import/migration_wizard.html",
            steps=MIGRATION_WIZARD_STEPS,
            current_step=step,
            wizard_data=wizard_data.get("data", {}),
            categories=modules_by_category(),
            recent_logs=list_import_audit(db, limit=20),
        )

    def _run_validate(db, module_key: str, rows: list, extra: dict):
        if module_key == "boq":
            project_id = extra.get("project_id")
            return validate_boq_import(db, rows, boq_units=boq_units, project_id=project_id)
        if module_key == "customers":
            return validate_customer_import(db, rows)
        if module_key == "vendors":
            return validate_vendor_import(db, rows)
        if module_key == "materials":
            from bulk_import_routes import _validate_materials_rows
            parsed, errors = _validate_materials_rows(db, rows)
            result = validation_result(parsed, errors)
            result["parsed_rows"] = parsed
            return result
        mod = get_module_info(module_key)
        if mod and not mod.implemented:
            return {
                "ok": False,
                "total_rows": len(rows),
                "error_count": 1,
                "errors": [{
                    "row": "—",
                    "column": "Module",
                    "error": f"{mod.label} save is not yet implemented.",
                    "suggested_fix": "Download template and use validate API when available.",
                }],
                "preview": rows[:20],
                "parsed_rows": rows,
            }
        return {"ok": False, "errors": [{"row": "—", "column": "—", "error": "Unknown module.", "suggested_fix": ""}]}

    def _run_save(db, module_key: str, parsed_rows: list, filename: str, extra: dict):
        username = session.get("username", "")
        if module_key == "boq":
            project_id = extra.get("project_id")
            if not project_id:
                raise ValueError("Project is required for BOQ import.")
            return save_boq_import(
                db,
                parsed_rows,
                project_id=project_id,
                username=username,
                filename=filename,
                generate_boq_number_fn=app_helpers["generate_boq_number"],
                insert_boq_lines_fn=app_helpers["insert_boq_lines"],
                create_approval_request_fn=lambda d, m, rid, tbl, u, uid: app_helpers["create_approval_request"](
                    d, m, rid, tbl, u, session.get("user_id")
                ),
                record_pending_checker=app_helpers["record_pending_checker"],
            )
        if module_key == "customers":
            return save_customer_import(
                db, parsed_rows, username=username, filename=filename,
                generate_client_code_fn=app_helpers["generate_client_code"],
            )
        if module_key == "vendors":
            return save_vendor_import(db, parsed_rows, username=username, filename=filename)
        if module_key == "materials":
            from store_service import import_materials_excel
            upload = extra.get("_upload")
            if not upload:
                raise ValueError("File required for materials import.")
            count, errors = import_materials_excel(db, upload, username)
            log_import(
                db, module_key="materials", imported_by=username, filename=filename,
                total_rows=len(parsed_rows), success_rows=count, failed_rows=len(errors),
                notes="; ".join(errors[:5]),
            )
            return {"ok": not errors, "imported": count, "errors": errors}
        raise ValueError("Import save not implemented for this module.")

    @app.route("/data-import/<module_key>", methods=["GET", "POST"])
    @login_required
    def data_import_module(module_key):
        mod = get_module_info(module_key)
        if not mod:
            flash("Unknown import module.")
            return redirect(url_for("data_import_hub"))
        if module_key == "boq_library":
            return redirect(url_for("boq_library"))
        db = get_db()
        _prepare(db)
        preview = None
        save_result = None
        if request.method == "POST":
            action = request.form.get("form_action", "validate")
            upload = request.files.get("import_file")
            project_id = request.form.get("project_id", type=int)
            extra = {"project_id": project_id, "_upload": upload}
            if not upload or not upload.filename:
                flash("Select an Excel file to import.")
                return redirect(url_for("data_import_module", module_key=module_key))
            rows, parse_err = parse_upload(upload)
            if parse_err:
                flash(parse_err, "warning")
                return redirect(url_for("data_import_module", module_key=module_key))
            preview = _run_validate(db, module_key, rows, extra)
            if action == "validate":
                if preview.get("ok"):
                    flash(f"Validation passed: {preview.get('valid_row_estimate', len(rows))} row(s) ready.")
                else:
                    flash(f"Validation found {preview.get('error_count', 0)} issue(s).", "warning")
            elif action == "save":
                if not preview.get("ok"):
                    flash("Fix validation errors before saving.", "warning")
                elif not mod.implemented:
                    flash("This module is not yet available for save.", "warning")
                else:
                    try:
                        parsed = preview.get("parsed_rows") or rows
                        save_result = _run_save(
                            db, module_key, parsed,
                            secure_filename(upload.filename), extra,
                        )
                        db.commit()
                        if module_key == "boq":
                            flash(f"BOQ {save_result.get('boq_number')} imported with {save_result.get('line_count')} lines.")
                        else:
                            flash(f"Imported {save_result.get('imported', 0)} record(s).")
                    except ValueError as exc:
                        db.rollback()
                        flash(str(exc))
        projects = []
        if mod.requires_project:
            projects = db.execute(
                "SELECT id, project_code, project_name FROM projects ORDER BY project_name",
            ).fetchall()
        return render_template(
            "data_import/module_import.html",
            mod=mod,
            preview=preview,
            save_result=save_result,
            projects=[dict(p) for p in projects],
        )

    @app.route("/data-import/<module_key>/template")
    @login_required
    def data_import_template_download(module_key):
        factories = {
            "boq": boq_import_template,
            "customers": customer_import_template,
            "vendors": vendor_import_template,
        }
        if module_key in factories:
            buf = factories[module_key]()
        else:
            return redirect(url_for("bulk_import_template", module_key=module_key))
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"maxek_import_{module_key}_template.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.route("/data-import/<module_key>/sample")
    @login_required
    def data_import_sample_download(module_key):
        return redirect(url_for("data_import_template_download", module_key=module_key))
