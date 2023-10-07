from typing import Any

from phonenumbers import PhoneNumber
from pydantic import BaseModel, EmailStr

from src.schemas import Permission
from src.fields import IdentityField, RegisterField, LoginField, BaseField, ContactField
from src.utils import hash_sha256


class Roles(BaseModel):
    admin: Any = Permission(action_1=True, action_2=True)
    client: Any = Permission(action_1=False, can_do_2=True)
    manager: Any = Permission(can_do_4=False, can_do_5=True)

    class Config:
        default = Permission(can_do_1=False, can_do_2=False)


class User(BaseModel):
    id: int = IdentityField()
    password: str = (RegisterField(hash_func=hash_sha256), LoginField(hash_func=hash_sha256))
    email: EmailStr = (ContactField(), LoginField(),
                       RegisterField())

    class Config:
        arbitrary_types_allowed = True
        database_schema = {
            'nullable': ['password', 'username', 'id'],
            'unique': ['username', 'email', 'id'],
        }