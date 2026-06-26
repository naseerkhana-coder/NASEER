"""Flask routes for OpenAI-powered MAXEK ERP features."""

from __future__ import annotations

import json
import os
from typing import Any

from flask import jsonify, request, session

from ai_service import OpenAIConfigurationError, chat_completion, chat_completion_json
from tenant_isolation import get_tenant_context, tenant_where_clause

PROJECT_DOC_FIELDS = {
    "agreement_document": "Agreement",
    "work_order_document": "Work Order",
    "bank_guarantee_document": "Bank Guarantee",
    "security_deposit_document": "Security Deposit",
}


def _json_error(message: str, code: str, status: int = 400):
    return jsonify({"error": message, "code": code}), status


def _require_session_user():
    if not session.get("user_id"):
        return _json_error("Authentication required", "unauthorized", 401)
    return None


def _openai_unavailable_response(exc: Exception):
    if isinstance(exc, OpenAIConfigurationError):
        return _json_error(str(exc), "openai_not_configured", 503)
    return _json_error("AI service is temporarily unavailable.", "openai_error", 503)


def _request_json() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _tenant_ctx() -> dict[str, Any]:
    return get_tenant_context(session=session)


def _project_row(db, project_id: int, tenant_ctx: dict[str, Any]):
    tenant_sql, tenant_params = tenant_where_clause("p", tenant_ctx)
    clauses = ["p.id=?"]
    params: list[Any] = [project_id]
    if tenant_sql:
        clauses.append(tenant_sql)
        params.extend(tenant_params)
    return db.execute(
        f"SELECT p.* FROM projects p WHERE {' AND '.join(clauses)}",
        tuple(params),
    ).fetchone()


def _serialize_boq_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "boq_id": row.get("boq_id"),
        "boq_number": row.get("boq_number") or "",
        "line_no": row.get("line_no"),
        "item_code": row.get("item_code") or "",
        "item_description": row.get("item_description") or "",
        "quantity": float(row.get("quantity") or 0),
        "unit": row.get("unit") or "",
        "rate": float(row.get("rate") or 0),
        "amount": float(row.get("amount") or 0),
    }


def _fetch_boq_items(db, *, project_id: int | None, limit: int = 200) -> list[dict[str, Any]]:
    tenant_ctx = _tenant_ctx()
    sql = (
        "SELECT bi.id, bi.boq_id, bi.line_no, COALESCE(bi.item_code, '') AS item_code, "
        "COALESCE(bi.item_description, '') AS item_description, "
        "COALESCE(bi.quantity, 0) AS quantity, COALESCE(bi.unit, '') AS unit, "
        "COALESCE(bi.rate, 0) AS rate, COALESCE(bi.amount, 0) AS amount, "
        "COALESCE(bm.boq_number, '') AS boq_number, p.project_name, p.project_code "
        "FROM boq_items bi "
        "LEFT JOIN boq_master bm ON bi.boq_id = bm.id "
        "LEFT JOIN projects p ON COALESCE(bi.project_id, bm.project_id) = p.id "
        "WHERE COALESCE(bi.is_deleted, 0)=0 AND COALESCE(bm.is_deleted, 0)=0 "
    )
    params: list[Any] = []
    if project_id:
        sql += "AND COALESCE(bi.project_id, bm.project_id)=? "
        params.append(project_id)
    tenant_sql, tenant_params = tenant_where_clause("p", tenant_ctx)
    if tenant_sql:
        sql += f"AND {tenant_sql} "
        params.extend(tenant_params)
    sql += "ORDER BY p.project_name, bm.boq_number, bi.line_no, bi.id LIMIT ?"
    params.append(limit)
    rows = db.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def _fetch_dpr_context(db, *, project_id: int | None, report_date: str | None) -> dict[str, Any]:
    tenant_ctx = _tenant_ctx()
    project = None
    if project_id:
        project_row = _project_row(db, project_id, tenant_ctx)
        if project_row:
            project = dict(project_row)

    sql = (
        "SELECT m.id, m.report_date, m.boq_number, m.boq_description, m.unit, "
        "m.calculated_quantity, m.work_description, m.approval_status, "
        "p.project_code, p.project_name "
        "FROM dpr_measurements m "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "WHERE COALESCE(m.dpr_status, 'submitted') != 'draft' "
    )
    params: list[Any] = []
    if project_id:
        sql += "AND m.project_id=? "
        params.append(project_id)
    if report_date:
        sql += "AND m.report_date=? "
        params.append(report_date)
    tenant_sql, tenant_params = tenant_where_clause("p", tenant_ctx)
    if tenant_sql:
        sql += f"AND {tenant_sql} "
        params.extend(tenant_params)
    sql += "ORDER BY m.report_date DESC, m.id DESC LIMIT 40"
    measurements = [dict(row) for row in db.execute(sql, tuple(params)).fetchall()]
    return {"project": project, "measurements": measurements}


