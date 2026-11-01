import os
import time

from primitive_db import core, decorators
from primitive_db.constants import META_FILE
from primitive_db.decorators import create_cacher
from primitive_db.engine import execute
from primitive_db.parser import parse_command, parse_value
from primitive_db.utils import (
    get_table_path,
    load_metadata,
    load_table_data,
    save_metadata,
    save_table_data,
)


def test_metadata():
    """Check missing metadata and a JSON round trip."""
    assert load_metadata(META_FILE) == {}

    metadata = core.create_table({}, "users", ["name:str", "age:int"])

    assert list(metadata["users"]) == ["ID", "name", "age"]

    save_metadata(META_FILE, metadata)

    assert load_metadata(META_FILE) == metadata
    assert core.create_table(metadata, "users", ["name:str"]) is None
    assert core.create_table({}, "bad", ["price:float"]) is None


def test_parser():
    """Check quoted strings, booleans, and update assignments."""
    command, arguments = parse_command(
        'insert into users values ("Анна, Мария", 23, false)'
    )

    assert command == "insert"
    assert arguments["values"] == ["Анна, Мария", 23, False]

    command, arguments = parse_command(
        'update users set age = 29, name = "Anna" where ID = 1'
    )

    assert command == "update"
    assert arguments["set_clause"] == {"age": 29, "name": "Anna"}
    assert arguments["where_clause"] == {"ID": 1}

    try:
        parse_value("Anna")
    except ValueError:
        pass
    else:
        raise AssertionError("Строка без кавычек должна отклоняться.")


def test_insert():
    """Check automatic IDs, required fields, and exact types."""
    metadata = core.create_table(
        {},
        "records",
        ["name:str", "age:int", "active:bool"],
    )

    first = core.insert(metadata, "records", ["Anna", 23, True])
    assert first[0]["ID"] == 1

    save_table_data("records", first)

    second = core.insert(metadata, "records", ["Sergei", 28, False])
    assert [row["ID"] for row in second] == [1, 2]

    assert core.insert(metadata, "records", ["Wrong", True, True]) is None
    assert core.insert(metadata, "records", ["Only name"]) is None


def test_select_and_update():
    """Check filtering, cache freshness, and independent updates."""
    rows = [
        {"ID": 1, "age": 20},
        {"ID": 2, "age": 30},
    ]

    selected = core.select(rows, {"age": 20})
    assert selected == [{"ID": 1, "age": 20}]

    updated = core.update(rows, {"age": 21}, {"ID": 1})

    assert updated[0]["age"] == 21
    assert rows[0]["age"] == 20
    assert core.update(rows, {"ID": 9}, {"ID": 1}) is None

    rows[0]["age"] = 22

    assert core.select(rows, {"age": 20}) == []


def test_cache():
    """Check that a cached calculation runs once."""
    calls = []
    cached = create_cacher()

    def calculate():
        """Return a value and count the calculation."""
        calls.append("called")
        return [{"value": 1}]

    first = cached("key", calculate)
    first[0]["value"] = 99

    second = cached("key", calculate)

    assert calls == ["called"]
    assert second == [{"value": 1}]


def test_confirmation():
    """Check cancelled and confirmed record deletion."""
    rows = [{"ID": 1, "age": 20}]

    try:
        decorators.input = lambda question: "n"
        assert core.delete(rows, {"ID": 1}) is None

        decorators.input = lambda question: "y"
        assert core.delete(rows, {"ID": 1}) == []
    finally:
        del decorators.input

    assert rows == [{"ID": 1, "age": 20}]


def test_cli():
    """Check persistent CRUD operations through the command engine."""
    execute("create_table people name:str age:int active:bool")
    execute('insert into people values ("Anna", 23, true)')
    execute("update people set age = 24 where ID = 1")

    assert load_table_data("people")[0]["age"] == 24

    execute("update people set unknown = 1 where ID = 1")

    assert "unknown" not in load_table_data("people")[0]

    try:
        decorators.input = lambda question: "y"

        execute("delete from people where ID = 1")
        assert load_table_data("people") == []

        execute("drop_table people")
        assert "people" not in load_metadata(META_FILE)
        assert not os.path.exists(get_table_path("people"))
    finally:
        del decorators.input


def run_tests():
    """Run functional tests inside a dedicated temporary directory."""
    original_directory = os.getcwd()
    directory_name = f".db-test-{os.getpid()}-{time.time_ns()}"
    test_directory = os.path.join(original_directory, directory_name)

    os.mkdir(test_directory)

    tests = [
        test_metadata,
        test_parser,
        test_insert,
        test_select_and_update,
        test_cache,
        test_confirmation,
        test_cli,
    ]

    try:
        os.chdir(test_directory)

        for test in tests:
            test()
            print(f"PASSED: {test.__name__}")

        print(f"\nУспешно выполнено тестов: {len(tests)}.")
    finally:
        os.chdir(original_directory)

        for root, directories, files in os.walk(
            test_directory,
            topdown=False,
        ):
            for filename in files:
                os.remove(os.path.join(root, filename))

            for directory in directories:
                os.rmdir(os.path.join(root, directory))

        os.rmdir(test_directory)


if __name__ == "__main__":
    run_tests()
