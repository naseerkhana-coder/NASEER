"""Database backup & recovery — scheduled and manual SQLite backups with retention."""

from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime, timedelta
from typing import Any

from treasury_service import log_treasury_audit

BACKUP_TYPES = ("manual", "daily", "weekly", "monthly")
BACKUP_STATUSES = ("completed", "failed", "in_progress")
STORAGE_TARGETS = ("server", "onedrive", "external")

BACKUP_SETTINGS_KEY = "backup_system_prefs"
DEFAULT_BACKUP_PREFS: dict[str, Any] = {
    "daily_enabled": True,
    "weekly_enabled": True,
    "monthly_enabled": True,
    "retention_daily": 7,
    "retention_weekly": 4,
    "retention_monthly": 12,
    "onedrive_enabled": False,
    "external_enabled": False,
    "onedrive_path": "",
    "external_path": "",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "database", "backups")


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _backup_filename() -> str:
    return datetime.now().strftime("maxek_backup_%Y%m%d_%H%M%S.db")


def _ensure_app_settings_table(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings(
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )
        """
    )


def _get_app_setting(db, key: str, default: Any = None) -> Any:
    _ensure_app_settings_table(db)
    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key=?",
        (key,),
    ).fetchone()
    if not row or row["setting_value"] is None:
        return default
    return row["setting_value"]


def _set_app_setting(db, key: str, value: str) -> None:
    _ensure_app_settings_table(db)
    db.execute(
        "INSERT INTO app_settings(setting_key, setting_value) VALUES(?,?) "
        "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
        (key, value),
    )


def ensure_backup_schema(db) -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backup_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'completed',
            storage_target TEXT DEFAULT 'server',
            created_at TEXT NOT NULL,
            created_by TEXT,
            notes TEXT
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_backup_runs_type ON backup_runs(backup_type)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_backup_runs_created ON backup_runs(created_at)"
    )


def get_backup_settings(db) -> dict[str, Any]:
    raw = _get_app_setting(db, BACKUP_SETTINGS_KEY)
    if not raw:
        prefs = dict(DEFAULT_BACKUP_PREFS)
        _set_app_setting(db, BACKUP_SETTINGS_KEY, json.dumps(prefs))
        return prefs
    try:
        data = json.loads(raw)
        merged = dict(DEFAULT_BACKUP_PREFS)
        merged.update({k: data[k] for k in data if k in merged or k in data})
        return merged
    except (TypeError, json.JSONDecodeError):
        return dict(DEFAULT_BACKUP_PREFS)


def save_backup_settings(db, prefs: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_BACKUP_PREFS)
    for key in DEFAULT_BACKUP_PREFS:
        if key in prefs:
            merged[key] = prefs[key]
    for int_key in ("retention_daily", "retention_weekly", "retention_monthly"):
        try:
            merged[int_key] = max(1, int(merged.get(int_key) or DEFAULT_BACKUP_PREFS[int_key]))
        except (TypeError, ValueError):
            merged[int_key] = DEFAULT_BACKUP_PREFS[int_key]
    for bool_key in (
        "daily_enabled",
        "weekly_enabled",
        "monthly_enabled",
        "onedrive_enabled",
        "external_enabled",
    ):
        merged[bool_key] = bool(merged.get(bool_key))
    for path_key in ("onedrive_path", "external_path"):
        merged[path_key] = str(merged.get(path_key) or "").strip()
    _set_app_setting(db, BACKUP_SETTINGS_KEY, json.dumps(merged))
    return merged


def _resolve_storage_targets(prefs: dict[str, Any]) -> list[str]:
    targets = ["server"]
    if prefs.get("onedrive_enabled"):
        targets.append("onedrive")
    if prefs.get("external_enabled"):
        targets.append("external")
    return targets


def _stub_copy_to_target(
    source_path: str,
    target: str,
    prefs: dict[str, Any],
) -> str | None:
    """Stub for OneDrive / external storage — logs path only, no remote copy."""
    if target == "server":
        return None
    if target == "onedrive":
        stub_path = (prefs.get("onedrive_path") or "").strip() or "(OneDrive not configured)"
        return f"OneDrive stub: {stub_path}"
    if target == "external":
        stub_path = (prefs.get("external_path") or "").strip() or "(External path not configured)"
        return f"External stub: {stub_path}"
    return None


def create_backup(
    db,
    db_path: str,
    *,
    backup_type: str = "manual",
    created_by: str = "",
    notes: str = "",
    storage_target: str = "server",
) -> dict[str, Any]:
    ensure_backup_schema(db)
    btype = (backup_type or "manual").strip().lower()
    if btype not in BACKUP_TYPES:
        raise ValueError(f"Invalid backup type: {backup_type}")

    if not os.path.isfile(db_path):
        raise ValueError("Database file not found.")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    filename = _backup_filename()
    dest_path = os.path.join(BACKUP_DIR, filename)
    ts = _now_ts()

    db.execute(
        """
        INSERT INTO backup_runs(
            backup_type, file_path, file_size, status, storage_target,
            created_at, created_by, notes
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (btype, dest_path, 0, "in_progress", storage_target, ts, created_by, notes),
    )
    run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        shutil.copy2(db_path, dest_path)
        file_size = os.path.getsize(dest_path)
        db.execute(
            "UPDATE backup_runs SET file_size=?, status=? WHERE id=?",
            (file_size, "completed", run_id),
        )
        log_treasury_audit(
            db,
            "backup_run",
            run_id,
            "backup_created",
            created_by,
            f"{btype} backup — {filename} ({file_size} bytes)",
        )
        db.commit()
        return get_backup_info(db, run_id) or {}
    except OSError as exc:
        db.execute(
            "UPDATE backup_runs SET status=?, notes=? WHERE id=?",
            ("failed", f"{notes} | Error: {exc}".strip(" |"), run_id),
        )
        db.commit()
        raise ValueError(f"Backup failed: {exc}") from exc


def list_backups(db, limit: int = 100) -> list[dict[str, Any]]:
    ensure_backup_schema(db)
    rows = db.execute(
        """
        SELECT * FROM backup_runs
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (max(1, limit),),
    ).fetchall()
    return [_serialize_backup(row) for row in rows]


def get_backup_info(db, backup_id: int) -> dict[str, Any] | None:
    ensure_backup_schema(db)
    row = db.execute(
        "SELECT * FROM backup_runs WHERE id=?",
        (backup_id,),
    ).fetchone()
    if not row:
        return None
    return _serialize_backup(row)


def _serialize_backup(row) -> dict[str, Any]:
    data = dict(row)
    path = data.get("file_path") or ""
    data["filename"] = os.path.basename(path) if path else ""
    data["file_exists"] = bool(path and os.path.isfile(path))
    size = int(data.get("file_size") or 0)
    if size <= 0 and data["file_exists"]:
        try:
            size = os.path.getsize(path)
            data["file_size"] = size
        except OSError:
            pass
    data["file_size_mb"] = round(size / (1024 * 1024), 2) if size else 0.0
    return data


def delete_backup(db, backup_id: int, actor: str = "") -> bool:
    ensure_backup_schema(db)
    row = db.execute(
        "SELECT * FROM backup_runs WHERE id=?",
        (backup_id,),
    ).fetchone()
    if not row:
        return False
    path = row["file_path"]
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
    db.execute("DELETE FROM backup_runs WHERE id=?", (backup_id,))
    log_treasury_audit(
        db,
        "backup_run",
        backup_id,
        "backup_deleted",
        actor,
        f"Deleted {os.path.basename(path or '')}",
    )
    db.commit()
    return True


def restore_backup(
    db,
    backup_id: int,
    db_path: str,
    *,
    actor: str = "",
) -> dict[str, Any]:
    ensure_backup_schema(db)
    info = get_backup_info(db, backup_id)
    if not info:
        raise ValueError("Backup not found.")
    if info.get("status") != "completed":
        raise ValueError("Only completed backups can be restored.")
    backup_path = info.get("file_path") or ""
    if not backup_path or not os.path.isfile(backup_path):
        raise ValueError("Backup file is missing on disk.")

    safety = create_backup(
        db,
        db_path,
        backup_type="manual",
        created_by=actor,
        notes=f"Pre-restore safety backup before restore #{backup_id}",
    )

    try:
        shutil.copy2(backup_path, db_path)
    except OSError as exc:
        raise ValueError(f"Restore failed: {exc}") from exc

    log_treasury_audit(
        db,
        "backup_run",
        backup_id,
        "backup_restored",
        actor,
        f"Restored from {info.get('filename')} — safety backup #{safety.get('id')}",
    )
    db.commit()
    return {
        "restored_from": info,
        "safety_backup": safety,
    }


def _last_backup_of_type(db, backup_type: str) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT * FROM backup_runs
        WHERE backup_type=? AND status='completed'
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 1
        """,
        (backup_type,),
    ).fetchone()
    return dict(row) if row else None


def _parse_created_at(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except ValueError:
            continue
    return None


def _is_daily_due(last: dict[str, Any] | None, today: date) -> bool:
    if not last:
        return True
    created = _parse_created_at(last.get("created_at"))
    if not created:
        return True
    return created.date() < today


def _is_weekly_due(last: dict[str, Any] | None, today: date) -> bool:
    if not last:
        return True
    created = _parse_created_at(last.get("created_at"))
    if not created:
        return True
    return (today - created.date()).days >= 7


def _is_monthly_due(last: dict[str, Any] | None, today: date) -> bool:
    if not last:
        return True
    created = _parse_created_at(last.get("created_at"))
    if not created:
        return True
    return (created.year, created.month) < (today.year, today.month)


def apply_retention_policy(db, prefs: dict[str, Any] | None = None) -> int:
    """Delete backups beyond retention limits per type. Returns count removed."""
    ensure_backup_schema(db)
    prefs = prefs or get_backup_settings(db)
    limits = {
        "daily": int(prefs.get("retention_daily") or 7),
        "weekly": int(prefs.get("retention_weekly") or 4),
        "monthly": int(prefs.get("retention_monthly") or 12),
    }
    removed = 0
    for btype, keep in limits.items():
        rows = db.execute(
            """
            SELECT id FROM backup_runs
            WHERE backup_type=? AND status='completed'
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (btype,),
        ).fetchall()
        for row in rows[keep:]:
            if delete_backup(db, row["id"], actor="system"):
                removed += 1
    return removed


def run_scheduled_backup_if_due(db, db_path: str, actor: str = "system") -> dict[str, Any]:
    """Create daily/weekly/monthly backups when schedules are due."""
    ensure_backup_schema(db)
    prefs = get_backup_settings(db)
    today = date.today()
    result: dict[str, Any] = {"created": [], "skipped": [], "retention_removed": 0}

    schedule = (
        ("daily", prefs.get("daily_enabled", True), _is_daily_due),
        ("weekly", prefs.get("weekly_enabled", True), _is_weekly_due),
        ("monthly", prefs.get("monthly_enabled", True), _is_monthly_due),
    )
    for btype, enabled, due_fn in schedule:
        if not enabled:
            result["skipped"].append(btype)
            continue
        last = _last_backup_of_type(db, btype)
        if not due_fn(last, today):
            result["skipped"].append(btype)
            continue
        stub_notes = [
            note
            for target in _resolve_storage_targets(prefs)
            if target != "server"
            for note in [_stub_copy_to_target("", target, prefs)]
            if note
        ]
        backup = create_backup(
            db,
            db_path,
            backup_type=btype,
            created_by=actor,
            notes="; ".join(stub_notes),
            storage_target="server",
        )
        result["created"].append({"type": btype, "id": backup.get("id")})

    result["retention_removed"] = apply_retention_policy(db, prefs)
    return result


def get_backup_dashboard_stats(db) -> dict[str, Any]:
    ensure_backup_schema(db)
    prefs = get_backup_settings(db)
    backups = list_backups(db, limit=500)
    total_size = sum(int(b.get("file_size") or 0) for b in backups)
    completed = [b for b in backups if b.get("status") == "completed"]
    last_runs: dict[str, dict[str, Any] | None] = {}
    for btype in ("manual", "daily", "weekly", "monthly"):
        row = _last_backup_of_type(db, btype)
        last_runs[btype] = _serialize_backup(row) if row else None

    return {
        "total_backups": len(backups),
        "completed_backups": len(completed),
        "total_size": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "last_runs": last_runs,
        "settings": prefs,
        "backup_dir": BACKUP_DIR,
    }
