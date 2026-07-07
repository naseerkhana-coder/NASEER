"""Unit and integration tests for BOQ Management (MODULE-017)."""

from __future__ import annotations

import json
import sqlite3
import unittest

from boq_management_import_service import save_boq_management_import, validate_boq_management_import
from boq_management_service import (
    BOQ_MAX_ITEMS,
    approve_boq_master,
    compare_boqs,
    copy_boq_master,
    detect_duplicate_items,
    ensure_boq_management_schema,
    export_boqs_csv,
    generate_boq_number,
    get_boq_balance_summary,
    get_boq_items_for_project,
    get_boq_master,
    list_boqs_master,
    parse_boq_items_from_form,
    quantity_anomaly_check,
    save_boq_master,
    soft_delete_boq_master,
    update_executed_quantity,
    user_can_boq_management,
    validate_boq,
    validate_boq_uniqueness,
)


class _FormDict(dict):
    def getlist(self, key):
        val = self.get(key)
        if isinstance(val, list):
            return val
        return [val] if val is not None else []


def _sample_boq_form(**overrides):
    form = _FormDict(
        {
            "project_id": "1",
            "boq_number": "TE101",
            "boq_name": "Main Civil BOQ",
            "revision_number": "1",
            "revision_date": "2026-01-15",
            "client_reference": "CL-REF-01",
            "contract_reference": "CTR-01",
            "status": "Draft",
            "item_number[]": ["BOQ1", "BOQ2"],
            "item_description[]": ["Earth work", "PCC"],
            "specification[]": ["Ordinary soil", "M15"],
            "unit[]": ["Cum", "Cum"],
            "quantity[]": ["100", "50"],
            "rate[]": ["450", "5200"],
            "amount[]": ["45000", "260000"],
            "executed_quantity[]": ["0", "0"],
            "remarks[]": ["", ""],
            "boq_code[]": ["", ""],
        }
    )
    form.update(overrides)
    return form


class BoqManagementSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._seed_projects()

    def _seed_projects(self):
        self.conn.execute(
            """
            CREATE TABLE projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_code TEXT,
                project_name TEXT,
                client_id INTEGER,
                status TEXT
            )
            """
        )
        self.conn.execute(
            "INSERT INTO projects(id, project_code, project_name, status) VALUES(1,'TE100','Test Engineering', 'Active')"
        )
        ensure_boq_management_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_schema_extends_boq_master(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(boq_master)").fetchall()}
        for col in (
            "boq_name",
            "revision_number",
            "parent_boq_id",
            "is_current_revision",
            "client_reference",
            "contract_reference",
            "status",
            "approved_by",
        ):
            self.assertIn(col, cols)

    def test_boq_items_executed_quantity_column(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(boq_items)").fetchall()}
        self.assertIn("executed_quantity", cols)
        self.assertIn("item_number", cols)

    def test_boq_revisions_table_exists(self):
        tables = {
            row[0]
            for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        self.assertIn("boq_revisions", tables)


class BoqManagementCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_code TEXT,
                project_name TEXT,
                status TEXT
            )
            """
        )
        self.conn.execute(
            "INSERT INTO projects(id, project_code, project_name, status) VALUES(1,'TE100','Test Engineering','Active')"
        )
        ensure_boq_management_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_save_and_get_boq(self):
        boq_id = save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()
        boq = get_boq_master(self.conn, boq_id)
        self.assertIsNotNone(boq)
        self.assertEqual(boq["boq_name"], "Main Civil BOQ")
        self.assertEqual(len(boq["items"]), 2)
        self.assertAlmostEqual(float(boq["total_amount"]), 305000.0)

    def test_unique_boq_number_per_project(self):
        save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_boq_uniqueness(self.conn, project_id=1, boq_number="TE101")

    def test_generate_boq_number(self):
        num = generate_boq_number(self.conn, 1)
        self.assertTrue(num.startswith("TE"))

    def test_soft_delete_boq(self):
        boq_id = save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()
        soft_delete_boq_master(self.conn, boq_id, "tester")
        self.conn.commit()
        self.assertIsNone(get_boq_master(self.conn, boq_id))

    def test_revision_copy(self):
        boq_id = save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()
        new_id = copy_boq_master(self.conn, boq_id, "tester", as_revision=True)
        self.conn.commit()
        old = get_boq_master(self.conn, boq_id)
        new = get_boq_master(self.conn, new_id)
        self.assertEqual(int(new["revision_number"]), 2)
        self.assertEqual(int(old["is_current_revision"]), 0)
        self.assertEqual(int(new["is_current_revision"]), 1)

    def test_executed_quantity_hook(self):
        boq_id = save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()
        item_id = get_boq_master(self.conn, boq_id)["items"][0]["id"]
        update_executed_quantity(self.conn, item_id, 10)
        self.conn.commit()
        item = get_boq_master(self.conn, boq_id)["items"][0]
        self.assertAlmostEqual(float(item["executed_quantity"]), 10.0)
        self.assertAlmostEqual(float(item["balance_quantity"]), 90.0)

    def test_balance_summary(self):
        boq_id = save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()
        summary = get_boq_balance_summary(self.conn, 1)
        self.assertEqual(summary["item_count"], 2)
        self.assertGreater(summary["total_amount"], 0)

    def test_project_items_hook(self):
        save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()
        items = get_boq_items_for_project(self.conn, 1)
        self.assertEqual(len(items), 2)


class BoqManagementAiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE projects(id INTEGER PRIMARY KEY, project_name TEXT, project_code TEXT, status TEXT)"
        )
        self.conn.execute("INSERT INTO projects VALUES(1,'Test Engineering','TE100','Active')")
        ensure_boq_management_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_validate_boq_and_duplicates(self):
        form = _sample_boq_form()
        form["item_number[]"] = ["BOQ1", "BOQ1"]
        boq_id = save_boq_master(self.conn, form, "tester")
        self.conn.commit()
        result = validate_boq(self.conn, boq_id=boq_id)
        self.assertTrue(result["ok"])
        dup = detect_duplicate_items(self.conn, boq_id=boq_id)
        self.assertIn("boq1", dup["duplicates"])

    def test_quantity_anomaly_check(self):
        boq_id = save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()
        anomalies = quantity_anomaly_check(self.conn, boq_id=boq_id)
        self.assertIn("warnings", anomalies)

    def test_compare_boqs(self):
        a = save_boq_master(self.conn, _sample_boq_form(boq_number="TE101"), "tester")
        b = save_boq_master(
            self.conn,
            _FormDict({**_sample_boq_form(), "boq_number": "TE102", "item_description[]": ["Earth work", "Steel"]}),
            "tester",
        )
        self.conn.commit()
        cmp = compare_boqs(self.conn, a, b)
        self.assertTrue(cmp["ok"])


class BoqManagementImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE projects(id INTEGER PRIMARY KEY, project_name TEXT, project_code TEXT, status TEXT)"
        )
        self.conn.execute("INSERT INTO projects VALUES(1,'Test Engineering','TE100','Active')")
        ensure_boq_management_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_import_validate_and_save(self):
        rows = [
            {
                "_row_num": 2,
                "description": "Earth work",
                "unit": "Cum",
                "quantity": 10,
                "rate": 100,
                "amount": 1000,
                "item_no": "1",
            }
        ]
        val = validate_boq_management_import(self.conn, rows, boq_units=["Cum"], project_id=1)
        self.assertTrue(val.get("ok") or val.get("parsed_rows"))
        parsed = val.get("parsed_rows") or rows
        result = save_boq_management_import(
            self.conn,
            parsed,
            project_id=1,
            username="importer",
            filename="test.xlsx",
            boq_name="Imported BOQ",
        )
        self.conn.commit()
        self.assertTrue(result.get("boq_id"))
        boq = get_boq_master(self.conn, int(result["boq_id"]))
        self.assertEqual(boq["boq_name"], "Imported BOQ")


class BoqManagementExportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE projects(id INTEGER PRIMARY KEY, project_name TEXT, project_code TEXT, status TEXT)"
        )
        self.conn.execute("INSERT INTO projects VALUES(1,'Test Engineering','TE100','Active')")
        ensure_boq_management_schema(self.conn)
        save_boq_master(self.conn, _sample_boq_form(), "tester")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_list_and_export_csv(self):
        listing = list_boqs_master(self.conn)
        self.assertEqual(listing["total"], 1)
        csv_text = export_boqs_csv(self.conn)
        self.assertIn("boq_number", csv_text)


if __name__ == "__main__":
    unittest.main()
