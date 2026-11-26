"""Tests for the show-mode registry in software/service/userdata.py.

Run from the repo root:  python3 -I tests/test_showmode.py
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "software", "service"))
import userdata as U  # noqa: E402


class ShowMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = U.open_user(os.path.join(self.tmp.name, "user.sqlite"))
        self.seed = os.path.join(self.tmp.name, "seed.json")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def write_seed(self, items):
        with open(self.seed, "w", encoding="utf-8") as f:
            json.dump(items, f)

    def test_real_seed_file(self):
        with open(U.SEED_PATH, encoding="utf-8") as f:
            items = json.load(f)
        ids = [i["id"] for i in items]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids in functions_seed.json")
        self.assertTrue(all(i["cls"] in ("C", "L") for i in items), "class H must not be in the registry")
        U.seed_showmode(self.db)
        rows = U.list_showmode(self.db)
        self.assertEqual(len(rows), len(items))
        self.assertTrue(all(r["enabled"] == 0 for r in rows), "everything must start off")

    def test_toggle_and_unknown_id(self):
        self.write_seed([{"id": "F-1", "name": "a", "node": "n", "cls": "C"}])
        U.seed_showmode(self.db, self.seed)
        self.assertEqual(U.set_showmode(self.db, "F-1", True), 1)
        self.assertEqual(U.list_showmode(self.db)[0]["enabled"], 1)
        self.assertEqual(U.set_showmode(self.db, "F-1", False), 1)
        self.assertEqual(U.list_showmode(self.db)[0]["enabled"], 0)
        self.assertEqual(U.set_showmode(self.db, "F-999", True), 0)

    def test_reseed_keeps_setting_but_class_change_resets(self):
        self.write_seed([{"id": "F-1", "name": "a", "node": "n", "cls": "C"}])
        U.seed_showmode(self.db, self.seed)
        U.set_showmode(self.db, "F-1", True)
        self.write_seed([{"id": "F-1", "name": "renamed", "node": "n", "cls": "C"}])
        U.seed_showmode(self.db, self.seed)
        row = U.list_showmode(self.db)[0]
        self.assertEqual((row["name"], row["enabled"]), ("renamed", 1))
        self.write_seed([{"id": "F-1", "name": "renamed", "node": "n", "cls": "L"}])
        U.seed_showmode(self.db, self.seed)
        row = U.list_showmode(self.db)[0]
        self.assertEqual((row["cls"], row["enabled"]), ("L", 0), "a class change must reset to off")

    def test_seed_never_enables_and_skips_class_h(self):
        self.write_seed([{"id": "F-1", "name": "a", "node": "n", "cls": "C", "enabled": 1},
                         {"id": "F-501", "name": "abs valves", "node": "n", "cls": "H"}])
        U.seed_showmode(self.db, self.seed)
        rows = U.list_showmode(self.db)
        self.assertEqual([r["id"] for r in rows], ["F-1"])
        self.assertEqual(rows[0]["enabled"], 0)

    def test_all_off_and_allowed_ids(self):
        self.write_seed([{"id": "F-1", "name": "a", "node": "n", "cls": "C"},
                         {"id": "F-2", "name": "b", "node": "n", "cls": "L"}])
        U.seed_showmode(self.db, self.seed)
        U.set_showmode(self.db, "F-1", True)
        U.set_showmode(self.db, "F-2", True)
        self.assertEqual(U.allowed_ids(self.db), {"F-1": "C", "F-2": "L"})
        self.assertEqual(U.showmode_all_off(self.db), 2)
        self.assertEqual(U.allowed_ids(self.db), {})

    def test_missing_seed_file_is_safe(self):
        self.assertEqual(U.seed_showmode(self.db, os.path.join(self.tmp.name, "nope.json")), 0)
        self.assertEqual(U.list_showmode(self.db), [])
        self.assertEqual(U.allowed_ids(self.db), {})

    def test_list_order_puts_legal_critical_first(self):
        self.write_seed([{"id": "F-1", "name": "a", "node": "n", "cls": "C"},
                         {"id": "F-2", "name": "b", "node": "n", "cls": "L"}])
        U.seed_showmode(self.db, self.seed)
        self.assertEqual([r["cls"] for r in U.list_showmode(self.db)], ["L", "C"])


if __name__ == "__main__":
    unittest.main()
