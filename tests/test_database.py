import io
import unittest
from contextlib import chdir, redirect_stdout
from tempfile import TemporaryDirectory
from unittest.mock import patch

from primitive_db import core
from primitive_db.cache import create_cacher
from primitive_db.engine import execute
from primitive_db.parser import parse_command, parse_value
from primitive_db.utils import (
    METADATA_FILE,
    get_table_path,
    load_metadata,
    load_table_data,
    save_metadata,
    save_table_data,
)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.enterContext(chdir(directory))
        self.output = io.StringIO()
        self.enterContext(redirect_stdout(self.output))

        self.metadata = core.create_table(
            {},
            "users",
            ["name:str", "age:int", "is_active:bool"],
        )

    def test_missing_metadata_returns_empty_dictionary(self):
        self.assertEqual(load_metadata(METADATA_FILE), {})

    def test_metadata_round_trip(self):
        save_metadata(METADATA_FILE, self.metadata)

        self.assertEqual(
            load_metadata(METADATA_FILE),
            self.metadata,
        )

    def test_create_table_adds_id(self):
        self.assertEqual(
            list(self.metadata["users"]),
            ["ID", "name", "age", "is_active"],
        )

    def test_duplicate_table_is_rejected(self):
        result = core.create_table(
            self.metadata,
            "users",
            ["name:str"],
        )

        self.assertIsNone(result)

    def test_invalid_column_type_is_rejected(self):
        result = core.create_table({}, "bad", ["price:float"])

        self.assertIsNone(result)

    def test_insert_and_automatic_id(self):
        first = core.insert(
            self.metadata,
            "users",
            ["Sergei", 28, True],
        )
        save_table_data("users", first)

        second = core.insert(
            self.metadata,
            "users",
            ["Anna", 23, False],
        )

        self.assertEqual([row["ID"] for row in second], [1, 2])

    def test_boolean_is_not_integer(self):
        result = core.insert(
            self.metadata,
            "users",
            ["Sergei", True, True],
        )

        self.assertIsNone(result)

    def test_wrong_value_count_is_rejected(self):
        result = core.insert(
            self.metadata,
            "users",
            ["Sergei"],
        )

        self.assertIsNone(result)

    def test_select_filters_rows(self):
        rows = [
            {"ID": 1, "name": "A", "age": 20, "is_active": True},
            {"ID": 2, "name": "B", "age": 30, "is_active": False},
        ]

        result = core.select(rows, {"age": 30})

        self.assertEqual([row["ID"] for row in result], [2])

    def test_select_cache_does_not_return_stale_data(self):
        rows = [{"ID": 1, "age": 20}]

        first = core.select(rows, {"age": 20})
        rows[0]["age"] = 21
        second = core.select(rows, {"age": 20})

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_update_does_not_mutate_original_rows(self):
        rows = [{"ID": 1, "age": 20}]

        result = core.update(rows, {"age": 21}, {"ID": 1})

        self.assertEqual(result[0]["age"], 21)
        self.assertEqual(rows[0]["age"], 20)

    def test_id_update_is_rejected(self):
        result = core.update(
            [{"ID": 1, "age": 20}],
            {"ID": 2},
            {"ID": 1},
        )

        self.assertIsNone(result)

    def test_delete_can_be_cancelled(self):
        rows = [{"ID": 1, "age": 20}]

        with patch("builtins.input", return_value="n"):
            result = core.delete(rows, {"ID": 1})

        self.assertIsNone(result)
        self.assertEqual(len(rows), 1)

    def test_delete_can_be_confirmed(self):
        rows = [{"ID": 1, "age": 20}]

        with patch("builtins.input", return_value="y"):
            result = core.delete(rows, {"ID": 1})

        self.assertEqual(result, [])

    def test_drop_table_can_be_cancelled(self):
        with patch("builtins.input", return_value="n"):
            result = core.drop_table(self.metadata, "users")

        self.assertIsNone(result)
        self.assertIn("users", self.metadata)

    def test_parser_preserves_comma_inside_string(self):
        command, arguments = parse_command(
            'insert into users values ("Анна, Мария", 23, false)'
        )

        self.assertEqual(command, "insert")
        self.assertEqual(
            arguments["values"],
            ["Анна, Мария", 23, False],
        )

    def test_parser_supports_multiple_assignments(self):
        command, arguments = parse_command(
            'update users set age = 29, name = "Anna" where ID = 1'
        )

        self.assertEqual(command, "update")
        self.assertEqual(
            arguments["set_clause"],
            {"age": 29, "name": "Anna"},
        )
        self.assertEqual(arguments["where_clause"], {"ID": 1})

    def test_unquoted_string_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_value("Sergei")

    def test_cacher_calculates_result_once(self):
        calls = []
        cached = create_cacher()

        def calculate():
            calls.append("called")
            return [{"value": 1}]

        first = cached("key", calculate)
        first[0]["value"] = 99
        second = cached("key", calculate)

        self.assertEqual(calls, ["called"])
        self.assertEqual(second, [{"value": 1}])

    def test_cli_persists_crud_operations(self):
        execute("create_table people name:str age:int is_active:bool")
        execute('insert into people values ("Anna", 23, true)')
        execute("update people set age = 24 where ID = 1")

        self.assertEqual(load_table_data("people")[0]["age"], 24)

        with patch("builtins.input", return_value="y"):
            execute("delete from people where ID = 1")

        self.assertEqual(load_table_data("people"), [])

        with patch("builtins.input", return_value="y"):
            execute("drop_table people")

        self.assertNotIn("people", load_metadata(METADATA_FILE))
        self.assertFalse(get_table_path("people").exists())

    def test_unknown_column_is_rejected_without_saving(self):
        execute("create_table people name:str age:int is_active:bool")
        execute('insert into people values ("Anna", 23, true)')
        execute("update people set unknown = 1 where ID = 1")

        row = load_table_data("people")[0]

        self.assertNotIn("unknown", row)
        self.assertEqual(row["age"], 23)


if __name__ == "__main__":
    unittest.main()
