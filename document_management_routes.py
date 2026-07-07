"""Document Management API routes (MODULE-010) — library, upload, mobile, reports."""

from __future__ import annotations

import os
from typing import Callable

from flask import Response, jsonify, request, send_file, session
from werkzeug.utils import secure_filename

from bulk_import_service import parse_upload
from document_import_service import (
    document_import_template,
    save_document_import,
    validate_document_import,
)
from document_management_service import (
    DOCUMENT_CATEGORIES,
    DOCUMENT_TYPES,
    DMS_ALLOWED_EXTENSIONS,
    PREVIEW_INLINE_EXTENSIONS,
    ai_classify_document,
    ai_duplicate_check,
    ai_extract_metadata,
    approve_document,
    archive_document,
    attach_document,
    export_documents_csv,
    export_documents_excel,
    folder_tree,
    get_document,
    get_document_download_path,
    list_document_audit_trail,
    list_documents,
    list_folders,
    list_module_documents,
    list_tags,
    mobile_offline_cache_metadata,
    move_document_folder,
    reject_document,
    rename_document,
    restore_document,
    revoke_document_share,
    rollback_document_version,
    save_document,
    save_folder,
    share_document,
    soft_delete_document,
    soft_delete_folder,
    submit_document_for_approval,
    user_can_document_management,
    document_report,
)
from import_audit_service import log_import


