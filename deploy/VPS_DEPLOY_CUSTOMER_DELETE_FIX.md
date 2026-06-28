# VPS deploy — Customer delete 500 fix

**App path:** `/var/www/maxek-erp-flask/`

## Root cause

`delete_customer()` called `.get()` on a `sqlite3.Row` object (no `.get` method) → **500 Internal Server Error**.

Also hardened customer CRUD for reset/partial SQLite schemas (missing `users.customer_id`, missing limit tables).

## Files to upload

| File | Purpose |
|------|---------|
| `super_admin_service.py` | Fix Row→dict in `delete_customer`; safe dependency counts; schema guard on save/delete |
| `erp_admin_routes.py` | Catch `OperationalError` / generic errors; flash instead of 500 |

## Quick sync (from dev PC)

```bash
scp super_admin_service.py erp_admin_routes.py root@72.61.224.204:/var/www/maxek-erp-flask/
```

## Restart

```bash
ssh root@72.61.224.204 "systemctl restart maxek-erp-flask"
```

## Verify on VPS

```bash
ssh root@72.61.224.204 "journalctl -u maxek-erp-flask -n 50 --no-pager | grep -iE 'error|customer|AttributeError|OperationalError'"
```

## Smoke test (super admin)

1. `/erp-admin/customers` — list loads.
2. **Edit** a customer → Save → success flash.
3. **Delete** a customer with no users/licenses → success flash, row removed.
4. **Delete** a customer with linked users → friendly error flash (not 500).
5. **Add New** customer → save still works.
