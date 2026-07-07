# MODULE-022 — Enterprise Notification & Alert System

Centralized notification service for MAXEK ERP. Business modules send alerts through a single API; channel routing, user preferences, scheduling, and delivery logging are handled by this module.

## Database schema

### `notifications` (extends legacy workflow table)

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| uuid | TEXT | Unique identifier |
| company_id, branch_id | INTEGER | Tenant scope |
| user_id | INTEGER | Recipient |
| employee_id | INTEGER | Optional HR link |
| module / module_id | TEXT | Source module (both kept for compatibility) |
| notification_type | TEXT | See types below |
| priority | TEXT | Low, Normal, High, Critical |
| title, message | TEXT | Display content |
| channel | TEXT | in_app, email, sms |
| status | TEXT | Pending, Scheduled, Sent, Failed, Cancelled |
| is_read / read_status / read_at | | Read tracking |
| scheduled_at, sent_at | TEXT | Delivery timing |
| failed_reason | TEXT | Last failure |
| related_record_type / record_table | TEXT | Linked entity |
| related_record_id / record_id | INTEGER | Linked entity ID |
| ai_metadata | TEXT JSON | AI prep: summaries, model hints |
| risk_score | REAL | Predictive severity 0–1 |
| behavior_tags | TEXT JSON | Engagement ML tags |
| created_by, created_at, updated_at | TEXT | Audit |

### `notification_templates`

Seeded templates for Approval Pending, Task Assigned, Security Alert, System Error, Custom.

### `notification_channels`

Seeded: IN_APP, EMAIL (stub), SMS (stub).

### `notification_preferences`

Per-user (and optional company) settings: channel toggles, module/priority filters, quiet hours, daily/weekly summary flags.

### `notification_logs`

Delivery attempts with masked payloads for audit.

Bootstrap: `ensure_notification_schema(db)` — idempotent.

## Notification types

Approval Pending, Approval Approved, Approval Rejected, Task Assigned, Task Completed, Task Overdue, Attendance Issue, Payroll Generated, Invoice Created, Payment Received, Payment Overdue, Stock Low, Material Shortage, Purchase Order Approved, Work Order Assigned, Site Issue Reported, Security Alert, System Error, Custom Notification.

## Service usage

```python
from notification_service import notify_user, send_notification

# Thin wrapper (recommended for other modules)
notify_user(
    db,
    user_id=42,
    message="Purchase request PR-100 needs your approval",
    notification_type="Approval Pending",
    title="PR-100 pending",
    module="approvals",
    record_id=100,
    record_table="purchase_requests",
    priority="High",
    channel="in_app",  # or "email", "sms", "all"
    created_by=session.get("username", "system"),
)

# Full payload
send_notification(db, {
    "user_id": 42,
    "notification_type": "Stock Low",
    "title": "Cement below reorder",
    "message": "Warehouse A: cement 50 bags remaining",
    "module": "inventory",
    "priority": "High",
    "channel": "all",
    "ai_metadata": {"suggested_action": "create_po"},
    "risk_score": 0.72,
})
db.commit()
```

### Key functions

| Function | Purpose |
|----------|---------|
| `send_notification()` | Route to enabled channels with preference checks |
| `notify_user()` | Thin wrapper for modules |
| `schedule_notification()` | Future delivery (`scheduled_at` required) |
| `mark_as_read()` / `mark_all_as_read()` | Read state |
| `retry_failed_notification()` | Re-deliver failed/pending |
| `get_user_notifications()` | Paginated list with filters |
| `get_unread_count()` | Badge count |
| `get_dashboard_metrics()` | UI metrics |
| `get/set_user_notification_preferences()` | User settings |
| `send_email()` / `send_sms()` | Stubs — log intent only |

## REST API

Base path: `/api/v1/notifications`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/notifications` | List (page, per_page, sort_by, filters) |
| GET | `/api/v1/notifications/{id}` | Detail |
| POST | `/api/v1/notifications/send` | Send (requires `create`) |
| POST | `/api/v1/notifications/{id}/read` | Mark read |
| POST | `/api/v1/notifications/read-all` | Mark all read |
| GET | `/api/v1/notifications/unread-count` | Unread badge |
| GET/PUT | `/api/v1/notifications/preferences` | User preferences |
| POST | `/api/v1/notifications/retry` | Retry failed (`notification_id` in body) |
| GET | `/api/v1/notifications/dashboard` | Metrics |

Query params for list: `unread_only`, `notification_type`, `priority`, `status`, `module`, `channel`, `admin_view` (admin only).

## UI

- **Notification Center:** `/settings/notification-center` or `/notifications/center`
- Legacy `/notifications` redirects to Notification Center
- Settings nav: **Notification Center**

## Security & RBAC

- Screen: `notification_center` (Settings module)
- Users see own notifications by default
- `admin_view` (edit permission or admin) allows company-scoped admin listing
- Company/branch isolation on records
- Sensitive data masked in `notification_logs.masked_payload`
- Tables registered in `audit_trail_service.TRANSACTION_TABLES`

## Integration notes

1. Call `ensure_notification_schema(db)` is run at app bootstrap — modules only need `notify_user()` + `commit`.
2. Legacy `workflow_service.create_notification()` still works on the same `notifications` table.
3. Email/SMS are stubbed; replace `send_email` / `send_sms` bodies when SMTP/gateway is configured.
4. AI fields (`ai_metadata`, `risk_score`, `behavior_tags`) are optional and ignored by delivery today.

## Deployment

No separate migration command. On deploy/restart, `ensure_runtime_schema()` and `_prepare_notification_db()` apply schema idempotently.

```bash
python -m unittest tests.test_notification_service -v
```
