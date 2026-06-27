"""Flask routes for MAXEK ERP Super Admin / platform administration."""

import logging
import os
import sqlite3
import time

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from super_admin_service import (
    CHANGE_REQUEST_STATUSES,
    CUSTOMER_PLANS,
    CUSTOMER_STATUSES,
    DEPARTMENT_PORTAL_SLUGS,
    DEPARTMENT_SLUG_LABELS,
    ERP_ADMIN_SUBTOOLBAR,
    ERP_ADMIN_SUBTOOLBAR_SECTIONS,
    LICENSE_PRODUCTS,
    LICENSE_STATUSES,
    PRIORITY_LEVELS,
    SUBSCRIPTION_STATUSES,
    TICKET_STATUSES,
    create_customer_admin_user,
    get_customer_enabled_departments,
    get_platform_dashboard_data,
    get_system_health,
    list_audit_logs,
    list_branch_limits,
    list_change_requests,
    list_customer_packages,
    list_customers,
    list_erp_settings,
    list_licenses,
    list_storage_limits,
    list_subscriptions,
    list_support_tickets,
    list_user_limits,
    next_customer_code,
    save_change_request,
    save_customer,
    save_erp_setting,
    save_license,
    save_subscription,
    save_support_ticket,
    sync_customer_usage_counts,
    update_branch_limit,
    update_storage_limit,
    update_user_limit,
    ensure_super_admin_schema,
    backfill_customer_limit_rows,
)
from company_master_service import COMPANY_COUNTRIES

logger = logging.getLogger(__name__)


def _customer_codes(db):
    rows = db.execute(
        "SELECT customer_code FROM erp_customers "
        "WHERE COALESCE(is_platform, 0)=0 ORDER BY customer_code"
    ).fetchall()
    return [row["customer_code"] for row in rows]


def _prepare_support_upload(file_storage, uploads_dir):
    if not file_storage or not file_storage.filename:
        return None
    os.makedirs(uploads_dir, exist_ok=True)
    filename = secure_filename(file_storage.filename)
    saved = f"{int(time.time())}_{filename}"
    file_storage.save(os.path.join(uploads_dir, saved))
    return saved


def _prepare_limits_page(db):
    """Schema + limit rows for legacy production DBs before limits screens."""
    ensure_super_admin_schema(db)
    backfill_customer_limit_rows(db)
    db.commit()


def _render_limits_page(db, *, limit_type, limit_title, table_headers, table_rows, plans=None):
    return render_template(
        "erp_admin/limits.html",
        limit_type=limit_type,
        limit_title=limit_title,
        table_headers=table_headers,
        rows=table_rows,
        customer_codes=_customer_codes(db),
        plans=plans,
        sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
    )


