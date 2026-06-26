"""WSGI entry point for production (Gunicorn / systemd)."""
from app import app, init_db

with app.app_context():
    init_db()

application = app
