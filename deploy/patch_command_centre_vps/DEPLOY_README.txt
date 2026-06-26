MAXEK ERP — Command Centre / Dashboard VPS Patch
Date: 2026-06-22

CONTENTS
--------
Updates Command Centre dashboard, department workspace, shared MAXEK UI shell,
styles, and related Flask routes in app.py.

VPS INSTALL STEPS
-----------------
1. Stop the application (if you use systemd):
     sudo systemctl stop maxek-erp
   Or stop your gunicorn/uwsgi process manually.

2. On the VPS, back up files that this patch replaces (from your project root):
     mkdir -p ~/backups/command_centre_20260622
     cp -a app.py templates/dashboard.html templates/department_workspace.html \
       templates/department_dashboard.html templates/base_maxek.html \
       templates/macros/erp_ui.html templates/partials/ai_assistant_panel.html \
       static/css/maxek-dashboard.css static/js/maxek-ui.js static/js/ai-assistant.js \
       static/images/maxek-logo.png ~/backups/command_centre_20260622/ 2>/dev/null || true

3. Upload MAXEK_ERP_CommandCentre_Patch_20260622.zip to the server.

4. From your MAXEK ERP project root on the VPS, extract (overwrites matching paths):
     unzip -o MAXEK_ERP_CommandCentre_Patch_20260622.zip

5. Restart the application:
     sudo systemctl start maxek-erp
   Or restart gunicorn/uwsgi as you normally do.

6. In your browser, hard-refresh (Ctrl+F5) or clear cache so new CSS/JS load.

NOTES
-----
- No database migration is included in this patch.
- If your service name differs, adjust systemctl commands accordingly.