def _read_text_file(path: str, max_chars: int = 12000) -> str:
    if not path or not os.path.isfile(path):
        return ""
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".txt", ".md", ".csv", ".json"):
        return ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            return handle.read(max_chars)
    except OSError:
        return ""


def _resolve_document_content(
    db,
    *,
    document_id: int | None,
    project_id: int | None,
    doc_field: str | None,
    text: str | None,
    project_docs_dir: str,
    dpr_docs_dir: str,
) -> tuple[str, dict[str, Any]]:
    if text and str(text).strip():
        return str(text).strip(), {"source": "text"}

    meta: dict[str, Any] = {}

    if document_id:
        row = db.execute(
            "SELECT a.*, p.project_name, p.project_code "
            "FROM dpr_attachments a "
            "LEFT JOIN projects p ON a.project_id = p.id "
            "WHERE a.id=?",
            (document_id,),
        ).fetchone()
        if row:
            row = dict(row)
            meta = {
                "source": "dpr_attachment",
                "document_id": document_id,
                "filename": row.get("original_filename") or row.get("stored_filename"),
                "project_name": row.get("project_name"),
                "report_date": row.get("report_date"),
                "notes": row.get("notes") or "",
            }
            stored = row.get("stored_filename") or ""
            file_path = os.path.join(dpr_docs_dir, stored) if stored else ""
            extracted = _read_text_file(file_path)
            if extracted:
                return extracted, meta
            parts = [
                f"Site DPR document: {meta.get('filename') or 'attachment'}",
                f"Project: {meta.get('project_name') or row.get('project_id')}",
                f"Report date: {meta.get('report_date') or '—'}",
            ]
            if meta.get("notes"):
                parts.append(f"Uploader notes: {meta['notes']}")
            parts.append(
                "Binary PDF/image content is not extracted server-side; summarize from metadata "
                "and ask the user to paste text for full analysis if needed."
            )
            return "\n".join(parts), meta

    if project_id and doc_field and doc_field in PROJECT_DOC_FIELDS:
        tenant_ctx = _tenant_ctx()
        project = _project_row(db, project_id, tenant_ctx)
        if not project:
            raise ValueError("Project not found or not accessible.")
        project = dict(project)
        filename = project.get(doc_field) or ""
        meta = {
            "source": "project_document",
            "project_id": project_id,
            "doc_field": doc_field,
            "label": PROJECT_DOC_FIELDS[doc_field],
            "filename": filename,
            "project_name": project.get("project_name"),
            "project_code": project.get("project_code"),
        }
        if not filename:
            raise ValueError(f"No {PROJECT_DOC_FIELDS[doc_field]} file uploaded for this project.")
        file_path = os.path.join(project_docs_dir, os.path.basename(filename))
        extracted = _read_text_file(file_path)
        if extracted:
            return extracted, meta
        return (
            f"Project document ({meta['label']}): {filename}\n"
            f"Project: {meta.get('project_code') or project_id} — {meta.get('project_name')}\n"
            "PDF/image binary content is not extracted; summarize from filename and context.",
            meta,
        )

    raise ValueError("Provide text, document_id, or project_id with doc_field.")


