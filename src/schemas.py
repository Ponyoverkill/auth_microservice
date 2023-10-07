from typing import Any

from pydantic import BaseModel, EmailStr
from pydantic_extra_types.phone_numbers import PhoneNumber

from .fields import Permission, IdentityField, RegisterField, LoginField, BaseField,\
    ContactField
from .utils import hash_sha256


class Roles(BaseModel):
    role1: Any = Permission(can_do_1=True, can_do_2=False)
    role2: Any = Permission(can_do_1=False, can_do_2=True)
    role3: Any = Permission(can_do_4=False, can_do_5=True)

    class Config:
        default = Permission(can_do_1=False, can_do_2=False, can_do_10=False)


class User(BaseModel):
    id: int = (IdentityField())
    password: str = (RegisterField(hash_func=hash_sha256), LoginField(hash_func=hash_sha256))
    username: str = (LoginField(required_xor={'email', 'phone'}),
                     RegisterField(required_xor={'email', 'phone'}))
    field: str = (BaseField(default='empty'))
    email: EmailStr = (ContactField(),
                       LoginField(required_xor={'username', 'phone'}),
                       RegisterField(required_xor={'username', 'phone'}))
    phone: PhoneNumber = (ContactField(required_xor={'email'}),
                          LoginField(required_xor={'username', 'email'}),
                          RegisterField(required_xor={'username', 'email'}))
    discord: str = (ContactField())

    class Config:
        arbitrary_types_allowed = True
        database_schema = {
            'nullable': ['password', 'username', 'id'],
            'unique': ['username', 'email', 'phone', 'id'],
        }

