import json
from copy import deepcopy

from primitive_db.cache import create_cacher
from primitive_db.decorators import (
    confirm_action,
    handle_db_errors,
    log_time,
)
from primitive_db.utils import load_table_data, validate_identifier

SUPPORTED_TYPES = {
    "int": int,
    "str": str,
    "bool": bool,
}

cache_select = create_cacher()


def _schema(metadata, table_name):
    """Return an existing table schema."""
    validate_identifier(table_name)

    if table_name not in metadata:
        raise KeyError(table_name)

    schema = metadata[table_name]

    if not isinstance(schema, dict) or schema.get("ID") != "int":
        raise ValueError(f"Некорректная схема таблицы {table_name}.")

    if any(kind not in SUPPORTED_TYPES for kind in schema.values()):
        raise ValueError(f"Неизвестный тип в схеме таблицы {table_name}.")

    return schema


def _check_value(column, value, type_name):
    """Validate exact types, distinguishing bool from int."""
    expected_type = SUPPORTED_TYPES[type_name]

    if type(value) is not expected_type:
        raise ValueError(
            f"Столбец {column}: ожидается {type_name}, получено {type(value).__name__}."
        )


def _matches(row, where_clause):
    """Check whether a row satisfies all equalities."""
    if not where_clause:
        return True

    return all(
        key in row and type(row[key]) is type(value) and row[key] == value
        for key, value in where_clause.items()
    )


@handle_db_errors
def get_schema(metadata, table_name):
    """Return a copy of a table schema."""
    return dict(_schema(metadata, table_name))


@handle_db_errors
def validate_clause(schema, clause, allow_id=True):
    """Validate WHERE or SET values against a schema."""
    if clause is None:
        return {}

    for column, value in clause.items():
        if column not in schema:
            raise KeyError(column)

        if column == "ID" and not allow_id:
            raise ValueError("Столбец ID нельзя изменять.")

        _check_value(column, value, schema[column])

    return dict(clause)


@handle_db_errors
def create_table(metadata, table_name, columns):
    """Add a table schema with an automatic ID column."""
    validate_identifier(table_name)

    if table_name in metadata:
        raise ValueError(f'Таблица "{table_name}" уже существует.')

    if not columns:
        raise ValueError("Укажите хотя бы один пользовательский столбец.")

    schema = {"ID": "int"}

    for specification in columns:
        if specification.count(":") != 1:
            raise ValueError(
                f"Некорректный столбец: {specification}. Используйте имя:тип."
            )

        column, type_name = specification.split(":")
        validate_identifier(column)

        if type_name not in SUPPORTED_TYPES:
            raise ValueError(
                f"Некорректный тип: {type_name}. Допустимы int, str, bool."
            )

        if column.upper() == "ID":
            if column != "ID" or type_name != "int":
                raise ValueError(
                    "ID — зарезервированный столбец. Допустима только запись ID:int."
                )

            if list(columns).count("ID:int") > 1:
                raise ValueError("Столбец ID указан повторно.")

            continue

        if column in schema:
            raise ValueError(f"Столбец {column} указан повторно.")

        schema[column] = type_name

    if len(schema) == 1:
        raise ValueError("Укажите хотя бы один столбец помимо ID.")

    metadata[table_name] = schema
    return metadata


@handle_db_errors
@confirm_action("удаление таблицы")
def drop_table(metadata, table_name):
    """Remove a table schema after confirmation."""
    _schema(metadata, table_name)
    del metadata[table_name]

    return metadata


@handle_db_errors
@log_time
def insert(metadata, table_name, values):
    """Validate values and return rows with a new record."""
    schema = _schema(metadata, table_name)
    columns = [column for column in schema if column != "ID"]

    if len(values) != len(columns):
        raise ValueError(
            f"Ожидается значений: {len(columns)}, получено: {len(values)}. "
            "ID передавать не нужно."
        )

    for column, value in zip(columns, values, strict=True):
        _check_value(column, value, schema[column])

    table_data = load_table_data(table_name)

    for row in table_data:
        if type(row.get("ID")) is not int:
            raise ValueError("В файле таблицы обнаружен некорректный ID.")

    new_id = max((row["ID"] for row in table_data), default=0) + 1

    record = {"ID": new_id}
    record.update(zip(columns, values, strict=True))
    table_data.append(record)

    return table_data


@handle_db_errors
@log_time
def select(table_data, where_clause=None):
    """Return cached copies of matching rows."""
    cache_key = json.dumps(
        [table_data, where_clause],
        ensure_ascii=False,
        sort_keys=True,
    )

    return cache_select(
        cache_key,
        lambda: [deepcopy(row) for row in table_data if _matches(row, where_clause)],
    )


@handle_db_errors
def update(table_data, set_clause, where_clause):
    """Return rows with matching records updated."""
    if not where_clause:
        raise ValueError("Для update необходимо условие where.")

    if not set_clause:
        raise ValueError("Укажите изменяемые столбцы.")

    if "ID" in set_clause:
        raise ValueError("Столбец ID нельзя изменять.")

    result = deepcopy(table_data)

    for row in result:
        if _matches(row, where_clause):
            for column in set_clause:
                if column not in row:
                    raise KeyError(column)

            row.update(set_clause)

    return result


@handle_db_errors
@confirm_action("удаление записей")
def delete(table_data, where_clause):
    """Return rows without matching records after confirmation."""
    if not where_clause:
        raise ValueError("Для delete необходимо условие where.")

    return [deepcopy(row) for row in table_data if not _matches(row, where_clause)]
