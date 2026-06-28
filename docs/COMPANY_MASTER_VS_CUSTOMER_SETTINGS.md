# Company Master vs Customer Settings

## Purpose

MAXEK ERP separates **legal/registration data** from **tenant branding**. This avoids duplicating GST, bank, and logo in two places and matches how Super Admin provisions tenants vs how tenants manage their own legal entities.

## Customer Settings (Platform — Super Admin only)

**Route:** `/erp-admin/customers/<id>/settings`  
**Template:** `templates/erp_admin/customer_settings.html`

| Field | Purpose |
|-------|---------|
| Company Logo | Login/sidebar branding for the tenant |
| Company Display Name | UI header and login label (not legal name) |
| UI Theme | Command Dark / Pro Light / Ultra Color |
| Email Settings | SMTP / from-address for tenant-branded mail |

**Not here:** GST, PAN, CIN, registered address, bank details, financial year, currency, timezone (those belong in Company Master inside the tenant or Customer Master registration at onboarding).

## Company Master (Tenant — Company Admin)

**Route:** `/settings/company-master`  
**Template:** `templates/company_master.html`

| Area | Purpose |
|------|---------|
| Legal / trade name | Registered entity names |
| Address, phone, email, website | Official contact |
| Country-specific registration | GST, PAN, CIN, etc. |
| Primary bank account | Invoicing and payments |
| Branches, directors, documents | Compliance structure |
| GST registrations (India) | Multi-state billing |

**Not here:** Logo upload or UI theme (configured in Customer Settings by Super Admin).

## Implementation notes

- `erp_admin_routes.erp_admin_customer_settings` saves only branding fields via `save_customer_tenant_settings`.
- Company Master form never included a logo field; help text on both screens clarifies the split.
