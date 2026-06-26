"""Regression tests: Material Request and Purchase Request view pages."""
import os
import unittest

os.environ.setdefault("MAXEK_SKIP_DEMO_SEED", "1")

from app import app, get_db, query_db, create_approval_request  # noqa: E402


class MaterialPurchaseRequestViewTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "Admin"
            sess["workflow_role"] = "Administrator"

        with app.app_context():
            db = get_db()
            proj = query_db("SELECT id FROM projects LIMIT 1", one=True)
            if not proj:
                db.execute(
                    "INSERT INTO projects(project_name, approval_status) VALUES(?, ?)",
                    ("View Test Project", "Approved"),
                )
                db.commit()
                proj = query_db("SELECT id FROM projects LIMIT 1", one=True)
            pid = proj["id"]
            db.execute(
                "INSERT INTO material_requests("
                "project_id, request_date, item_name, quantity, unit, created_by, approval_status"
                ") VALUES(?,?,?,?,?,?,?)",
                (pid, "2026-06-21", "Test Cement", 5, "Bag", "admin", "Pending Checker"),
            )
            db.execute(
                "INSERT INTO purchase_requests("
                "project_id, request_date, item_description, quantity, estimated_cost, "
                "created_by, approval_status"
                ") VALUES(?,?,?,?,?,?,?)",
                (pid, "2026-06-21", "Test Steel", 2, 1500, "admin", "Pending Checker"),
            )
            db.commit()
            self.mr_id = query_db(
                "SELECT id FROM material_requests ORDER BY id DESC LIMIT 1", one=True
            )["id"]
            self.pr_id = query_db(
                "SELECT id FROM purchase_requests ORDER BY id DESC LIMIT 1", one=True
            )["id"]
            create_approval_request(
                db, "material_request", self.mr_id, "material_requests", "admin", 1
            )
            create_approval_request(
                db, "purchase_request", self.pr_id, "purchase_requests", "admin", 1
            )
            db.commit()

    def test_material_request_view_ok(self):
        resp = self.client.get(f"/material-request?view={self.mr_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Record #", body)
        self.assertIn("Approval History", body)
        self.assertNotIn("UndefinedError", body)

    def test_purchase_request_view_ok(self):
        resp = self.client.get(f"/purchase-request?view={self.pr_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Record #", body)
        self.assertIn("Approval History", body)
        self.assertNotIn("UndefinedError", body)


if __name__ == "__main__":
    unittest.main()
