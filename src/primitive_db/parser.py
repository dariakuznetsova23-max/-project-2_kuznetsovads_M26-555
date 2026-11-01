import ast
import re
import shlex

from primitive_db.utils import validate_identifier

TOKEN_PATTERN = re.compile(
    r"""
    \s*(
        "(?:\\.|[^"\\])*"
        |
        '(?:\\.|[^'\\])*'
        |
        [(),=]
        |
        [^\s(),="'\\]+
    )
    """,
    re.VERBOSE,
)

INTEGER_PATTERN = re.compile(r"[+-]?[0-9]+")


def tokenize(text):
    """Split a CRUD command while preserving quoted strings."""
    text = text.strip()
    tokens = []
    position = 0

    while position < len(text):
        match = TOKEN_PATTERN.match(text, position)

        if match is None:
            raise ValueError(f"Некорректный фрагмент команды: {text[position:]}")

        tokens.append(match.group(1))
        position = match.end()

    return tokens


def parse_value(token):
    """Parse a quoted string, integer, or boolean."""
    if token.startswith(("'", '"')):
        try:
            value = ast.literal_eval(token)
        except (SyntaxError, ValueError) as error:
            raise ValueError(f"Некорректная строка: {token}") from error

        if type(value) is not str:
            raise ValueError("Строковое значение должно быть строкой.")

        return value

    if INTEGER_PATTERN.fullmatch(token):
        return int(token)

    if token.lower() == "true":
        return True

    if token.lower() == "false":
        return False

    raise ValueError(
        f"Некорректное значение: {token}. "
        "Строки заключайте в кавычки; "
        "числа и true/false вводите без кавычек."
    )


def _take(tokens):
    """Take the next token."""
    if not tokens:
        raise ValueError("Команда не завершена.")

    return tokens.pop(0)


def _expect(tokens, expected):
    """Take and validate a keyword or punctuation token."""
    actual = _take(tokens)

    if actual.lower() != expected.lower():
        raise ValueError(f"Ожидалось {expected}, получено {actual}.")


def _assignment(tokens):
    """Parse one column = value expression."""
    column = validate_identifier(_take(tokens))
    _expect(tokens, "=")
    value = parse_value(_take(tokens))

    return column, value


def _where(tokens):
    """Parse a required WHERE clause with one equality."""
    _expect(tokens, "where")
    column, value = _assignment(tokens)

    return {column: value}


def _finish(tokens):
    """Reject unexpected trailing tokens."""
    if tokens:
        raise ValueError(f"Лишние аргументы: {' '.join(tokens)}")


def _parse_crud(text):
    """Parse insert, select, update, and delete commands."""
    tokens = tokenize(text)
    command = _take(tokens).lower()

    if command == "insert":
        _expect(tokens, "into")
        table_name = validate_identifier(_take(tokens))
        _expect(tokens, "values")
        _expect(tokens, "(")

        values = []

        if tokens and tokens[0] != ")":
            values.append(parse_value(_take(tokens)))

            while tokens and tokens[0] == ",":
                _take(tokens)
                values.append(parse_value(_take(tokens)))

        _expect(tokens, ")")
        _finish(tokens)

        return command, {
            "table_name": table_name,
            "values": values,
        }

    if command == "select":
        _expect(tokens, "from")
        table_name = validate_identifier(_take(tokens))
        where_clause = _where(tokens) if tokens else None
        _finish(tokens)

        return command, {
            "table_name": table_name,
            "where_clause": where_clause,
        }

    if command == "update":
        table_name = validate_identifier(_take(tokens))
        _expect(tokens, "set")

        column, value = _assignment(tokens)
        set_clause = {column: value}

        while tokens and tokens[0] == ",":
            _take(tokens)
            column, value = _assignment(tokens)

            if column in set_clause:
                raise ValueError(f"Столбец {column} указан повторно.")

            set_clause[column] = value

        where_clause = _where(tokens)
        _finish(tokens)

        return command, {
            "table_name": table_name,
            "set_clause": set_clause,
            "where_clause": where_clause,
        }

    if command == "delete":
        _expect(tokens, "from")
        table_name = validate_identifier(_take(tokens))
        where_clause = _where(tokens)
        _finish(tokens)

        return command, {
            "table_name": table_name,
            "where_clause": where_clause,
        }

    raise ValueError(f"Функции {command} нет. Попробуйте снова.")


def parse_command(text):
    """Return the command name and parsed arguments."""
    parts = shlex.split(text, comments=False, posix=True)

    if not parts:
        raise ValueError("Введите команду.")

    command = parts[0].lower()

    if command in {"insert", "select", "update", "delete"}:
        return _parse_crud(text)

    if command == "create_table":
        if len(parts) < 3:
            raise ValueError("Формат: create_table <таблица> <столбец:тип> ...")

        return command, {
            "table_name": validate_identifier(parts[1]),
            "columns": parts[2:],
        }

    if command in {"drop_table", "info"}:
        if len(parts) != 2:
            raise ValueError(f"Формат: {command} <таблица>")

        return command, {
            "table_name": validate_identifier(parts[1]),
        }

    if command in {"list_tables", "help", "exit"}:
        if len(parts) != 1:
            raise ValueError(f"Команда {command} не принимает аргументы.")

        return command, {}

    raise ValueError(f"Функции {parts[0]} нет. Попробуйте снова.")
