import json
import shlex

from primitive_db.utils import validate_identifier


def tokenize(text):
    """Split a command while preserving quoted values."""
    tokens = []
    position = 0
    punctuation = "(),="

    while position < len(text):
        character = text[position]

        if character.isspace():
            position += 1
            continue

        if character in punctuation:
            tokens.append(character)
            position += 1
            continue

        if character in {"'", '"'}:
            quote = character
            start = position
            position += 1
            escaped = False

            while position < len(text):
                current = text[position]

                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    position += 1
                    tokens.append(text[start:position])
                    break

                position += 1
            else:
                raise ValueError("Незакрытая кавычка в строковом значении.")

            continue

        start = position

        while position < len(text):
            current = text[position]

            if current.isspace() or current in punctuation:
                break

            if current in {"'", '"'}:
                raise ValueError("Отделяйте строковые значения от других токенов.")

            position += 1

        tokens.append(text[start:position])

    return tokens


def parse_value(token):
    """Parse a string, an integer, or a boolean."""
    if token.startswith('"'):
        try:
            value = json.loads(token)
        except ValueError as error:
            raise ValueError(f"Некорректная строка: {token}") from error

        if type(value) is not str:
            raise ValueError("Ожидалось строковое значение.")

        return value

    if token.startswith("'"):
        try:
            values = shlex.split(token, comments=False, posix=True)
        except ValueError as error:
            raise ValueError(f"Некорректная строка: {token}") from error

        if len(values) != 1:
            raise ValueError(f"Некорректная строка: {token}")

        return values[0]

    number = token[1:] if token.startswith(("+", "-")) else token

    if number and number.isascii() and number.isdigit():
        return int(token)

    if token.lower() == "true":
        return True

    if token.lower() == "false":
        return False

    raise ValueError(
        f"Некорректное значение: {token}. "
        "Строки заключайте в кавычки, "
        "числа и true/false вводите без кавычек."
    )


def _take(tokens):
    """Take the next token."""
    if not tokens:
        raise ValueError("Команда не завершена.")

    return tokens.pop(0)


def _expect(tokens, expected):
    """Require a keyword or punctuation token."""
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
    """Parse one WHERE equality."""
    _expect(tokens, "where")
    column, value = _assignment(tokens)
    return {column: value}


def _finish(tokens):
    """Reject unexpected trailing arguments."""
    if tokens:
        raise ValueError(f"Лишние аргументы: {' '.join(tokens)}")


def _parse_crud(text):
    """Parse insert, select, update, or delete."""
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
    """Return a command name and its arguments."""
    text = text.strip()

    if not text:
        raise ValueError("Введите команду.")

    command = text.split(maxsplit=1)[0].lower()

    if command in {"insert", "select", "update", "delete"}:
        return _parse_crud(text)

    parts = shlex.split(text, comments=False, posix=True)

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