def register_document_management_routes(
    app,
    *,
    login_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
    dest_root: str,
) -> None:
    def _user_id() -> int | None:
        return session.get("user_id")

    def _username() -> str:
        return str(session.get("username") or "")

    def _require(action: str):
        db = get_db()
        if not user_can_document_management(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/document-management")
    @login_required
    def api_list_documents():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        listing = list_documents(
            db,
            search=request.args.get("q", ""),
            folder_id=request.args.get("folder_id", type=int),
            module_name=request.args.get("module_name", ""),
            reference_id=request.args.get("reference_id", ""),
            category=request.args.get("category", ""),
            document_type=request.args.get("document_type", ""),
            status=request.args.get("status", ""),
            approval_status=request.args.get("approval_status", ""),
            company_id=request.args.get("company_id", type=int),
            branch_id=request.args.get("branch_id", type=int),
            project_id=request.args.get("project_id", type=int),
            tag=request.args.get("tag", ""),
            archive_flag=request.args.get("archive_flag", type=int),
            include_deleted=request.args.get("include_deleted") == "1",
            expiry_status=request.args.get("expiry_status", ""),
            date_from=request.args.get("date_from", ""),
            date_to=request.args.get("date_to", ""),
            page=request.args.get("page", 1, type=int),
            per_page=request.args.get("per_page", 25, type=int),
            sort_by=request.args.get("sort_by", "created_at"),
            sort_dir=request.args.get("sort_dir", "desc"),
        )
        return jsonify(listing)

    @app.route("/api/document-management/<int:document_id>")
    @login_required
    def api_get_document(document_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        item = get_document(db, document_id)
        if not item:
            return jsonify({"error": "Document not found"}), 404
        return jsonify(item)

    @app.route("/api/document-management/upload", methods=["POST"])
    @login_required
    def api_upload_document():
        denied = _require("upload")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        payload = request.form.to_dict(flat=True)
        allow_dup = payload.get("allow_duplicate") == "1"
        try:
            doc_id = save_document(
                db,
                payload,
                _username(),
                upload,
                dest_root=dest_root,
                document_id=payload.get("document_id", type=int),
                customer_id=session.get("customer_id"),
                allow_duplicate=allow_dup,
            )
            db.commit()
            return jsonify({"ok": True, "document_id": doc_id, "item": get_document(db, doc_id)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/download")
    @login_required
    def api_download_document(document_id: int):
        denied = _require("download")
        if denied:
            return denied
        db = get_db()
        version = request.args.get("version", type=int)
        paths = get_document_download_path(db, document_id, dest_root=dest_root, version=version)
        if not paths:
            return jsonify({"error": "File not found"}), 404
        abs_path, name = paths
        return send_file(abs_path, as_attachment=True, download_name=secure_filename(name))

    @app.route("/api/document-management/<int:document_id>/preview")
    @login_required
    def api_preview_document(document_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        version = request.args.get("version", type=int)
        paths = get_document_download_path(db, document_id, dest_root=dest_root, version=version)
        if not paths:
            return jsonify({"error": "File not found"}), 404
        abs_path, name = paths
        ext = os.path.splitext(name)[1].lower()
        if ext not in PREVIEW_INLINE_EXTENSIONS:
            return send_file(abs_path, as_attachment=True, download_name=secure_filename(name))
        mimetype = "application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}" if ext in {".jpg", ".jpeg", ".png", ".webp"} else "text/plain"
        return send_file(abs_path, mimetype=mimetype, as_attachment=False, download_name=secure_filename(name))

    @app.route("/api/document-management/<int:document_id>/versions")
    @login_required
    def api_document_versions(document_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        doc = get_document(db, document_id)
        if not doc:
            return jsonify({"error": "Document not found"}), 404
        return jsonify({"items": doc.get("versions", []), "document_id": document_id})

    @app.route("/api/document-management/<int:document_id>/rollback", methods=["POST"])
    @login_required
    def api_rollback_document(document_id: int):
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        version = int(payload.get("version_number") or payload.get("version") or 0)
        if not version:
            return jsonify({"error": "version_number is required"}), 400
        try:
            rollback_document_version(db, document_id, version, _username())
            db.commit()
            return jsonify({"ok": True, "item": get_document(db, document_id)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/rename", methods=["POST"])
    @login_required
    def api_rename_document(document_id: int):
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            rename_document(db, document_id, payload.get("document_name", ""), _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/move", methods=["POST"])
    @login_required
    def api_move_document(document_id: int):
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        folder_id = payload.get("folder_id")
        try:
            move_document_folder(db, document_id, int(folder_id) if folder_id else None, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/archive", methods=["POST"])
    @login_required
    def api_archive_document(document_id: int):
        denied = _require("archive")
        if denied:
            return denied
        db = get_db()
        try:
            archive_document(db, document_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/restore", methods=["POST"])
    @login_required
    def api_restore_document(document_id: int):
        denied = _require("restore")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        from_archive = payload.get("from_archive", True)
        try:
            restore_document(db, document_id, _username(), from_archive=bool(from_archive))
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>", methods=["DELETE"])
    @login_required
    def api_delete_document(document_id: int):
        denied = _require("delete")
        if denied:
            return denied
        db = get_db()
        try:
            soft_delete_document(db, document_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/approve", methods=["POST"])
    @login_required
    def api_approve_document(document_id: int):
        denied = _require("approve")
        if denied:
            return denied
        db = get_db()
        try:
            approve_document(db, document_id, _username())
            db.commit()
            return jsonify({"ok": True, "item": get_document(db, document_id)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/reject", methods=["POST"])
    @login_required
    def api_reject_document(document_id: int):
        denied = _require("approve")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            reject_document(db, document_id, _username(), payload.get("remarks", ""))
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/submit", methods=["POST"])
    @login_required
    def api_submit_document(document_id: int):
        denied = _require("upload")
        if denied:
            return denied
        db = get_db()
        try:
            submit_document_for_approval(db, document_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/<int:document_id>/share", methods=["POST"])
    @login_required
    def api_share_document(document_id: int):
        denied = _require("share")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            share_id = share_document(
                db,
                document_id,
                _username(),
                shared_with_user_id=payload.get("shared_with_user_id", type=int),
                shared_with_role=payload.get("shared_with_role", ""),
                permission=payload.get("permission", "view"),
                expires_at=payload.get("expires_at"),
            )
            db.commit()
            return jsonify({"ok": True, "share_id": share_id})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/shares/<int:share_id>", methods=["DELETE"])
    @login_required
    def api_revoke_share(share_id: int):
        denied = _require("share")
        if denied:
            return denied
        db = get_db()
        try:
            revoke_document_share(db, share_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/folders")
    @login_required
    def api_list_folders():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        tree = request.args.get("tree") == "1"
        if tree:
            return jsonify({"items": folder_tree(db, company_id=request.args.get("company_id", type=int))})
        return jsonify({"items": list_folders(db, company_id=request.args.get("company_id", type=int))})

    @app.route("/api/document-management/folders", methods=["POST"])
    @login_required
    def api_save_folder():
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        folder_id = payload.get("folder_id", type=int)
        try:
            fid = save_folder(db, payload, _username(), folder_id)
            db.commit()
            return jsonify({"ok": True, "folder_id": fid})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/folders/<int:folder_id>", methods=["DELETE"])
    @login_required
    def api_delete_folder(folder_id: int):
        denied = _require("delete")
        if denied:
            return denied
        db = get_db()
        try:
            soft_delete_folder(db, folder_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/tags")
    @login_required
    def api_list_tags():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_tags(db)})

    @app.route("/api/document-management/module/<module_name>/<reference_id>")
    @login_required
    def api_module_documents(module_name: str, reference_id: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        items = list_module_documents(db, module_name, reference_id)
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/document-management/<int:document_id>/audit")
    @login_required
    def api_document_audit(document_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_document_audit_trail(db, document_id), "document_id": document_id})

    @app.route("/api/document-management/reports/<report_key>")
    @login_required
    def api_document_report(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        try:
            rows = document_report(
                db,
                report_key,
                company_id=request.args.get("company_id", type=int),
                folder_id=request.args.get("folder_id", type=int),
            )
            return jsonify({"report": report_key, "items": rows, "count": len(rows)})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/document-management/export")
    @login_required
    def api_export_documents():
        denied = _require("export")
        if denied:
            return denied
        db = get_db()
        fmt = (request.args.get("format") or "xlsx").lower()
        filters = {
            k: v
            for k, v in {
                "folder_id": request.args.get("folder_id", type=int),
                "module_name": request.args.get("module_name", ""),
                "archive_flag": request.args.get("archive_flag", type=int),
                "include_deleted": request.args.get("include_deleted") == "1",
            }.items()
            if v not in (None, "", False) or k == "include_deleted"
        }
        if fmt == "csv":
            csv_text = export_documents_csv(db, **filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=documents.csv"},
            )
        buf = export_documents_excel(db, **filters)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="documents.xlsx",
        )

    @app.route("/api/document-management/import/template")
    @login_required
    def api_document_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = document_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="document_metadata_template.xlsx",
        )

    @app.route("/api/document-management/import/validate", methods=["POST"])
    @login_required
    def api_document_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_document_import(db, rows))

    @app.route("/api/document-management/import/save", methods=["POST"])
    @login_required
    def api_document_import_save():
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
        val = validate_document_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_document_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
            )
            log_import(
                db,
                module_key="documents",
                imported_by=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                total_rows=len(val["parsed_rows"]),
                success_rows=result.get("imported", 0),
                failed_rows=result.get("skipped", 0),
            )
            db.commit()
            return jsonify(result)
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/document-management/ai/metadata", methods=["POST"])
    @login_required
    def api_document_ai_metadata():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        return jsonify(
            ai_extract_metadata(
                db,
                document_id=payload.get("document_id"),
                form=payload.get("form"),
            )
        )

    @app.route("/api/document-management/<int:document_id>/ai/classify", methods=["POST"])
    @login_required
    def api_document_ai_classify(document_id: int):
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        result = ai_classify_document(db, document_id)
        if result.get("ok"):
            db.commit()
        return jsonify(result)

    @app.route("/api/document-management/<int:document_id>/ai/duplicate", methods=["GET"])
    @login_required
    def api_document_ai_duplicate(document_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(ai_duplicate_check(db, document_id))

    @app.route("/api/document-management/meta")
    @login_required
    def api_document_meta():
        return jsonify(
            {
                "categories": list(DOCUMENT_CATEGORIES),
                "document_types": list(DOCUMENT_TYPES),
                "allowed_extensions": sorted(ext.lstrip(".") for ext in DMS_ALLOWED_EXTENSIONS),
            }
        )

    @app.route("/api/mobile/documents", methods=["GET"])
    @login_required
    def api_mobile_list_documents():
        db = get_db()
        if not user_can_document_management(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        listing = list_documents(
            db,
            module_name=request.args.get("module_name", ""),
            reference_id=request.args.get("reference_id", ""),
            per_page=request.args.get("limit", 50, type=int),
        )
        items = [
            {
                "id": d["id"],
                "document_number": d.get("document_number"),
                "document_name": d.get("document_name"),
                "module_name": d.get("module_name"),
                "reference_id": d.get("reference_id"),
                "version_number": d.get("version_number"),
                "file_extension": d.get("file_extension"),
                "approval_status": d.get("approval_status"),
            }
            for d in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/documents/upload", methods=["POST"])
    @login_required
    def api_mobile_upload_document():
        db = get_db()
        if not user_can_document_management(db, _user_id(), "upload", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        upload = request.files.get("file") or request.files.get("camera")
        payload = request.form.to_dict(flat=True)
        payload.setdefault("document_name", getattr(upload, "filename", None) or "Camera capture")
        try:
            doc_id = save_document(
                db,
                payload,
                _username(),
                upload,
                dest_root=dest_root,
                customer_id=session.get("customer_id"),
            )
            db.commit()
            return jsonify({"ok": True, "document_id": doc_id})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/mobile/documents/<int:document_id>", methods=["GET"])
    @login_required
    def api_mobile_get_document(document_id: int):
        db = get_db()
        if not user_can_document_management(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        item = get_document(db, document_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        return jsonify(
            {
                "id": item["id"],
                "document_number": item.get("document_number"),
                "document_name": item.get("document_name"),
                "module_name": item.get("module_name"),
                "reference_id": item.get("reference_id"),
                "version_number": item.get("version_number"),
                "file_extension": item.get("file_extension"),
                "file_size": item.get("file_size"),
                "approval_status": item.get("approval_status"),
                "preview_url": f"/api/document-management/{document_id}/preview",
                "download_url": f"/api/document-management/{document_id}/download",
            }
        )

    @app.route("/api/mobile/documents/offline-cache")
    @login_required
    def api_mobile_offline_cache():
        db = get_db()
        if not user_can_document_management(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        items = mobile_offline_cache_metadata(db, _user_id(), limit=request.args.get("limit", 100, type=int))
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/documents/attach", methods=["POST"])
    @login_required
    def api_mobile_attach_document():
        db = get_db()
        if not user_can_document_management(db, _user_id(), "upload", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        upload = request.files.get("file")
        module_name = request.form.get("module_name", "")
        reference_id = request.form.get("reference_id", "")
        if not module_name or not reference_id:
            return jsonify({"error": "module_name and reference_id required"}), 400
        try:
            doc_id = attach_document(
                db,
                module_name,
                reference_id,
                upload,
                _username(),
                dest_root=dest_root,
                document_name=request.form.get("document_name", ""),
                category=request.form.get("category", ""),
            )
            db.commit()
            return jsonify({"ok": True, "document_id": doc_id})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
