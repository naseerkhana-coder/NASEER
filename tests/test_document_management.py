"""Unit tests for Enterprise Document Management (MODULE-010)."""

from __future__ import annotations

import io
import os
import sqlite3
import tempfile
import unittest

from document_import_service import save_document_import, validate_document_import
from document_management_service import (
    archive_document,
    attach_document,
    compute_file_hash,
    ensure_document_management_schema,
    export_documents_csv,
    find_duplicate_by_hash,
    get_document_download_path,
    list_documents,
    list_module_documents,
    restore_document,
    rollback_document_version,
    save_document,
    save_folder,
    soft_delete_document,
    user_can_document_management,
    validate_dms_upload,
    virus_scan_file,
)


class _FakeFile:
    def __init__(self, name: str, content: bytes = b"test content"):
        self.filename = name
        self._buf = io.BytesIO(content)

    def seek(self, pos, whence=0):
        return self._buf.seek(pos, whence)

    def tell(self):
        return self._buf.tell()

    def read(self, n=-1):
        return self._buf.read(n)

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            self._buf.seek(0)
            fh.write(self._buf.read())


class DocumentManagementSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_document_management_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_tables_exist(self):
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for name in (
            "documents",
            "document_versions",
            "document_folders",
            "document_tags",
            "document_tag_map",
            "document_shares",
        ):
            self.assertIn(name, tables)

    def test_default_folders_seeded(self):
        count = self.conn.execute("SELECT COUNT(*) FROM document_folders").fetchone()[0]
        self.assertGreater(count, 0)


class DocumentUploadTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_document_management_schema(self.conn)
        self.tmp = tempfile.mkdtemp()
        self.folder_id = save_folder(self.conn, {"folder_name": "Test"}, "tester")

    def tearDown(self):
        self.conn.close()

    def test_validate_rejects_bad_extension(self):
        f = _FakeFile("malware.exe")
        ext, err = validate_dms_upload(f)
        self.assertIsNone(ext)
        self.assertIn("Allowed", err or "")

    def test_upload_creates_version(self):
        f = _FakeFile("spec.pdf", b"%PDF-1.4 sample")
        doc_id = save_document(
            self.conn,
            {"document_name": "Spec", "folder_id": self.folder_id},
            "tester",
            f,
            dest_root=self.tmp,
        )
        self.conn.commit()
        doc = self.conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        self.assertEqual(doc["version_number"], 1)
        versions = self.conn.execute(
            "SELECT COUNT(*) FROM document_versions WHERE document_id=?", (doc_id,)
        ).fetchone()[0]
        self.assertEqual(versions, 1)

    def test_version_increment_on_update(self):
        f1 = _FakeFile("a.pdf", b"version one")
        doc_id = save_document(
            self.conn,
            {"document_name": "Doc A", "folder_id": self.folder_id},
            "tester",
            f1,
            dest_root=self.tmp,
        )
        f2 = _FakeFile("a.pdf", b"version two longer")
        save_document(
            self.conn,
            {"document_name": "Doc A", "folder_id": self.folder_id},
            "tester",
            f2,
            dest_root=self.tmp,
            document_id=doc_id,
        )
        ver = self.conn.execute(
            "SELECT version_number FROM documents WHERE id=?", (doc_id,)
        ).fetchone()[0]
        self.assertEqual(ver, 2)

    def test_duplicate_hash_detection(self):
        content = b"duplicate payload"
        f1 = _FakeFile("one.pdf", content)
        save_document(
            self.conn,
            {"document_name": "First", "folder_id": self.folder_id},
            "tester",
            f1,
            dest_root=self.tmp,
        )
        hv = compute_file_hash(io.BytesIO(content))
        dup = find_duplicate_by_hash(self.conn, hv)
        self.assertIsNotNone(dup)

    def test_soft_delete(self):
        f = _FakeFile("x.pdf", b"x")
        doc_id = save_document(
            self.conn,
            {"document_name": "Del", "folder_id": self.folder_id},
            "tester",
            f,
            dest_root=self.tmp,
        )
        soft_delete_document(self.conn, doc_id, "tester")
        row = self.conn.execute(
            "SELECT is_deleted FROM documents WHERE id=?", (doc_id,)
        ).fetchone()
        self.assertEqual(row[0], 1)

    def test_archive_restore(self):
        f = _FakeFile("x.pdf", b"x")
        doc_id = save_document(
            self.conn,
            {"document_name": "Arc", "folder_id": self.folder_id},
            "tester",
            f,
            dest_root=self.tmp,
        )
        archive_document(self.conn, doc_id, "tester")
        self.assertEqual(
            self.conn.execute(
                "SELECT archive_flag FROM documents WHERE id=?", (doc_id,)
            ).fetchone()[0],
            1,
        )
        restore_document(self.conn, doc_id, "tester", from_archive=True)
        self.assertEqual(
            self.conn.execute(
                "SELECT archive_flag FROM documents WHERE id=?", (doc_id,)
            ).fetchone()[0],
            0,
        )

    def test_rollback_version(self):
        f1 = _FakeFile("r.pdf", b"v1")
        doc_id = save_document(
            self.conn,
            {"document_name": "Roll", "folder_id": self.folder_id},
            "tester",
            f1,
            dest_root=self.tmp,
        )
        f2 = _FakeFile("r.pdf", b"v2")
        save_document(
            self.conn,
            {"document_name": "Roll", "folder_id": self.folder_id},
            "tester",
            f2,
            dest_root=self.tmp,
            document_id=doc_id,
        )
        rollback_document_version(self.conn, doc_id, 1, "tester")
        ver = self.conn.execute(
            "SELECT version_number FROM documents WHERE id=?", (doc_id,)
        ).fetchone()[0]
        self.assertEqual(ver, 1)

    def test_attach_and_list_module_documents(self):
        f = _FakeFile("attach.pdf", b"mod")
        doc_id = attach_document(
            self.conn,
            "purchase_orders",
            "PO-100",
            f,
            "tester",
            dest_root=self.tmp,
            category="Contract",
        )
        items = list_module_documents(self.conn, "purchase_orders", "PO-100")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], doc_id)

    def test_download_path(self):
        f = _FakeFile("dl.pdf", b"download me")
        doc_id = save_document(
            self.conn,
            {"document_name": "DL", "folder_id": self.folder_id},
            "tester",
            f,
            dest_root=self.tmp,
        )
        paths = get_document_download_path(self.conn, doc_id, dest_root=self.tmp)
        self.assertIsNotNone(paths)
        abs_path, name = paths
        self.assertTrue(os.path.isfile(abs_path))
        self.assertIn("dl.pdf", name.lower())

    def test_search(self):
        f = _FakeFile("s.pdf", b"s")
        save_document(
            self.conn,
            {"document_name": "UniqueAlphaDoc", "folder_id": self.folder_id},
            "tester",
            f,
            dest_root=self.tmp,
        )
        listing = list_documents(self.conn, search="UniqueAlpha")
        self.assertEqual(listing["total"], 1)

    def test_virus_scan_stub(self):
        result = virus_scan_file("/tmp/nonexistent-stub.pdf")
        self.assertTrue(result.get("clean"))


class DocumentImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_document_management_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_metadata_import(self):
        rows = [
            {
                "_row_num": 2,
                "document_name": "Imported Policy",
                "category": "Policy",
                "folder_name": "Legal",
                "module_name": "enterprise_dms",
            }
        ]
        val = validate_document_import(self.conn, rows)
        self.assertTrue(val.get("ok"))
        result = save_document_import(self.conn, val["parsed_rows"], username="tester")
        self.assertEqual(result["imported"], 1)


class DocumentPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_document_management_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_admin_has_access(self):
        self.assertTrue(user_can_document_management(self.conn, None, "view", is_admin=True))

    def test_no_user_denied(self):
        self.assertFalse(user_can_document_management(self.conn, None, "view", is_admin=False))


class DocumentExportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_document_management_schema(self.conn)
        self.tmp = tempfile.mkdtemp()
        fid = save_folder(self.conn, {"folder_name": "X"}, "t")
        save_document(
            self.conn,
            {"document_name": "Exp", "folder_id": fid},
            "t",
            _FakeFile("e.pdf", b"e"),
            dest_root=self.tmp,
        )

    def tearDown(self):
        self.conn.close()

    def test_csv_export(self):
        csv_text = export_documents_csv(self.conn)
        self.assertIn("document_number", csv_text)
        self.assertIn("Exp", csv_text)


if __name__ == "__main__":
    unittest.main()
