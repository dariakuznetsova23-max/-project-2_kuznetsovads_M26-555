import json
import os

from primitive_db.constants import (
    DATA_DIR,
    ENCODING,
    JSON_INDENT,
    TEMP_SUFFIX,
)


def validate_identifier(value):
    """Validate a table or column name."""
    if not isinstance(value, str) or not value:
        raise ValueError("Имя должно быть непустой строкой.")

    if not value.isascii():
        raise ValueError("В именах используйте только латинские буквы.")

    if not (value[0].isalpha() or value[0] == "_"):
        raise ValueError("Имя должно начинаться с буквы или подчёркивания.")

    if not all(character.isalnum() or character == "_" for character in value):
        raise ValueError("Имя может содержать только буквы, цифры и подчёркивание.")

    return value


def _load_json(filepath, expected_type, default_factory):
    """Read a JSON file and validate its top-level structure."""
    try:
        with open(filepath, encoding=ENCODING) as file:
            data = json.load(file)
    except FileNotFoundError:
        return default_factory()

    if not isinstance(data, expected_type):
        raise ValueError(f"Некорректная структура JSON в файле {filepath}.")

    return data


def _save_json(filepath, data):
    """Write JSON to a temporary file and replace the destination."""
    parent = os.path.dirname(filepath)

    if parent:
        os.makedirs(parent, exist_ok=True)

    temporary_path = f"{filepath}{TEMP_SUFFIX}"

    with open(temporary_path, "w", encoding=ENCODING) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=JSON_INDENT,
        )
        file.write("\n")

    os.replace(temporary_path, filepath)


def load_metadata(filepath):
    """Return database metadata or an empty dictionary."""
    return _load_json(filepath, dict, dict)


def save_metadata(filepath, data):
    """Save database metadata."""
    if not isinstance(data, dict):
        raise ValueError("Метаданные должны быть словарём.")

    _save_json(filepath, data)


def get_table_path(table_name):
    """Return a validated path to a table data file."""
    validate_identifier(table_name)
    return os.path.join(DATA_DIR, f"{table_name}.json")


def load_table_data(table_name):
    """Return table records or an empty list."""
    records = _load_json(get_table_path(table_name), list, list)

    if any(not isinstance(record, dict) for record in records):
        raise ValueError("Каждая запись таблицы должна быть словарём.")

    return records


def save_table_data(table_name, data):
    """Save table records."""
    if not isinstance(data, list):
        raise ValueError("Данные таблицы должны быть списком.")

    _save_json(get_table_path(table_name), data)
