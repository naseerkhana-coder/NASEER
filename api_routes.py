"""REST API routes for SmartQTO integration."""

from __future__ import annotations

from typing import Any

import jwt
from flask import current_app, g, jsonify, request

from auth_jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    ensure_jwt_schema,
    extract_bearer_token,
    jwt_required,
    revoke_token,
)
from super_admin_service import (
    assert_branch_limit_not_exceeded,
    assert_user_limit_not_exceeded,
    get_customer_by_code,
    get_customer_by_id,
    is_super_admin_user,
    is_platform_super_admin,
    list_customers,
    list_licenses,
    log_audit,
    save_customer,
    save_license,
    sync_customer_usage_counts,
)


def _json_error(message: str, code: str, status: int = 400):
    return jsonify({"error": message, "code": code}), status


def _serialize_customer(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "customer_code": row.get("customer_code"),
        "company_name": row.get("company_name"),
        "country": row.get("country"),
        "contact_person": row.get("contact_person"),
        "mobile": row.get("mobile"),
        "email": row.get("email"),
        "vat_gst_number": row.get("vat_gst_number"),
        "num_branches": row.get("num_branches"),
        "num_users": row.get("num_users"),
        "plan": row.get("plan"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "modified_at": row.get("modified_at"),
    }


def _serialize_license(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "license_no": row.get("license_no"),
        "customer_id": row.get("customer_id"),
        "customer_code": row.get("customer_code"),
        "company_name": row.get("company_name"),
        "product": row.get("product"),
        "plan": row.get("plan"),
        "start_date": row.get("start_date"),
        "expiry_date": row.get("expiry_date"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "modified_at": row.get("modified_at"),
    }


def _require_super_admin_jwt(db):
    role = (g.api_role or "").strip().lower()
    if role in ("super admin", "superadmin"):
        return None
    user = db.execute("SELECT * FROM users WHERE id=?", (g.api_user_id,)).fetchone()
    if user and is_platform_super_admin(db, user):
        return None
    return _json_error("Super Admin access required", "forbidden", 403)


def register_api_routes(
    app,
    *,
    get_db,
    hash_password,
    verify_password,
    authenticate_user,
    user_is_active,
    get_user_id,
    get_user_display_name,
):
    @app.route("/api/auth/login", methods=["POST"])
    def api_auth_login():
        data = request.get_json(silent=True) or {}
        company_code = (data.get("company_code") or "").strip()
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        if not username or not password:
            return _json_error("company_code, username, and password are required", "validation_error", 422)
        if not company_code:
            return _json_error("company_code is required", "validation_error", 422)

        db = get_db()
        ensure_jwt_schema(db)
        user = authenticate_user(db, username, password, company_code=company_code)
        if not user or not user_is_active(user):
            return _json_error("Invalid credentials or inactive account", "invalid_credentials", 401)

        user_id = get_user_id(user)
        customer_id = user["customer_id"] if "customer_id" in user.keys() else None
        company_code_val = company_code.upper()
        if customer_id:
            customer = get_customer_by_id(db, customer_id)
            if customer:
                company_code_val = customer["customer_code"]

        role = user["role"] if "role" in user.keys() else "User"
        access = create_access_token(
            app,
            user_id=user_id,
            username=user["username"],
            role=role,
            customer_id=customer_id,
            company_code=company_code_val,
        )
        refresh = create_refresh_token(
            app,
            user_id=user_id,
            username=user["username"],
            role=role,
            customer_id=customer_id,
            company_code=company_code_val,
        )
        log_audit(
            db,
            customer_id,
            user_id,
            "API Login",
            "Auth",
            f"JWT login for {username}",
            username=username,
            ip_address=(request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip(),
        )
        db.commit()
        return jsonify(
            {
                "access_token": access,
                "refresh_token": refresh,
                "token_type": "Bearer",
                "user": {
                    "id": user_id,
                    "username": user["username"],
                    "role": role,
                    "customer_id": customer_id,
                    "company_code": company_code_val,
                    "display_name": get_user_display_name(user),
                },
            }
        )

    @app.route("/api/auth/refresh", methods=["POST"])
    def api_auth_refresh():
        data = request.get_json(silent=True) or {}
        refresh_token = (data.get("refresh_token") or extract_bearer_token() or "").strip()
        if not refresh_token:
            return _json_error("refresh_token is required", "validation_error", 422)
        db = get_db()
        ensure_jwt_schema(db)
        try:
            payload = decode_token(app, refresh_token, expected_type="refresh")
        except jwt.ExpiredSignatureError:
            return _json_error("Refresh token expired", "token_expired", 401)
        except jwt.InvalidTokenError as exc:
            return _json_error(str(exc), "invalid_token", 401)

        from auth_jwt import is_token_revoked

        if is_token_revoked(db, payload.get("jti", "")):
            return _json_error("Refresh token revoked", "token_revoked", 401)

        user_id = int(payload["sub"])
        access = create_access_token(
            app,
            user_id=user_id,
            username=payload.get("username", ""),
            role=payload.get("role", "User"),
            customer_id=payload.get("customer_id"),
            company_code=payload.get("company_code"),
        )
        return jsonify({"access_token": access, "token_type": "Bearer"})

    @app.route("/api/auth/logout", methods=["POST"])
    @jwt_required(token_type="access")
    def api_auth_logout():
        db = get_db()
        ensure_jwt_schema(db)
        revoke_token(db, g.jwt_payload)
        refresh = (request.get_json(silent=True) or {}).get("refresh_token")
        if refresh:
            try:
                refresh_payload = decode_token(app, refresh, expected_type="refresh")
                revoke_token(db, refresh_payload)
            except jwt.InvalidTokenError:
                pass
        db.commit()
        return jsonify({"message": "Logged out", "revoked": True})

    @app.route("/api/customers", methods=["GET"])
    @jwt_required()
    def api_list_customers():
        db = get_db()
        forbidden = _require_super_admin_jwt(db)
        if forbidden:
            return forbidden
        search = request.args.get("q", "")
        rows = [_serialize_customer(r) for r in list_customers(db, search=search)]
        return jsonify({"customers": rows, "count": len(rows)})

    @app.route("/api/customers", methods=["POST"])
    @jwt_required()
    def api_create_customer():
        db = get_db()
        forbidden = _require_super_admin_jwt(db)
        if forbidden:
            return forbidden
        data = request.get_json(silent=True) or {}
        try:
            customer_id = save_customer(db, data)
            db.commit()
            row = get_customer_by_id(db, customer_id)
            return jsonify({"customer": _serialize_customer(dict(row))}), 201
        except ValueError as exc:
            return _json_error(str(exc), "validation_error", 422)

    @app.route("/api/customers/<int:customer_id>", methods=["PUT"])
    @jwt_required()
    def api_update_customer(customer_id: int):
        db = get_db()
        forbidden = _require_super_admin_jwt(db)
        if forbidden:
            return forbidden
        existing = get_customer_by_id(db, customer_id)
        if not existing or existing["is_platform"]:
            return _json_error("Customer not found", "not_found", 404)
        data = request.get_json(silent=True) or {}
        try:
            save_customer(db, data, record_id=customer_id)
            db.commit()
            row = get_customer_by_id(db, customer_id)
            return jsonify({"customer": _serialize_customer(dict(row))})
        except ValueError as exc:
            return _json_error(str(exc), "validation_error", 422)

    @app.route("/api/licenses", methods=["GET"])
    @jwt_required()
    def api_list_licenses():
        db = get_db()
        forbidden = _require_super_admin_jwt(db)
        if forbidden:
            return forbidden
        search = request.args.get("q", "")
        rows = [_serialize_license(r) for r in list_licenses(db, search=search)]
        return jsonify({"licenses": rows, "count": len(rows)})

    @app.route("/api/licenses", methods=["POST"])
    @jwt_required()
    def api_create_license():
        db = get_db()
        forbidden = _require_super_admin_jwt(db)
        if forbidden:
            return forbidden
        data = request.get_json(silent=True) or {}
        try:
            license_id = save_license(db, data)
            db.commit()
            row = db.execute(
                """
                SELECT l.*, c.customer_code, c.company_name
                FROM erp_licenses l
                JOIN erp_customers c ON c.id = l.customer_id
                WHERE l.id=?
                """,
                (license_id,),
            ).fetchone()
            return jsonify({"license": _serialize_license(dict(row))}), 201
        except ValueError as exc:
            return _json_error(str(exc), "validation_error", 422)

    @app.route("/api/company", methods=["GET"])
    @jwt_required()
    def api_list_companies():
        db = get_db()
        code = (request.args.get("company_code") or request.args.get("code") or "").strip().upper()
        if code:
            customer = get_customer_by_code(db, code)
            if not customer:
                return _json_error("Company not found", "not_found", 404)
            if customer["is_platform"]:
                forbidden = _require_super_admin_jwt(db)
                if forbidden:
                    return forbidden
            elif g.api_customer_id and customer["id"] != g.api_customer_id:
                forbidden = _require_super_admin_jwt(db)
                if forbidden:
                    return forbidden
            return jsonify({"company": _serialize_customer(dict(customer))})

        forbidden = _require_super_admin_jwt(db)
        if forbidden:
            if g.api_customer_id:
                customer = get_customer_by_id(db, g.api_customer_id)
                if customer:
                    return jsonify(
                        {
                            "companies": [_serialize_customer(dict(customer))],
                            "count": 1,
                        }
                    )
            return forbidden
        rows = [_serialize_customer(r) for r in list_customers(db)]
        return jsonify({"companies": rows, "count": len(rows)})

    @app.route("/api/company", methods=["POST"])
    @jwt_required()
    def api_create_company():
        db = get_db()
        forbidden = _require_super_admin_jwt(db)
        if forbidden:
            return forbidden
        data = request.get_json(silent=True) or {}
        if not data.get("customer_code") and data.get("company_code"):
            data = dict(data)
            data["customer_code"] = data["company_code"]
        try:
            customer_id = save_customer(db, data)
            db.commit()
            row = get_customer_by_id(db, customer_id)
            return jsonify({"company": _serialize_customer(dict(row))}), 201
        except ValueError as exc:
            return _json_error(str(exc), "validation_error", 422)

    @app.route("/api/users", methods=["POST"])
    @jwt_required()
    def api_create_user():
        """Optional API user creation with license enforcement."""
        db = get_db()
        data = request.get_json(silent=True) or {}
        customer_code = (data.get("company_code") or data.get("customer_code") or g.api_company_code or "").strip().upper()
        customer = get_customer_by_code(db, customer_code) if customer_code else None
        if not customer:
            return _json_error("Valid company_code / customer_code required", "validation_error", 422)
        if g.api_customer_id and customer["id"] != g.api_customer_id:
            forbidden = _require_super_admin_jwt(db)
            if forbidden:
                return forbidden
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        if not username or not password:
            return _json_error("username and password are required", "validation_error", 422)
        try:
            assert_user_limit_not_exceeded(db, customer["id"])
        except ValueError as exc:
            return _json_error(str(exc), "limit_exceeded", 403)
        existing = db.execute(
            "SELECT id FROM users WHERE username=? AND customer_id=?",
            (username, customer["id"]),
        ).fetchone()
        if existing:
            return _json_error("Username already exists for this company", "duplicate", 422)
        role = (data.get("role") or "User").strip()
        db.execute(
            "INSERT INTO users(username, password, role, workflow_role, employee_name, status, customer_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                username,
                hash_password(password),
                role,
                data.get("workflow_role") or "Maker",
                data.get("display_name") or username,
                data.get("status") or "Active",
                customer["id"],
            ),
        )
        sync_customer_usage_counts(db, customer["id"])
        db.commit()
        return jsonify({"message": "User created", "username": username, "customer_code": customer_code}), 201
