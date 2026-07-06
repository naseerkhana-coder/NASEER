"""Flask routes for MAXEK ERP Super Admin / platform administration."""

import logging
import os
import sqlite3
import time

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from dashboard_prefs_service import DASHBOARD_THEME_SELECT_OPTIONS
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
    delete_customer,
    delete_license,
    get_customer_by_id,
    get_customer_enabled_departments,
    get_license_handover_details,
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
    next_license_no,
    save_change_request,
    save_customer,
    save_customer_tenant_settings,
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


def _license_customer_options(db):
    rows = db.execute(
        """
        SELECT c.id, c.customer_code, c.company_name, c.contact_person, c.mobile, c.email,
               c.plan, c.package_code, COALESCE(ul.users_allowed, c.num_users, 0) AS users_allowed,
               (
                 SELECT u.username FROM users u
                 WHERE u.customer_id = c.id
                 ORDER BY CASE WHEN u.role IN ('admin', 'super_admin', 'Super Admin') THEN 0 ELSE 1 END, u.id
                 LIMIT 1
               ) AS admin_username
        FROM erp_customers c
        LEFT JOIN erp_user_limits ul ON ul.customer_id = c.id
        WHERE COALESCE(c.is_platform, 0)=0
        ORDER BY c.company_name, c.customer_code
        """
    ).fetchall()
    return [dict(row) for row in rows]


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
    timezone_options=None,
    build_company_erp_section=None,
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
                "endpoint": "erp_admin_system_health",
                "label": "System Health",
                "icon": "fa-heart-pulse",
                "description": "Database size and platform status checks",
            },
            {
                "endpoint": "treasury_backup_system",
                "label": "Backup & Restore",
                "icon": "fa-database",
                "description": "Scheduled backups, download, restore, and retention",
            },
            {
                "endpoint": "erp_admin_audit_logs",
                "label": "Audit Logs",
                "icon": "fa-list-check",
                "description": "Platform-wide audit trail and compliance history",
            },
        ]
        company_erp = None
        if build_company_erp_section:
            try:
                company_erp = build_company_erp_section(db)
            except Exception:
                logging.exception("Failed to build company ERP section for platform dashboard")
        return render_template(
            "erp_admin/platform_dashboard.html",
            platform_data=platform_data,
            quick_links=quick_links,
            company_erp=company_erp,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/customers", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_customers():
        db = get_db()
        try:
            ensure_super_admin_schema(db)
            db.commit()
        except Exception:
            logger.exception("erp_admin_customers schema ensure failed")
        packages = list_customer_packages(db)
        package_defaults = {
            pkg["package_code"]: pkg.get("default_department_slugs") or []
            for pkg in packages
        }
        edit_id = request.args.get("edit", type=int)
        view_only = request.args.get("view") == "1"
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
            form_action = (request.form.get("form_action") or "").strip()
            if form_action == "delete":
                try:
                    record_id = request.form.get("record_id", type=int)
                    if not record_id:
                        raise ValueError("Invalid customer.")
                    cascade = request.form.get("cascade") == "1"
                    delete_customer(db, record_id, cascade=cascade)
                    db.commit()
                    flash("Customer deleted successfully.")
                    return redirect(url_for("erp_admin_customers"))
                except ValueError as exc:
                    db.rollback()
                    flash(str(exc))
                except sqlite3.OperationalError as exc:
                    db.rollback()
                    logger.exception("Customer delete failed (database): %s", exc)
                    flash(
                        "Could not delete customer — database schema may need migration. "
                        "Try again after restart or contact support."
                    )
                except Exception as exc:
                    db.rollback()
                    logger.exception("Customer delete failed: %s", exc)
                    flash(f"Could not delete customer: {exc}")
            else:
                try:
                    record_id = request.form.get("record_id", type=int)
                    admin_username = request.form.get("admin_username", "").strip()
                    admin_password = request.form.get("admin_password", "").strip()
                    admin_email = request.form.get("admin_email", "").strip()
                    admin_mobile = request.form.get("admin_mobile", "").strip()
                    if not record_id:
                        if not admin_username:
                            raise ValueError("Admin username is required for new customers.")
                        if not admin_password:
                            raise ValueError("Admin password is required for new customers.")
                    form_data = request.form.to_dict(flat=True)
                    form_data["enabled_departments"] = request.form.getlist("enabled_departments")
                    customer_id = save_customer(db, form_data, record_id=record_id)
                    if not record_id:
                        create_customer_admin_user(
                            db,
                            customer_id,
                            username=admin_username,
                            password=admin_password,
                            confirm_password=request.form.get("admin_confirm_password", ""),
                            display_name=request.form.get("admin_display_name", ""),
                            email=admin_email,
                            mobile=admin_mobile,
                            hash_password_fn=hash_password,
                        )
                        customer_row = get_customer_by_id(db, customer_id)
                        customer_code = (
                            str(customer_row["customer_code"]).strip()
                            if customer_row and customer_row["customer_code"]
                            else form_data.get("customer_code", "")
                        )
                        session["customer_onboarding_credentials"] = {
                            "username": admin_username,
                            "password": admin_password,
                            "role": "Customer Administrator",
                            "customer_code": customer_code,
                            "company_name": form_data.get("company_name", ""),
                        }
                        flash(
                            "Customer registered. Copy the administrator login credentials "
                            "shown below — the password is displayed once."
                        )
                    else:
                        flash("Customer saved successfully.")
                    db.commit()
                    if not record_id:
                        return redirect(url_for("erp_admin_customers", created=customer_id))
                    return redirect(url_for("erp_admin_customers"))
                except ValueError as exc:
                    db.rollback()
                    flash(str(exc))
                except sqlite3.IntegrityError:
                    db.rollback()
                    flash("Username already exists for this customer. Choose a different login ID.")
                except sqlite3.OperationalError as exc:
                    db.rollback()
                    logger.exception("Customer save failed (database): %s", exc)
                    flash(
                        "Could not save customer — database schema may need migration. "
                        "Try again after restart or contact support."
                    )
                except Exception as exc:
                    db.rollback()
                    logger.exception("Customer save failed: %s", exc)
                    flash(f"Could not save customer: {exc}")
        search = request.args.get("q", "")
        rows = list_customers(db, search=search)
        for row in rows:
            row["enabled_department_count"] = len(
                get_customer_enabled_departments(db, row["id"])
            )
        created_credentials = None
        if request.args.get("created"):
            created_credentials = session.pop("customer_onboarding_credentials", None)
        return render_template(
            "erp_admin/customers.html",
            rows=rows,
            edit_record=edit_record,
            view_only=view_only and bool(edit_record),
            created_credentials=created_credentials,
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
        )

    @app.route("/erp-admin/customers/<int:customer_id>/settings", methods=["GET", "POST"])
    @login_required
    @super_admin_required
    def erp_admin_customer_settings(customer_id):
        db = get_db()
        ensure_super_admin_schema(db)
        db.commit()
        row = get_customer_by_id(db, customer_id)
        if not row:
            flash("Customer not found.")
            return redirect(url_for("erp_admin_customers"))
        customer = dict(row)
        if int(customer.get("is_platform") or 0):
            flash("Platform customer settings are not editable here.")
            return redirect(url_for("erp_admin_customers"))

        logo_upload_dir = os.path.join(app.static_folder or "static", "uploads", "customer_logos")
        tz_options = timezone_options or [
            ("Asia/Kolkata", "Asia/Kolkata (IST)"),
            ("Asia/Dubai", "Asia/Dubai (GST)"),
            ("UTC", "UTC"),
        ]

        if request.method == "POST":
            try:
                logo_path = (customer.get("logo_path") or "").strip()
                logo_file = request.files.get("logo")
                if logo_file and logo_file.filename:
                    os.makedirs(logo_upload_dir, exist_ok=True)
                    safe_name = secure_filename(logo_file.filename)
                    saved = f"{customer_id}_{int(time.time())}_{safe_name}"
                    logo_file.save(os.path.join(logo_upload_dir, saved))
                    logo_path = f"uploads/customer_logos/{saved}"

                save_customer_tenant_settings(
                    db,
                    customer_id,
                    {
                        "company_name": request.form.get("company_name"),
                        "logo_path": logo_path,
                        "theme": request.form.get("theme"),
                        "dashboard_theme": request.form.get("dashboard_theme"),
                        "email_settings": request.form.get("email_settings"),
                    },
                )
                db.commit()
                flash("Customer settings saved.")
                return redirect(url_for("erp_admin_customer_settings", customer_id=customer_id))
            except ValueError as exc:
                db.rollback()
                flash(str(exc))
            except Exception as exc:
                db.rollback()
                logger.exception("Customer settings save failed: %s", exc)
                flash(f"Could not save settings: {exc}")

        row = get_customer_by_id(db, customer_id)
        customer = dict(row) if row else customer
        return render_template(
            "erp_admin/customer_settings.html",
            customer=customer,
            timezone_options=tz_options,
            dashboard_theme_options=DASHBOARD_THEME_SELECT_OPTIONS,
        )

    @app.route("/erp-admin/customers/<int:customer_id>/migration-wizard")
    @login_required
    @super_admin_required
    def erp_admin_migration_wizard(customer_id):
        db = get_db()
        ensure_super_admin_schema(db)
        row = get_customer_by_id(db, customer_id)
        if not row:
            flash("Customer not found.")
            return redirect(url_for("erp_admin_customers"))
        customer = dict(row)
        if int(customer.get("is_platform") or 0):
            flash("Platform customer has no migration wizard.")
            return redirect(url_for("erp_admin_customers"))

        step_num = request.args.get("step", type=int) or 1
        step_num = max(1, min(6, step_num))
        base = url_for("erp_admin_migration_wizard", customer_id=customer_id)

        steps = [
            {"number": 1, "label": "Company Details", "url": f"{base}?step=1", "active": step_num == 1, "disabled": False},
            {"number": 2, "label": "Admin User", "url": f"{base}?step=2", "active": step_num == 2, "disabled": False},
            {"number": 3, "label": "Import Masters", "url": f"{base}?step=3", "active": step_num == 3, "disabled": False},
            {"number": 4, "label": "Import Transactions", "url": f"{base}?step=4", "active": step_num == 4, "disabled": False},
            {"number": 5, "label": "Validation", "url": f"{base}?step=5", "active": step_num == 5, "disabled": False},
            {"number": 6, "label": "Finish", "url": f"{base}?step=6", "active": step_num == 6, "disabled": False},
        ]

        tpl = lambda key: url_for("bulk_import_template", module_key=key)

        if step_num == 1:
            step_title = "Step 1 — Company Details"
            step_content = (
                f'<p>Configure legal entity, branches, GST/PAN, and bank details in '
                f'<strong>Company Master</strong> after the tenant admin logs in.</p>'
                f'<p>Branding for this customer: '
                f'<a href="{url_for("erp_admin_customer_settings", customer_id=customer_id)}">Customer Settings</a></p>'
                f'<p class="erp-hint">Existing onboarding flow — company registration lives in the tenant ERP.</p>'
            )
        elif step_num == 2:
            step_title = "Step 2 — Create Admin User"
            step_content = (
                "<p>First administrator is created during customer registration on Customer Master.</p>"
                f'<p><a href="{url_for("erp_admin_customers", edit=customer_id)}">Edit customer</a> to review admin account.</p>'
            )
        elif step_num == 3:
            step_title = "Step 3 — Import Masters"
            step_content = (
                "<p>Download templates and import master data. BOQ and materials are wired in Phase A/B.</p>"
                "<ul>"
                f'<li><a href="{tpl("boq")}">BOQ lines template</a> — validate &amp; save via '
                f'<a href="{url_for("boq_management")}">BOQ Management → Import</a></li>'
                f'<li><a href="{tpl("customers")}">Customers template</a> — '
                f'<a href="{url_for("data_import_module", module_key="customers")}">Import hub</a> (validate + save)</li>'
                f'<li><a href="{tpl("vendors")}">Vendors template</a> — '
                f'<a href="{url_for("data_import_module", module_key="vendors")}">Import hub</a> (validate + save)</li>'
                f'<li><a href="{tpl("materials")}">Materials template</a> — '
                f'<a href="{url_for("store_materials")}">Material Master</a> (validate + save)</li>'
                f'<li><a href="{tpl("employees")}">Employees template</a> — validate only (save Phase 2)</li>'
                f'<li><a href="{url_for("boq_library")}">Standard BOQ Library</a> — maintain reusable items</li>'
                "</ul>"
            )
        elif step_num == 4:
            step_title = "Step 4 — Import Transactions"
            step_content = (
                "<p>Historical transactions migration.</p>"
                "<ul>"
                f'<li><strong>BOQ</strong> — use Excel import on BOQ Management (full workflow)</li>'
                f'<li><strong>Sales / Purchase / Payments</strong> — Phase 2 (stubs documented)</li>'
                f'<li><strong>Bank statement CSV/xlsx</strong> — Phase 2 reconciliation module</li>'
                "</ul>"
            )
        elif step_num == 5:
            step_title = "Step 5 — Validation Summary"
            step_content = (
                "<p>After imports, verify totals and workflow status in each module.</p>"
                "<ul>"
                "<li>BOQ: pending checker approval on imported masters</li>"
                "<li>Materials: spot-check codes and GST in Material Master</li>"
                "<li>Phase 2 modules: run validate endpoint before go-live when save is available</li>"
                "</ul>"
                f'<p>See <code>docs/BULK_IMPORT_MIGRATION.md</code> for the full rollout plan.</p>'
            )
        else:
            step_title = "Step 6 — Finish"
            step_content = (
                "<p>Migration wizard complete for available modules.</p>"
                f'<p>Hand off to tenant admin at customer code <strong>{customer["customer_code"]}</strong>.</p>'
                f'<p><a class="erp-btn erp-btn-primary" href="{url_for("erp_admin_customers")}">Back to Customer Master</a></p>'
            )

        return render_template(
            "erp_admin/migration_wizard.html",
            customer=customer,
            steps=steps,
            step_title=step_title,
            step_content=step_content,
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
        edit_id = request.args.get("edit", type=int)
        view_only = request.args.get("view") == "1"
        edit_record = None
        if edit_id:
            row = db.execute(
                """
                SELECT l.*, c.customer_code, c.company_name
                FROM erp_licenses l
                JOIN erp_customers c ON c.id = l.customer_id
                WHERE l.id=?
                """,
                (edit_id,),
            ).fetchone()
            edit_record = dict(row) if row else None
        if request.method == "POST":
            form_action = (request.form.get("form_action") or "").strip()
            if form_action == "delete":
                try:
                    record_id = request.form.get("record_id", type=int)
                    delete_license(db, record_id)
                    db.commit()
                    flash("License deleted successfully.")
                    return redirect(url_for("erp_admin_licenses"))
                except ValueError as exc:
                    db.rollback()
                    flash(str(exc))
                except sqlite3.Error:
                    db.rollback()
                    logger.exception("erp_admin_licenses delete failed")
                    flash("Unable to delete license.")
            else:
                try:
                    record_id = request.form.get("record_id", type=int)
                    license_id = save_license(db, request.form, record_id=record_id)
                    db.commit()
                    flash("License saved successfully.")
                    if not record_id:
                        session["license_handover_password"] = request.form.get("login_password", "")
                        session["license_handover_username"] = request.form.get("login_username", "")
                        return redirect(url_for("erp_admin_license_handover", license_id=license_id))
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
            customers=_license_customer_options(db),
            customer_codes=_customer_codes(db),
            next_license_no=next_license_no(db),
            products=LICENSE_PRODUCTS,
            plans=CUSTOMER_PLANS,
            statuses=LICENSE_STATUSES,
            edit_record=edit_record,
            view_only=view_only,
            sub_toolbar=ERP_ADMIN_SUBTOOLBAR,
            sub_toolbar_sections=ERP_ADMIN_SUBTOOLBAR_SECTIONS,
        )

    @app.route("/erp-admin/licenses/<int:license_id>/handover")
    @login_required
    @super_admin_required
    def erp_admin_license_handover(license_id):
        db = get_db()
        details = get_license_handover_details(db, license_id)
        if not details:
            flash("License record not found.")
            return redirect(url_for("erp_admin_licenses"))
        login_password = session.pop("license_handover_password", "")
        login_username = session.pop("license_handover_username", "") or (
            details.get("login_user") or {}
        ).get("username", "")
        return render_template(
            "erp_admin/license_handover.html",
            details=details,
            login_username=login_username,
            login_password=login_password,
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
