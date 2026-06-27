"""Verify corporate template INSERT column/placeholder alignment and runtime schema."""
import os
import sqlite3
import tempfile
import unittest

from corporate_template_service import ensure_corporate_template_schema, save_template


TEMPLATE_INSERT_COLUMNS = (
    "template_name, is_active, is_default, "
    "company_logo_path, watermark_logo_path, company_seal_path, signatory_image_path, "
    "letterhead_html, footer_html, "
    "primary_color, secondary_color, background_color, "
    "font_family, pdf_orientation, "
    "footer_address, footer_phone, footer_email, footer_website, "
    "header_title_line1, header_title_line2, "
    "created_by, created_at, updated_at"
)


def _count_placeholders(values_clause: str) -> int:
    inner = values_clause.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    return len([p for p in inner.split(",") if p.strip() == "?"])


class CorporateTemplateInsertSchemaTest(unittest.TestCase):
    def test_insert_column_count_matches_placeholders_in_service_source(self):
        service_path = os.path.join(
            os.path.dirname(__file__), "..", "corporate_template_service.py"
        )
        with open(service_path, encoding="utf-8") as fh:
            content = fh.read()
        marker = "header_title_line1, header_title_line2,\n            created_by, created_at, updated_at"
        start = content.index(marker)
        values_start = content.index("VALUES(", start) + 7
        values_end = content.index(")", values_start)
        values_clause = content[values_start:values_end]
        col_count = len([c.strip() for c in TEMPLATE_INSERT_COLUMNS.split(",") if c.strip()])
        self.assertEqual(_count_placeholders(values_clause), col_count)

    def test_runtime_insert_after_schema_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                CREATE TABLE corporate_report_templates(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    is_default INTEGER DEFAULT 0
                )
                """
            )
            ensure_corporate_template_schema(conn)
            form = {
                "template_name": "Test Template",
                "is_active": "1",
                "is_default": "0",
                "pdf_orientation": "portrait",
                "font_family": "Arial, Helvetica, sans-serif",
            }
            new_id = save_template(conn, form, "tester", {}, None)
            row = conn.execute(
                "SELECT template_name FROM corporate_report_templates WHERE id=?",
                (new_id,),
            ).fetchone()
            self.assertEqual(row["template_name"], "Test Template")
            conn.close()


if __name__ == "__main__":
    unittest.main()
