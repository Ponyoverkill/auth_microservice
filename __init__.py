from .src import AuthApp
from .src.fields import BaseField, LoginField, RegisterField, ContactField, IdentityField,\
    UserViewField, Permission
from .src.utils import hash_sha256, get_current_user
# import __main__ as __migrate_script__

LIB_NAME = 'fastapi_auth'