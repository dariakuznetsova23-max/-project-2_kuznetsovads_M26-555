import json
import time

from primitive_db.constants import CACHE_LIMIT, CONFIRMATION_ANSWER


def _preserve_metadata(wrapper, original):
    """Preserve the decorated function name and documentation."""
    wrapper.__name__ = original.__name__
    wrapper.__doc__ = original.__doc__
    wrapper.__wrapped__ = original
    return wrapper


def handle_db_errors(func):
    """Handle database errors without terminating the command loop."""

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

    return _preserve_metadata(wrapper, func)


def confirm_action(action_name):
    """Request confirmation before performing a dangerous action."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            question = f'Вы уверены, что хотите выполнить "{action_name}"? [y/n]: '

            try:
                answer = input(question)
            except (EOFError, KeyboardInterrupt):
                print("\nОперация отменена.")
                return None

            if answer.strip().lower() != CONFIRMATION_ANSWER:
                print("Операция отменена.")
                return None

            return func(*args, **kwargs)

        return _preserve_metadata(wrapper, func)

    return decorator


def log_time(func):
    """Print the execution time of a function."""

    def wrapper(*args, **kwargs):
        started = time.monotonic()

        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - started
            print(f"Функция {func.__name__} выполнилась за {elapsed:.3f} секунд.")

    return _preserve_metadata(wrapper, func)


def create_cacher():
    """Create a bounded cache stored inside a closure."""
    cache = {}

    def cache_result(key, value_func):
        """Return an independent copy of a cached JSON-compatible result."""
        if key not in cache:
            if len(cache) >= CACHE_LIMIT:
                cache.clear()

            result = value_func()
            cache[key] = json.dumps(result, ensure_ascii=False)

        return json.loads(cache[key])

    return cache_result
