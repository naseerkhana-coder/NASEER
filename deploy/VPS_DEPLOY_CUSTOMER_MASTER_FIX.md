# VPS deploy — Customer Master edit/delete + toolbar cleanup

**App path:** `/var/www/maxek-erp-flask/`

## Files to upload

| File | Purpose |
|------|---------|
| `super_admin_service.py` | `delete_customer()` with dependency checks |
| `erp_admin_routes.py` | Delete POST handler; deduped template context |
| `app.py` | Stop duplicate ERP Admin `module_sub_toolbar` |
| `templates/erp_admin/customers.html` | Single toolbar, edit/delete actions, list-only layout |

## Quick sync (from dev PC)

```bash
scp super_admin_service.py erp_admin_routes.py app.py root@72.61.224.204:/var/www/maxek-erp-flask/
scp templates/erp_admin/customers.html root@72.61.224.204:/var/www/maxek-erp-flask/templates/erp_admin/
```

## Restart

```bash
ssh root@72.61.224.204 "systemctl restart maxek-erp-flask"
```

## Smoke test (super admin)

1. Open `/erp-admin/customers` — one department sub-toolbar only (no repeated ERP Admin link rows).
2. Customer list shows **Edit** and **Delete** on each row.
3. **Edit** opens the registration form pre-filled; Save updates the record.
4. **Delete** prompts for confirmation; removes customer when no users/licenses are linked.
5. **Add New** opens the hidden form via `#add-customer`.
