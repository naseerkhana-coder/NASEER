"""JWT authentication helpers for SmartQTO / MAXEK ERP REST APIs."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable

import jwt
from flask import current_app, g, jsonify, request

ACCESS_TOKEN_MINUTES = int(os.environ.get("MAXEK_JWT_ACCESS_MINUTES", "60"))
REFRESH_TOKEN_DAYS = int(os.environ.get("MAXEK_JWT_REFRESH_DAYS", "7"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_jwt_secret(app=None) -> str:
    app = app or current_app
    return (
        os.environ.get("MAXEK_JWT_SECRET")
        or os.environ.get("JWT_SECRET")
        or app.config.get("JWT_SECRET_KEY")
        or app.secret_key
    )


def ensure_jwt_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS jwt_token_blocklist(
            jti TEXT PRIMARY KEY,
            token_type TEXT,
            user_id INTEGER,
            expires_at TEXT NOT NULL,
            revoked_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_jwt_blocklist_expires ON jwt_token_blocklist(expires_at)"
    )


def _now_iso() -> str:
    return _utcnow().strftime("%Y-%m-%d %H:%M:%S")


def build_token_claims(
    *,
    user_id: int,
    username: str,
    role: str,
    customer_id: int | None,
    company_code: str | None,
    token_type: str,
    expires_delta: timedelta,
) -> dict[str, Any]:
    now = _utcnow()
    exp = now + expires_delta
    return {
        "sub": str(user_id),
        "username": username,
        "role": role or "User",
        "customer_id": customer_id,
        "company_code": (company_code or "").upper() or None,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }


def create_access_token(app, *, user_id, username, role, customer_id, company_code) -> str:
    claims = build_token_claims(
        user_id=user_id,
        username=username,
        role=role,
        customer_id=customer_id,
        company_code=company_code,
        token_type="access",
        expires_delta=timedelta(minutes=ACCESS_TOKEN_MINUTES),
    )
    return jwt.encode(claims, get_jwt_secret(app), algorithm="HS256")


def create_refresh_token(app, *, user_id, username, role, customer_id, company_code) -> str:
    claims = build_token_claims(
        user_id=user_id,
        username=username,
        role=role,
        customer_id=customer_id,
        company_code=company_code,
        token_type="refresh",
        expires_delta=timedelta(days=REFRESH_TOKEN_DAYS),
    )
    return jwt.encode(claims, get_jwt_secret(app), algorithm="HS256")


def decode_token(app, token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        get_jwt_secret(app),
        algorithms=["HS256"],
        options={"require": ["exp", "sub", "jti", "type"]},
    )
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected {expected_type} token")
    return payload


def is_token_revoked(db, jti: str) -> bool:
    row = db.execute(
        "SELECT jti FROM jwt_token_blocklist WHERE jti=?",
        (jti,),
    ).fetchone()
    return row is not None


def revoke_token(db, payload: dict[str, Any]) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    db.execute(
        "INSERT OR IGNORE INTO jwt_token_blocklist(jti, token_type, user_id, expires_at, revoked_at) "
        "VALUES(?,?,?,?,?)",
        (
            jti,
            payload.get("type"),
            int(payload.get("sub") or 0) or None,
            expires_at,
            _now_iso(),
        ),
    )


def extract_bearer_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def jwt_required(*, token_type: str = "access", roles: tuple[str, ...] | None = None):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            get_db_fn = current_app.config.get("GET_DB")
            if not get_db_fn:
                return jsonify({"error": "Server misconfigured", "code": "server_error"}), 500

            token = extract_bearer_token()
            if not token:
                return jsonify({"error": "Authorization required", "code": "auth_required"}), 401
            try:
                payload = decode_token(current_app, token, expected_type=token_type)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired", "code": "token_expired"}), 401
            except jwt.InvalidTokenError as exc:
                return jsonify({"error": str(exc), "code": "invalid_token"}), 401

            db = get_db_fn()
            if is_token_revoked(db, payload.get("jti", "")):
                return jsonify({"error": "Token revoked", "code": "token_revoked"}), 401

            g.jwt_payload = payload
            g.api_user_id = int(payload["sub"])
            g.api_username = payload.get("username")
            g.api_role = payload.get("role")
            g.api_customer_id = payload.get("customer_id")
            g.api_company_code = payload.get("company_code")

            if roles:
                role_norm = (g.api_role or "").strip().lower()
                allowed = {r.lower() for r in roles}
                if role_norm not in allowed:
                    return jsonify({"error": "Forbidden", "code": "forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def api_super_admin_required(fn: Callable):
    return jwt_required(roles=("Super Admin", "superadmin", "super admin"))(fn)