def register_ai_routes(
    app,
    *,
    login_required,
    get_db,
    project_docs_dir: str,
    dpr_docs_dir: str,
):
    del login_required  # API routes use JSON session checks instead of HTML redirect.

    @app.route("/api/ai/dpr-writer", methods=["POST"])
    def api_ai_dpr_writer():
        auth_err = _require_session_user()
        if auth_err:
            return auth_err
        data = _request_json()
        project_id = data.get("project_id")
        report_date = (data.get("date") or data.get("report_date") or "").strip()
        notes = (data.get("notes") or "").strip()
        measurements = data.get("measurements")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                return _json_error("Invalid project_id", "validation_error", 400)

        db = get_db()
        ctx = _fetch_dpr_context(db, project_id=project_id, report_date=report_date or None)
        if project_id and not ctx.get("project"):
            return _json_error("Project not found or not accessible.", "not_found", 404)

        payload = {
            "project": ctx.get("project"),
            "report_date": report_date,
            "user_notes": notes,
            "extra_measurements": measurements,
            "recent_measurements": ctx.get("measurements") or [],
        }
        system = (
            "You are a construction site Daily Progress Report (DPR) writer for MAXEK ERP. "
            "Write clear, professional site progress narrative suitable for client and internal records. "
            "Use Indian construction terminology where appropriate. Mention quantities, activities, and issues "
            "when present in the data. Keep output concise (2–5 short paragraphs) with optional bullet highlights."
        )
        user_prompt = (
            "Generate a suggested DPR narrative from this JSON context:\n"
            f"{json.dumps(payload, default=str, indent=2)}"
        )
        try:
            narrative = chat_completion(system, user_prompt, temperature=0.5, max_tokens=1800)
        except OpenAIConfigurationError as exc:
            return _openai_unavailable_response(exc)
        except Exception:
            return _openai_unavailable_response(Exception("openai failed"))

        return jsonify({
            "narrative": narrative,
            "project_id": project_id,
            "date": report_date,
        })

    @app.route("/api/ai/project-assistant", methods=["POST"])
    def api_ai_project_assistant():
        auth_err = _require_session_user()
        if auth_err:
            return auth_err
        data = _request_json()
        message = (data.get("message") or "").strip()
        if not message:
            return _json_error("message is required", "validation_error", 400)
        project_id = data.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                return _json_error("Invalid project_id", "validation_error", 400)

        db = get_db()
        tenant_ctx = _tenant_ctx()
        context: dict[str, Any] = {"user": session.get("employee_name") or session.get("username")}
        if project_id:
            project = _project_row(db, project_id, tenant_ctx)
            if not project:
                return _json_error("Project not found or not accessible.", "not_found", 404)
            project = dict(project)
            boq_count = db.execute(
                "SELECT COUNT(*) AS c FROM boq_items bi "
                "LEFT JOIN boq_master bm ON bi.boq_id = bm.id "
                "WHERE COALESCE(bi.project_id, bm.project_id)=? "
                "AND COALESCE(bi.is_deleted, 0)=0",
                (project_id,),
            ).fetchone()["c"]
            dpr_count = db.execute(
                "SELECT COUNT(*) AS c FROM dpr_measurements WHERE project_id=?",
                (project_id,),
            ).fetchone()["c"]
            context["project"] = {
                "id": project_id,
                "project_code": project.get("project_code"),
                "project_name": project.get("project_name"),
                "location": project.get("location"),
                "status": project.get("status"),
                "start_date": project.get("start_date"),
                "end_date": project.get("end_date"),
                "approved_total_amount": project.get("approved_total_amount"),
                "boq_item_count": int(boq_count or 0),
                "dpr_measurement_count": int(dpr_count or 0),
            }

        system = (
            "You are MAXEK ERP Project Assistant — a helpful construction ERP copilot. "
            "Answer questions about projects, DPR, BOQ, billing, and site operations using only the "
            "provided context. If data is missing, say what the user should open in MAXEK ERP. "
            "Be practical and concise."
        )
        user_prompt = (
            f"Context JSON:\n{json.dumps(context, default=str, indent=2)}\n\n"
            f"User question:\n{message}"
        )
        try:
            reply = chat_completion(system, user_prompt, temperature=0.4, max_tokens=1500)
        except OpenAIConfigurationError as exc:
            return _openai_unavailable_response(exc)
        except Exception:
            return _openai_unavailable_response(Exception("openai failed"))

        return jsonify({"reply": reply, "project_id": project_id})

    @app.route("/api/ai/boq-search", methods=["POST"])
    def api_ai_boq_search():
        auth_err = _require_session_user()
        if auth_err:
            return auth_err
        data = _request_json()
        query_text = (data.get("query") or "").strip()
        if not query_text:
            return _json_error("query is required", "validation_error", 400)
        project_id = data.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                return _json_error("Invalid project_id", "validation_error", 400)

        db = get_db()
        if project_id:
            if not _project_row(db, project_id, _tenant_ctx()):
                return _json_error("Project not found or not accessible.", "not_found", 404)

        items = _fetch_boq_items(db, project_id=project_id, limit=250)
        compact = [_serialize_boq_item(row) for row in items]

        system = (
            "You help users find BOQ (Bill of Quantities) line items in a construction ERP. "
            "Given a natural language query and a list of BOQ items, return JSON with keys: "
            "`explanation` (string, brief) and `matched_ids` (array of integer item ids from the list). "
            "Only include ids that genuinely match the query. If none match, return an empty array."
        )
        user_prompt = (
            f"Search query: {query_text}\n\n"
            f"BOQ items JSON:\n{json.dumps(compact, indent=2)}"
        )
        try:
            ai_result = chat_completion_json(system, user_prompt, max_tokens=1200)
        except OpenAIConfigurationError as exc:
            return _openai_unavailable_response(exc)
        except ValueError as exc:
            return _json_error(str(exc), "ai_parse_error", 502)
        except Exception:
            return _openai_unavailable_response(Exception("openai failed"))

        matched_ids = ai_result.get("matched_ids") or []
        id_set = set()
        for raw_id in matched_ids:
            try:
                id_set.add(int(raw_id))
            except (TypeError, ValueError):
                continue
        matched_items = [_serialize_boq_item(row) for row in items if row.get("id") in id_set]

        return jsonify({
            "query": query_text,
            "explanation": ai_result.get("explanation") or "",
            "items": matched_items,
            "total_candidates": len(compact),
        })

    @app.route("/api/ai/document-reader", methods=["POST"])
    def api_ai_document_reader():
        auth_err = _require_session_user()
        if auth_err:
            return auth_err
        data = _request_json()
        text = data.get("text")
        document_id = data.get("document_id")
        project_id = data.get("project_id")
        doc_field = (data.get("doc_field") or "").strip()

        if document_id is not None:
            try:
                document_id = int(document_id)
            except (TypeError, ValueError):
                return _json_error("Invalid document_id", "validation_error", 400)
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                return _json_error("Invalid project_id", "validation_error", 400)

        db = get_db()
        try:
            content, meta = _resolve_document_content(
                db,
                document_id=document_id,
                project_id=project_id,
                doc_field=doc_field or None,
                text=text,
                project_docs_dir=project_docs_dir,
                dpr_docs_dir=dpr_docs_dir,
            )
        except ValueError as exc:
            return _json_error(str(exc), "validation_error", 400)

        system = (
            "You summarize construction project documents for MAXEK ERP users. "
            "Return JSON with keys: summary (string), key_points (array of strings), "
            "action_items (array of strings, may be empty). "
            "Be factual; note uncertainty if content is thin."
        )
        user_prompt = f"Document metadata:\n{json.dumps(meta, indent=2)}\n\nDocument content:\n{content}"
        try:
            raw = chat_completion_json(system, user_prompt, max_tokens=1600)
        except OpenAIConfigurationError as exc:
            return _openai_unavailable_response(exc)
        except ValueError as exc:
            return _json_error(str(exc), "ai_parse_error", 502)
        except Exception:
            return _openai_unavailable_response(Exception("openai failed"))

        return jsonify({
            "summary": raw.get("summary") or "",
            "key_points": raw.get("key_points") or [],
            "action_items": raw.get("action_items") or [],
            "metadata": meta,
        })
