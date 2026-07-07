"""Subcontractor Master API routes — export, import, audit, reports, AI, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from import_audit_service import log_import
from subcontractor_import_service import save_subcontractor_import, validate_subcontractor_import
from subcontractor_master_service import (
    ai_validate_subcontractor,
    export_subcontractors_csv,
    export_subcontractors_excel,
    export_subcontractors_pdf,
    get_subcontractor_master,
    list_subcontractor_audit_trail,
    list_subcontractors_master,
    subcontractor_import_template,
    subcontractor_report,
    user_can_subcontractor_master,
)


def register_subcontractor_master_routes(
    app,
    *,
    login_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
) -> None:
    def _user_id() -> int | None:
        return session.get("user_id")

    def _username() -> str:
        return str(session.get("username") or "")

    def _require(action: str):
        db = get_db()
        if not user_can_subcontractor_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/subcontractor-master/export")
    @login_required
    def subcontractor_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "status": request.args.get("status") or "",
            "classification": request.args.get("classification") or "",
            "trade_category": request.args.get("trade_category") or "",
            "approval_status": request.args.get("approval_status") or "",
        }
        if request.args.get("blacklisted") == "1":
            filters["is_blacklisted"] = True
        clean_filters = {k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"}
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_subcontractors_pdf(db, report_title=title, **clean_filters)
            return send_file(
                buf, mimetype="application/pdf", as_attachment=True, download_name=f"subcontractors_{report}.pdf"
            )
        if fmt in ("xlsx", "excel"):
            buf = export_subcontractors_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="subcontractors.xlsx",
            )
        if fmt == "csv":
            csv_text = export_subcontractors_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=subcontractors.csv"},
            )
        if fmt == "pdf":
            buf = export_subcontractors_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="subcontractors.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/subcontractor-master/import/template")
    @login_required
    def subcontractor_master_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = subcontractor_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="subcontractor_master_template.xlsx",
        )

    @app.route("/api/subcontractor-master/import/validate", methods=["POST"])
    @login_required
    def subcontractor_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_subcontractor_import(db, rows))

    @app.route("/api/subcontractor-master/import/save", methods=["POST"])
    @login_required
    def subcontractor_master_import_save():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload) if upload else ([], None)
        if not rows:
            payload = request.get_json(silent=True) or {}
            rows = payload.get("parsed_rows") or payload.get("rows") or []
        if parse_err and not rows:
            return jsonify({"ok": False, "error": parse_err}), 400
        val = validate_subcontractor_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_subcontractor_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="subcontractors",
                imported_by=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                total_rows=len(val["parsed_rows"]),
                success_rows=result.get("imported", 0),
                failed_rows=0,
            )
            db.commit()
            return jsonify(result)
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/subcontractor-master/<int:subcontractor_id>/audit")
    @login_required
    def subcontractor_master_audit(subcontractor_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(
            {"items": list_subcontractor_audit_trail(db, subcontractor_id), "subcontractor_id": subcontractor_id}
        )

    @app.route("/api/subcontractor-master/reports/<report_key>")
    @login_required
    def subcontractor_master_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = subcontractor_report(
            db,
            report_key,
            status=request.args.get("status") or "",
            classification=request.args.get("classification") or "",
            trade_category=request.args.get("trade_category") or "",
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/subcontractor-master/ai/validate", methods=["POST"])
    @login_required
    def subcontractor_master_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        subcontractor_id = payload.get("subcontractor_id") or request.form.get("subcontractor_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_subcontractor(db, subcontractor_id=subcontractor_id, form=form or None))

    @app.route("/api/subcontractor-master/search", methods=["GET"])
    @login_required
    def subcontractor_master_search():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        q = request.args.get("q") or request.args.get("search") or ""
        listing = list_subcontractors_master(
            db,
            search=q,
            status=request.args.get("status") or "Active",
            per_page=min(int(request.args.get("limit") or 50), 200),
        )
        items = [
            {
                "id": s["id"],
                "subcontractor_code": s.get("subcontractor_code"),
                "subcontractor_name": s.get("subcontractor_name"),
                "gst_number": s.get("gst_number"),
                "status": s.get("status"),
                "rating": s.get("rating"),
            }
            for s in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/subcontractors", methods=["GET"])
    @login_required
    def api_mobile_list_subcontractors():
        db = get_db()
        if not user_can_subcontractor_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        q = request.args.get("q") or request.args.get("search") or ""
        listing = list_subcontractors_master(
            db,
            search=q,
            status="Active",
            per_page=min(int(request.args.get("limit") or 100), 500),
        )
        items = [
            {
                "id": s["id"],
                "subcontractor_code": s.get("subcontractor_code"),
                "subcontractor_name": s.get("subcontractor_name"),
                "gst_number": s.get("gst_number"),
                "phone": s.get("phone") or s.get("contact_number"),
                "city": s.get("city"),
                "rating": s.get("rating"),
                "trade_categories": s.get("trade_categories_list") or [],
            }
            for s in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/subcontractors/<int:subcontractor_id>", methods=["GET"])
    @login_required
    def api_mobile_get_subcontractor(subcontractor_id: int):
        db = get_db()
        if not user_can_subcontractor_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_subcontractor_master(db, subcontractor_id)
        if not row:
            return jsonify({"error": "Subcontractor not found"}), 404
        return jsonify(
            {
                "id": row["id"],
                "subcontractor_code": row.get("subcontractor_code"),
                "subcontractor_name": row.get("subcontractor_name"),
                "legal_name": row.get("legal_name"),
                "classification": row.get("classification"),
                "trade_categories": row.get("trade_categories_list") or [],
                "rate_type": row.get("rate_type"),
                "gst_number": row.get("gst_number"),
                "pan_number": row.get("pan_number"),
                "phone": row.get("phone") or row.get("contact_number"),
                "email": row.get("email"),
                "address": row.get("address"),
                "city": row.get("city"),
                "state": row.get("state"),
                "pincode": row.get("pincode"),
                "payment_terms": row.get("payment_terms"),
                "retention_percent": row.get("retention_percent"),
                "security_deposit": row.get("security_deposit"),
                "insurance_policy_no": row.get("insurance_policy_no"),
                "insurance_expiry": row.get("insurance_expiry"),
                "labour_license_no": row.get("labour_license_no"),
                "labour_license_expiry": row.get("labour_license_expiry"),
                "rating": row.get("rating"),
                "status": row.get("status"),
                "vendor_code": row.get("vendor_code"),
                "contacts": row.get("contacts") or [],
                "addresses": row.get("addresses") or [],
                "bank_accounts": row.get("bank_accounts") or [],
            }
        )
