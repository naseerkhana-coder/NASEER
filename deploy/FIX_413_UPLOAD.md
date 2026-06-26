# Fix HTTP 413 on project creation (VPS)

## Symptom

Creating a project at `/projects` returns **413 Request Entity Too Large** when attaching agreement, bank guarantee, security deposit, or work order documents.

## Root cause

The project form uses `multipart/form-data` with up to **four file uploads** plus many text fields. Nginx’s default `client_max_body_size` is **1 MB**, so large uploads are rejected **before** Gunicorn/Flask see the request.

Flask now enforces `MAX_CONTENT_LENGTH = 32 MB` in `app.py`. Nginx must allow at least the same limit.

## Limits (application)

| Layer | Setting | Value |
|-------|---------|-------|
| Nginx | `client_max_body_size` | 32M |
| Flask | `MAX_CONTENT_LENGTH` | 32 MB |
| Per project file | `MAX_PROJECT_UPLOAD_BYTES` | 10 MB each |

Allowed extensions: `.pdf`, `.jpg`, `.jpeg`, `.png`

## Fix on VPS (srv1704727 or any host)

SSH in, then run:

```bash
APP=/var/www/maxek-erp

# 1) Check current nginx body limit (empty = default 1m)
sudo grep -R "client_max_body_size" /etc/nginx/ 2>/dev/null || echo "No client_max_body_size set (default 1m)"

# 2) Deploy site config from repo (includes 32M)
sudo cp "$APP/deploy/nginx-maxek-erp.conf" /etc/nginx/sites-available/maxek-erp

# 3) Edit server_name if needed (IP or domain)
sudo nano /etc/nginx/sites-available/maxek-erp

# 4) Enable site and test
sudo ln -sf /etc/nginx/sites-available/maxek-erp /etc/nginx/sites-enabled/maxek-erp
sudo nginx -t
sudo systemctl reload nginx
```

If you use **HTTPS (Certbot)**, ensure the active `listen 443 ssl` server block also has `client_max_body_size 32M;` (see commented block in `deploy/nginx-maxek-erp.conf`).

### Minimal patch (without replacing whole file)

```bash
sudo nano /etc/nginx/sites-available/maxek-erp
```

Inside each `server { ... }` block, add:

```nginx
client_max_body_size 32M;
```

Then:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## Deploy application changes

After pulling code with Flask limits:

```bash
APP=/var/www/maxek-erp
cd "$APP"
git pull   # or your deploy method
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
```

## Verify

```bash
# Nginx still proxies to Gunicorn
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/login

# Confirm limit in active config
sudo nginx -T 2>/dev/null | grep client_max_body_size
```

Then create a test project with a small PDF (&lt; 10 MB) in the UI.
