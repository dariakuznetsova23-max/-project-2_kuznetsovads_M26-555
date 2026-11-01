import prompt
from prettytable import PrettyTable

from primitive_db import core
from primitive_db.decorators import handle_db_errors
from primitive_db.parser import parse_command
from primitive_db.utils import (
    METADATA_FILE,
    get_table_path,
    load_metadata,
    load_table_data,
    save_metadata,
    save_table_data,
)


def print_help():
    """Print the complete command reference."""
    print("\n***База данных***")
    print("\nУправление таблицами:")
    print("create_table <таблица> <столбец:тип> ... - создать таблицу")
    print("list_tables - показать список таблиц")
    print("drop_table <таблица> - удалить таблицу")
    print("info <таблица> - информация о таблице")

    print("\nОперации с данными:")
    print("insert into <таблица> values (<значение>, ...) - добавить запись")
    print("select from <таблица> - показать все записи")
    print("select from <таблица> where <столбец> = <значение>")
    print("update <таблица> set <столбец> = <значение> where <столбец> = <значение>")
    print("delete from <таблица> where <столбец> = <значение>")

    print("\nОбщие команды:")
    print("help - справочная информация")
    print("exit - выход из программы")
    print("\nТипы: int, str, bool.")
    print("Строки — в кавычках. Булевы значения — true или false.")
    print("ID создаётся автоматически и не передаётся в insert.\n")


def welcome():
    """Print the application greeting."""
    print("\nДобро пожаловать в Primitive DB!")
    print_help()


def _print_rows(schema, rows):
    """Display rows using PrettyTable."""
    table = PrettyTable()
    table.field_names = list(schema)

    for row in rows:
        table.add_row([row[column] for column in schema])

    print(table)
    print(f"Найдено записей: {len(rows)}.")


def _create_table(metadata, arguments):
    """Create a schema and an empty data file."""
    table_name = arguments["table_name"]
    result = core.create_table(metadata, **arguments)

    if result is None:
        return

    save_table_data(table_name, [])
    save_metadata(METADATA_FILE, result)

    columns = ", ".join(
        f"{column}:{kind}" for column, kind in result[table_name].items()
    )

    print(f'Таблица "{table_name}" успешно создана со столбцами: {columns}')


def _drop_table(metadata, table_name):
    """Drop a schema and remove its data file."""
    result = core.drop_table(metadata, table_name)

    if result is None:
        return

    save_metadata(METADATA_FILE, result)
    get_table_path(table_name).unlink(missing_ok=True)

    print(f'Таблица "{table_name}" успешно удалена.')


def _execute_data_command(command, metadata, arguments):
    """Execute commands for an existing table."""
    table_name = arguments["table_name"]
    schema = core.get_schema(metadata, table_name)

    if schema is None:
        return

    if command == "insert":
        result = core.insert(metadata, table_name, arguments["values"])

        if result is not None:
            save_table_data(table_name, result)
            print(
                f"Запись с ID={result[-1]['ID']} "
                f'успешно добавлена в таблицу "{table_name}".'
            )

        return

    table_data = load_table_data(table_name)

    if command == "info":
        columns = ", ".join(f"{column}:{kind}" for column, kind in schema.items())
        print(f"Таблица: {table_name}")
        print(f"Столбцы: {columns}")
        print(f"Количество записей: {len(table_data)}")
        return

    where_clause = core.validate_clause(
        schema,
        arguments.get("where_clause"),
    )

    if where_clause is None:
        return

    if command == "select":
        result = core.select(table_data, where_clause)

        if result is not None:
            _print_rows(schema, result)

        return

    if command == "update":
        set_clause = core.validate_clause(
            schema,
            arguments["set_clause"],
            allow_id=False,
        )

        if set_clause is None:
            return

        matched = core.select(table_data, where_clause)

        if matched is None:
            return

        result = core.update(table_data, set_clause, where_clause)

        if result is not None:
            save_table_data(table_name, result)
            print(f"Успешно обновлено записей: {len(matched)}.")

        return

    if command == "delete":
        result = core.delete(table_data, where_clause)

        if result is not None:
            save_table_data(table_name, result)
            print(f"Успешно удалено записей: {len(table_data) - len(result)}.")


@handle_db_errors
def execute(user_input):
    """Parse and execute one command; False means exit."""
    command, arguments = parse_command(user_input)

    if command == "exit":
        return False

    if command == "help":
        print_help()
        return True

    metadata = load_metadata(METADATA_FILE)

    if command == "create_table":
        _create_table(metadata, arguments)
    elif command == "drop_table":
        _drop_table(metadata, arguments["table_name"])
    elif command == "list_tables":
        if not metadata:
            print("Таблиц пока нет.")

        for table_name in sorted(metadata):
            print(f"- {table_name}")
    else:
        _execute_data_command(command, metadata, arguments)

    return True


def run():
    """Run the interactive database loop."""
    welcome()

    while True:
        try:
            user_input = prompt.string("Введите команду: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if not user_input:
            continue

        if execute(user_input) is False:
            print("До свидания!")
            break
