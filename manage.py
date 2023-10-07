import sys
from functools import wraps
# from .test import main

metadata = None


def make_migrations(module_name, obj_name):
    print(module_name, obj_name)
    module = __import__(module_name)  # Импортируем модуль module_name
    obj = getattr(module, obj_name)  # Получаем класс A из модуля
    print('obj is', obj)
    metadata = obj.builder.metadata


commands = {
    'make_migrations': make_migrations,
}


def check_command_name(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'command' in kwargs.keys():

            if kwargs['command'] in commands.keys():
                return func(*args, **kwargs)
            return 'Invalid command name'
        return "Command name required, use 'python manage.py help' to see all commands"
    return wrapper


@check_command_name
def execute_command_with_kwarg(command=None, key=None, value=None):
    return commands[command](key, value)


@check_command_name
def execute_command_with_arg(command=None, argument=None):
    return commands[command](argument)


@check_command_name
def execute_command_without_args(command=None):
    return commands[command]()


if __name__ == '__main__':
    args = sys.argv[1:]
    for arg in args:
        if '=' in arg:
            command, argument = arg.split('=')
            key, value = None, None
            if argument != '':
                if ':' in argument:
                    key, value = argument.split(':')
                    print(command, key, value)
                    execute_command_with_kwarg(command=command, key=key, value=value)
                else:
                    execute_command_with_arg(command=command, argument=argument)
        else:
            command = arg
            execute_command_without_args(command=command)

