import os
import runpy
import sys
from functools import wraps
from importlib import import_module, util
metadata = None
DB_URL = None


def migrate(url, **kwargs):
    for k, v in kwargs.items():
        module_name = k
        obj_name = v
        break
    for path in sys.path:
        if 'fastapi_auth' in path:
            lib_path = path
            break

    with open(f'{lib_path}/settings', 'w') as f:
        f.write(f'{module_name} {obj_name} {os.getcwd()} {url}')

    sys.path.append(os.getcwd())
    module = __import__(module_name)
    perms = getattr(module, obj_name).permissions
    permissions = []
    for p in perms:
        permissions.append({'name': p})

    os.chdir(lib_path)
    versions = './migrations/versions'
    os.system('alembic revision --autogenerate')
    with open(f"{lib_path}/migrations/versions/{os.listdir(path=versions)[0]}", 'r') as f:
        old_file = f.read()
    with open(f"{lib_path}/script.by.ponyoverkill", 'r') as f:
        some_changes = f.read()
    new_file = old_file.replace('    # ### end Alembic commands ###', some_changes, 1)
    with open(f"{lib_path}/migrations/versions/{os.listdir(path=versions)[0]}", 'w') as f:
        f.write(new_file)

    os.system('alembic upgrade head')
    # os.remove(f'{lib_path}/settings')


def delete_migration(url, **kwargs):
    for path in sys.path:
        if 'fastapi_auth' in path:
            lib_path = path
            break
    os.chdir(lib_path)
    os.system('alembic downgrade base')
    versions = './migrations/versions'
    os.remove(f"{lib_path}/{versions}/{os.listdir(path=f'{lib_path}{versions}')[0]}")


commands = {
    'migrate': migrate,
    'delete_migration': delete_migration,
    'help': None
}


def check_command_name(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if '_name' in kwargs.keys():

            if kwargs['_name'] in commands.keys():
                return func(*args, **kwargs)
            print('Invalid command name')
            exit()
        print("Command name required, use 'python manage.py help' to see all commands")
        exit()
    return wrapper


@check_command_name
def execute_command(*args, _name: str, **kwargs):
    return commands[_name](*args, **kwargs)


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print("Command name required, use 'python fastapi_auth help' to see all commands")
        exit()
    command_found = False
    for k in commands.keys():
        if k in args:
            command_found = True
    if not command_found:
        print("Wrong command, use 'python fastapi_auth help' to see all commands")
        exit()
    command_indexes = []
    for arg in args:
        if arg in commands.keys():
            command_indexes.append(args.index(arg))
    command_indexes.append(len(args))
    for i in range(len(command_indexes)-1):
        arguments = []
        kw_arguments = {}
        df = '12345'
        for j in range(command_indexes[i]+1, command_indexes[i+1]):
            if '[' and ']' in args[j]:
                if ':' in args[j]:
                    key, value = args[j][1:-1].split(':')
                    kw_arguments.update({key: value})
                else:
                    arguments.append(args[j][1:-1])
            elif '=' in args[j]:
                key, value = args[j].split('=')
                kw_arguments.update({key: value})
            else:
                arguments.append(args[j])
        execute_command(*arguments, _name=args[i], **kw_arguments)