def register_erp_admin_routes(
    app,
    *,
    login_required,
    super_admin_required,
    get_db,
    is_super_admin_user,
    get_login_report,
    db_path,
    support_uploads_dir,
    hash_password,
):
    @app.route("/super-admin/dashboard")
    @login_required
    @super_admin_required
    def super_admin_platform_dashboard():
        db = get_db()
        platform_data = get_platform_dashboard_data(db)
        quick_links = [
            {
                "endpoint": "erp_admin_customers",
                "label": "Customer Master",
                "icon": "fa-building-user",
                "description": "Register tenants and onboard first admin accounts",
            },
            {
                "endpoint": "erp_admin_licenses",
                "label": "License Master",
                "icon": "fa-key",
                "description": "Issue and renew product licenses",
            },
            {
                "endpoint": "user_management",
                "label": "User Management",
                "icon": "fa-user-shield",
                "description": "Manage platform and tenant login accounts",
            },
            {
                "endpoint": "erp_admin_user_limits",
                "label": "User Limits",
                "icon": "fa-users-gear",
                "description": "Adjust licensed user capacity per customer",
            },
            {
                "endpoint": "erp_admin_subscriptions",
                "label": "Subscriptions",
                "icon": "fa-credit-card",
                "description": "Billing plans and renewal dates",
            },
            {
                "endpoint": "erp_admin_system_health",
                "label": "System Health",
                "icon": "fa-heart-pulse",
                "description": "Database size and platform status checks",
            },
        ]
        return render_template(
            "erp_admin/platform_dashboard.html",
            platform_data=platform_data,
            quick_links=quick_links,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/customers", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_customers():
        db = get_db()
        ensure_super_admin_schema(db)
        db.commit()
        packages = list_customer_packages(db)
        package_defaults = {
            pkg["package_code"]: pkg.get("default_department_slugs") or []
            for pkg in packages
        }
        edit_id = request.args.get("edit", type=int)
        edit_record = None
        selected_departments: list[str] = []
        if edit_id:
            row = db.execute(
                "SELECT * FROM erp_customers WHERE id=? AND is_platform=0", (edit_id,)
            ).fetchone()
            edit_record = dict(row) if row else None
            if edit_record:
                selected_departments = get_customer_enabled_departments(db, edit_id)
        if request.method == "POST":
            try:
                record_id = request.form.get("record_id", type=int)
                admin_username = request.form.get("admin_username", "").strip()
                admin_password = request.form.get("admin_password", "").strip()
                if not record_id and admin_password and not admin_username:
                    raise ValueError("Admin username is required when setting a password.")
                form_data = request.form.to_dict(flat=True)
                form_data["enabled_departments"] = request.form.getlist("enabled_departments")
                customer_id = save_customer(db, form_data, record_id=record_id)
                if not record_id and admin_username:
                    create_customer_admin_user(
                        db,
                        customer_id,
                        username=admin_username,
                        password=request.form.get("admin_password", ""),
                        confirm_password=request.form.get("admin_confirm_password", ""),
                        display_name=request.form.get("admin_display_name", ""),
                        hash_password_fn=hash_password,
                    )
                    flash("Customer and first admin account created successfully.")
                else:
                    flash("Customer saved successfully.")
                db.commit()
                return redirect(url_for("erp_admin_customers"))
            except ValueError as exc:
                db.rollback()
                flash(str(exc))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("Username already exists for this customer. Choose a different login ID.")
        search = request.args.get("q", "")
        rows = list_customers(db, search=search)
        for row in rows:
            row["enabled_department_count"] = len(
                get_customer_enabled_departments(db, row["id"])
            )
        return render_template(
            "erp_admin/customers.html",
            rows=rows,
            edit_record=edit_record,
            search=search,
            next_customer_code=next_customer_code(db),
            countries=COMPANY_COUNTRIES,
            plans=CUSTOMER_PLANS,
            packages=packages,
            package_defaults=package_defaults,
            department_slugs=DEPARTMENT_PORTAL_SLUGS,
            department_labels=DEPARTMENT_SLUG_LABELS,
            selected_departments=selected_departments,
            statuses=CUSTOMER_STATUSES,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
                sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/licenses", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_licenses():
        db = get_db()
        try:
            ensure_super_admin_schema(db)
            db.commit()
        except Exception:
            logger.exception("erp_admin_licenses schema ensure failed")
        if request.method == "POST":
            try:
                save_license(db, request.form)
                db.commit()
                flash("License saved successfully.")
                return redirect(url_for("erp_admin_licenses"))
            except ValueError as exc:
                db.rollback()
                flash(str(exc))
            except (sqlite3.Error, KeyError, TypeError):
                db.rollback()
                logger.exception("erp_admin_licenses save failed")
                flash(
                    "Unable to save license. "
                    "If this persists after deploy, check server logs (journalctl -u maxek-erp)."
                )
        return render_template(
            "erp_admin/licenses.html",
            rows=list_licenses(db),
            customer_codes=_customer_codes(db),
            products=LICENSE_PRODUCTS,
            plans=CUSTOMER_PLANS,
            statuses=LICENSE_STATUSES,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/subscriptions", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_subscriptions():
        db = get_db()
        if request.method == "POST":
            try:
                save_subscription(db, request.form)
                db.commit()
                flash("Subscription saved.")
                return redirect(url_for("erp_admin_subscriptions"))
            except ValueError as exc:
                flash(str(exc))
        return render_template(
            "erp_admin/subscriptions.html",
            rows=list_subscriptions(db),
            customer_codes=_customer_codes(db),
            plans=CUSTOMER_PLANS,
            statuses=SUBSCRIPTION_STATUSES,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/user-limits", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_user_limits():
        db = get_db()
        try:
            _prepare_limits_page(db)
            if request.method == "POST" and request.form.get("form_action") == "update_user":
                try:
                    update_user_limit(
                        db,
                        request.form.get("customer_code", ""),
                        int(request.form.get("users_allowed") or 0),
                        request.form.get("plan", ""),
                    )
                    db.commit()
                    flash("User limits updated.")
                except ValueError as exc:
                    flash(str(exc))
                return redirect(url_for("erp_admin_user_limits"))
            for row in list_user_limits(db):
                sync_customer_usage_counts(db, row["customer_id"])
            db.commit()
            rows = list_user_limits(db)
            table_rows = [
                {
                    "values": [
                        r.get("customer_code", ""),
                        r.get("company_name", ""),
                        r.get("plan") or r.get("customer_plan") or "Standard",
                        r.get("users_allowed", 0),
                        r.get("current_users", 0),
                    ]
                }
                for r in rows
            ]
            return _render_limits_page(
                db,
                limit_type="user",
                limit_title="User Limits",
                table_headers=["Customer", "Company", "Plan", "Allowed", "Current"],
                table_rows=table_rows,
                plans=CUSTOMER_PLANS,
            )
        except Exception:
            logger.exception("erp_admin_user_limits failed")
            flash("Unable to load User Limits. Check server logs for details.")
            return redirect(url_for("erp_admin_customers"))

    @app.route("/erp-admin/branch-limits", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_branch_limits():
        db = get_db()
        try:
            _prepare_limits_page(db)
            if request.method == "POST" and request.form.get("form_action") == "update_branch":
                try:
                    update_branch_limit(
                        db,
                        request.form.get("customer_code", ""),
                        int(request.form.get("branches_allowed") or 0),
                    )
                    db.commit()
                    flash("Branch limits updated.")
                except ValueError as exc:
                    flash(str(exc))
                return redirect(url_for("erp_admin_branch_limits"))
            for row in list_branch_limits(db):
                sync_customer_usage_counts(db, row["customer_id"])
            db.commit()
            rows = list_branch_limits(db)
            table_rows = [
                {
                    "values": [
                        r.get("customer_code", ""),
                        r.get("company_name", ""),
                        r.get("branches_allowed", 0),
                        r.get("current_branches", 0),
                    ]
                }
                for r in rows
            ]
            return _render_limits_page(
                db,
                limit_type="branch",
                limit_title="Branch Limits",
                table_headers=["Customer", "Company", "Allowed", "Current"],
                table_rows=table_rows,
            )
        except Exception:
            logger.exception("erp_admin_branch_limits failed")
            flash("Unable to load Branch Limits. Check server logs for details.")
            return redirect(url_for("erp_admin_customers"))

    @app.route("/erp-admin/storage-limits", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_storage_limits():
        db = get_db()
        try:
            _prepare_limits_page(db)
            if request.method == "POST" and request.form.get("form_action") == "update_storage":
                try:
                    update_storage_limit(
                        db,
                        request.form.get("customer_code", ""),
                        int(request.form.get("storage_allowed_mb") or 0),
                    )
                    db.commit()
                    flash("Storage limits updated.")
                except ValueError as exc:
                    flash(str(exc))
                return redirect(url_for("erp_admin_storage_limits"))
            rows = list_storage_limits(db)
            table_rows = [
                {
                    "values": [
                        r.get("customer_code", ""),
                        r.get("company_name", ""),
                        r.get("storage_allowed_mb", 0),
                        r.get("current_usage_mb", 0),
                    ]
                }
                for r in rows
            ]
            return _render_limits_page(
                db,
                limit_type="storage",
                limit_title="Storage Limits",
                table_headers=["Customer", "Company", "Allowed (MB)", "Used (MB)"],
                table_rows=table_rows,
            )
        except Exception:
            logger.exception("erp_admin_storage_limits failed")
            flash("Unable to load Storage Limits. Check server logs for details.")
            return redirect(url_for("erp_admin_customers"))

    @app.route("/erp-admin/login-monitoring")
    @login_required
    @super_admin_required
    def erp_admin_login_monitoring():
        db = get_db()
        date_from = request.args.get("from_date", "").strip() or None
        date_to = request.args.get("to_date", "").strip() or None
        login_rows = get_login_report(db, date_from=date_from, date_to=date_to)
        return render_template(
            "erp_admin/login_monitoring.html",
            login_rows=login_rows,
            date_from=date_from,
            date_to=date_to,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/support-tickets", methods=["GET", "POST"])
    @login_required
    def erp_admin_support_tickets():
        db = get_db()
        super_admin = is_super_admin_user()
        customer_id = session.get("customer_id")
        if not super_admin and not customer_id:
            flash("Support tickets require a tenant account.")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            screenshot = _prepare_support_upload(request.files.get("screenshot"), support_uploads_dir)
            try:
                save_support_ticket(
                    db,
                    request.form,
                    screenshot_path=screenshot,
                    customer_id=None if super_admin else customer_id,
                )
                db.commit()
                flash("Support ticket submitted.")
                return redirect(url_for("erp_admin_support_tickets"))
            except ValueError as exc:
                flash(str(exc))
        tickets = list_support_tickets(
            db,
            customer_id=None if super_admin else customer_id,
        )
        return render_template(
            "erp_admin/support_tickets.html",
            rows=tickets,
            customer_codes=_customer_codes(db) if super_admin else [],
            priorities=PRIORITY_LEVELS,
            statuses=TICKET_STATUSES,
            is_super_admin=super_admin,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR if super_admin else None,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS if super_admin else None,
        )

    @app.route("/erp-admin/change-requests", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_change_requests():
        db = get_db()
        if request.method == "POST":
            data = dict(request.form)
            data["created_by"] = session.get("username")
            try:
                save_change_request(db, data)
                db.commit()
                flash("Change request saved.")
                return redirect(url_for("erp_admin_change_requests"))
            except ValueError as exc:
                flash(str(exc))
        return render_template(
            "erp_admin/change_requests.html",
            rows=list_change_requests(db),
            customer_codes=_customer_codes(db),
            priorities=PRIORITY_LEVELS,
            statuses=CHANGE_REQUEST_STATUSES,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/settings", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_settings():
        db = get_db()
        if request.method == "POST":
            save_erp_setting(
                db,
                request.form.get("setting_key", "").strip(),
                request.form.get("setting_value", "").strip(),
                request.form.get("category", "General").strip(),
                request.form.get("description", "").strip(),
            )
            db.commit()
            flash("Setting saved.")
            return redirect(url_for("erp_admin_settings"))
        return render_template(
            "erp_admin/settings.html",
            rows=list_erp_settings(db),
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/audit-logs")
    @login_required
    @super_admin_required
    def erp_admin_audit_logs():
        db = get_db()
        return render_template(
            "erp_admin/audit_logs.html",
            rows=list_audit_logs(db),
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/system-health")
    @login_required
    @super_admin_required
    def erp_admin_system_health():
        db = get_db()
        health = get_system_health(db, db_path)
        return render_template(
            "erp_admin/system_health.html",
            health=health,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/support/tickets", methods=["GET", "POST"])
    @login_required
    def customer_support_tickets():
        if is_super_admin_user():
            return redirect(url_for("erp_admin_support_tickets"))
        return erp_admin_support_tickets()
