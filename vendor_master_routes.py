"""Vendor Master API routes — export, import, audit, reports, AI, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from import_audit_service import log_import
from vendor_import_service import save_vendor_import, validate_vendor_import
from vendor_master_service import (
    ai_validate_vendor,
    export_vendors_csv,
    export_vendors_excel,
    export_vendors_pdf,
    get_vendor_master,
    list_vendor_audit_trail,
    list_vendors_master,
    user_can_vendor_master,
    vendor_import_template,
    vendor_report,
)


def register_vendor_master_routes(
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
        if not user_can_vendor_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/vendor-master/export")
    @login_required
    def vendor_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "status": request.args.get("status") or "",
            "vendor_type": request.args.get("vendor_type") or "",
            "approval_status": request.args.get("approval_status") or "",
        }
        if request.args.get("blacklisted") == "1":
            filters["is_blacklisted"] = True
        clean_filters = {k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"}
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_vendors_pdf(db, report_title=title, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"vendors_{report}.pdf")
        if fmt in ("xlsx", "excel"):
            buf = export_vendors_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="vendors.xlsx",
            )
        if fmt == "csv":
            csv_text = export_vendors_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=vendors.csv"},
            )
        if fmt == "pdf":
            buf = export_vendors_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="vendors.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/vendor-master/import/template")
    @login_required
    def vendor_master_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = vendor_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="vendor_master_template.xlsx",
        )

    @app.route("/api/vendor-master/import/validate", methods=["POST"])
    @login_required
    def vendor_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_vendor_import(db, rows))

    @app.route("/api/vendor-master/import/save", methods=["POST"])
    @login_required
    def vendor_master_import_save():
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
        val = validate_vendor_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_vendor_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="vendors",
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

    @app.route("/api/vendor-master/<int:vendor_id>/audit")
    @login_required
    def vendor_master_audit(vendor_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_vendor_audit_trail(db, vendor_id), "vendor_id": vendor_id})

    @app.route("/api/vendor-master/reports/<report_key>")
    @login_required
    def vendor_master_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = vendor_report(
            db,
            report_key,
            status=request.args.get("status") or "",
            vendor_type=request.args.get("vendor_type") or "",
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/vendor-master/ai/validate", methods=["POST"])
    @login_required
    def vendor_master_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        vendor_id = payload.get("vendor_id") or request.form.get("vendor_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_vendor(db, vendor_id=vendor_id, form=form or None))

    @app.route("/api/vendor-master/search", methods=["GET"])
    @login_required
    def vendor_master_search():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        q = request.args.get("q") or request.args.get("search") or ""
        listing = list_vendors_master(
            db,
            search=q,
            status=request.args.get("status") or "Active",
            per_page=min(int(request.args.get("limit") or 50), 200),
        )
        items = [
            {
                "id": v["id"],
                "vendor_code": v.get("code"),
                "vendor_name": v.get("name"),
                "gstin": v.get("gstin"),
                "status": v.get("status"),
                "rating": v.get("rating"),
            }
            for v in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/vendors", methods=["GET"])
    @login_required
    def api_mobile_list_vendors():
        db = get_db()
        if not user_can_vendor_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        q = request.args.get("q") or request.args.get("search") or ""
        listing = list_vendors_master(
            db,
            search=q,
            status="Active",
            per_page=min(int(request.args.get("limit") or 100), 500),
        )
        items = [
            {
                "id": v["id"],
                "vendor_code": v.get("code"),
                "vendor_name": v.get("name"),
                "gstin": v.get("gstin"),
                "phone": v.get("phone"),
                "city": v.get("city"),
                "rating": v.get("rating"),
            }
            for v in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/vendors/<int:vendor_id>", methods=["GET"])
    @login_required
    def api_mobile_get_vendor(vendor_id: int):
        db = get_db()
        if not user_can_vendor_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_vendor_master(db, vendor_id)
        if not row:
            return jsonify({"error": "Vendor not found"}), 404
        return jsonify(
            {
                "id": row["id"],
                "vendor_code": row.get("code"),
                "vendor_name": row.get("name"),
                "gstin": row.get("gstin"),
                "pan": row.get("pan"),
                "phone": row.get("phone"),
                "email": row.get("email"),
                "address": row.get("address"),
                "city": row.get("city"),
                "state": row.get("state"),
                "pincode": row.get("pincode"),
                "payment_terms": row.get("payment_terms"),
                "credit_limit": row.get("credit_limit"),
                "rating": row.get("rating"),
                "status": row.get("status"),
                "vendor_types": row.get("vendor_types_list") or [],
                "contacts": row.get("contacts") or [],
                "addresses": row.get("addresses") or [],
                "bank_accounts": row.get("bank_accounts") or [],
            }
        )
