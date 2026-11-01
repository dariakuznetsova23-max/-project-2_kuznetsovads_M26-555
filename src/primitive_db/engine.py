import prompt


def print_help():
    """Print available commands."""
    print("exit - выйти из программы")
    print("help - справочная информация")


def welcome():
    """Run the initial command loop."""
    print("\nПервая попытка запустить проект!")
    print_help()

    while True:
        try:
            command = prompt.string("Введите команду: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if command == "exit":
            print("До свидания!")
            break

        if command == "help":
            print_help()
        else:
            print(f"Функции {command} нет. Попробуйте снова.")
