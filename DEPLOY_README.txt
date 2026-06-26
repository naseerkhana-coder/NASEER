MAXEK ERP - FINAL VPS Deployment Package
========================================

Target: existing MAXEK_ERP application directory on your VPS (Linux).

1) Upload the zip to the server (example):
   scp MAXEK_ERP_FINAL_deploy.zip user@YOUR_VPS:/tmp/

2) On the VPS, back up and extract (overwrite app files; does NOT include database or .env):
   cd /path/to/MAXEK_ERP
   cp -a . ../MAXEK_ERP_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
   unzip -o /tmp/MAXEK_ERP_FINAL_deploy.zip -d /path/to/MAXEK_ERP

3) Python dependencies:
   cd /path/to/MAXEK_ERP
   source .venv/bin/activate   # if you use a venv
   pip install -r requirements.txt

4) Set OpenAI key in .env (create or edit; NOT shipped in this zip):
   echo 'OPENAI_API_KEY=sk-your-key-here' >> .env
   # or: nano .env

5) Optional production DB migration:
   python deploy/migrate_production.py

6) Restart the app (adjust to your setup):
   sudo systemctl restart maxek-erp
   # OR: sudo systemctl restart gunicorn
   # OR: touch wsgi.py && supervisorctl restart maxek

7) Super Admin (if needed on fresh DB):
   python seed_super_admin.py
   Company code: MAXEK | Username: superadmin | Password: superadmin123 (change after login)

Verify after deploy:
- Login page loads (templates/login.html)
- AI assistant panel appears (requires OPENAI_API_KEY)
- app.py registers register_ai_routes
