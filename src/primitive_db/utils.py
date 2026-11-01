import json
import re
from pathlib import Path

METADATA_FILE = Path("db_meta.json")
DATA_DIR = Path("data")

IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def validate_identifier(value):
    """Validate a table or column name."""
    if not isinstance(value, str):
        raise ValueError("Имя должно быть строкой.")

    if IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(
            f"Некорректное имя: {value}. "
            "Используйте латинские буквы, цифры и подчёркивание; "
            "имя не должно начинаться с цифры."
        )

    return value


def _load_json(filepath, expected_type, default_factory):
    """Load JSON and check its top-level structure."""
    path = Path(filepath)

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return default_factory()

    if not isinstance(data, expected_type):
        raise ValueError(f"Некорректная структура JSON в файле {path}.")

    return data


def _save_json(filepath, data):
    """Replace a JSON file after writing a complete temporary file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")

    temporary_path.replace(path)


def load_metadata(filepath):
    """Return metadata or an empty dictionary if the file is absent."""
    return _load_json(filepath, dict, dict)


def save_metadata(filepath, data):
    """Save table schemas."""
    if not isinstance(data, dict):
        raise ValueError("Метаданные должны быть словарём.")

    _save_json(filepath, data)


def get_table_path(table_name):
    """Build a safe path to a table data file."""
    validate_identifier(table_name)
    return DATA_DIR / f"{table_name}.json"


def load_table_data(table_name):
    """Return table rows or an empty list if the file is absent."""
    data = _load_json(get_table_path(table_name), list, list)

    if any(not isinstance(row, dict) for row in data):
        raise ValueError("Каждая запись таблицы должна быть словарём.")

    return data


def save_table_data(table_name, data):
    """Save table rows."""
    if not isinstance(data, list):
        raise ValueError("Данные таблицы должны быть списком.")

    _save_json(get_table_path(table_name), data)
