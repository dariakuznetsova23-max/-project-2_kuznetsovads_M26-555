import time
from functools import wraps


def handle_db_errors(func):
    """Handle database errors and return None on failure."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as error:
            print(f"Ошибка: Файл данных не найден. {error}")
        except KeyError as error:
            print(f"Ошибка: Таблица или столбец {error.args[0]} не найден.")
        except ValueError as error:
            print(f"Ошибка валидации: {error}")
        except OSError as error:
            print(f"Ошибка работы с файлами: {error}")
        except Exception as error:
            print(f"Произошла непредвиденная ошибка: {error}")

        return None

    return wrapper


def confirm_action(action_name):
    """Ask for confirmation before a dangerous operation."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            question = f'Вы уверены, что хотите выполнить "{action_name}"? [y/n]: '

            try:
                answer = input(question)
            except (EOFError, KeyboardInterrupt):
                print("\nОперация отменена.")
                return None

            if answer.strip().lower() != "y":
                print("Операция отменена.")
                return None

            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_time(func):
    """Print function execution time."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        started = time.monotonic()

        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - started
            print(f"Функция {func.__name__} выполнилась за {elapsed:.3f} секунд.")

    return wrapper
