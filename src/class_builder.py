import datetime
import uuid
from typing import Any, Tuple, Set, Dict, Union

from pydantic import BaseModel, create_model, EmailStr, Json
from pydantic_core import PydanticUndefined
from pydantic_extra_types.phone_numbers import PhoneNumber
from sqlalchemy import Column, Identity, Table, ForeignKey, MetaData, BigInteger, Boolean, \
    String, Float, DateTime, Time, Date, JSON, event
from sqlalchemy import UUID as sqlUUID
from sqlalchemy.ext.declarative import declarative_base

from .exceptions import InvalidModel
from .fields import LoginField, BaseField, RegisterField, IdentityField, ContactField
from .utils import xor_fields_maker, hash_validator_maker



type_dict = {
    int: BigInteger,
    bool: Boolean,
    str: String,
    uuid.UUID: sqlUUID(as_uuid=True),
    float: Float,
    datetime.datetime: DateTime,
    datetime.time: Time,
    datetime.date: Date,
    EmailStr: String,
    Json: JSON,
    PhoneNumber: String,
}


class ClassBuilder:
    def __init__(
            self,
            *args,
            user_model: BaseModel = None,
            role_model: BaseModel = None,
            **kwargs
    ):
        self.metadata = MetaData()
        self.Base = declarative_base(metadata=self.metadata)
        if not issubclass(user_model, BaseModel):
            raise InvalidModel('User model must be subclass of pydantic.BaseModel')
        if not issubclass(role_model, BaseModel):
            raise InvalidModel('Role model must be subclass of pydantic.BaseModel')

        self.user_model = user_model
        self.role_model = role_model
        self.login_fields = {}
        self.register_fields = {}
        self.user_fields = {}
        self.user_identity = None
        self.validators = {
            'login_schema': {'required_xor': [], 'hash': {}},
            'register_schema': {'required_xor': [], 'hash': {}}
        }
        self.contacts = {}
        self.perms_set = {}
        self.roles = {}
        self.user_sql_dict = {}
        self.parse_user()
        self.parse_roles()

    def add_validators(
            self,
            c_name: str = None,
            field: BaseField | LoginField | RegisterField = None
    ) -> None:

        types = {LoginField: 'login_schema', RegisterField: 'register_schema'}

        if 'required_xor' in field.dict.keys():
            xor_fields = {c_name} | field.dict['required_xor']
            if xor_fields not in self.validators[types[type(field)]]['required_xor']:
                self.validators[types[type(field)]]['required_xor'].append(xor_fields)
        if field.dict['hash_func'] is not None:
            self.validators[types[type(field)]]['hash'].update(
                {
                    c_name: field.dict['hash_func']
                }
            )

    def parse_roles(self) -> Tuple[Set[str], Dict[str, list[str]]] | None:
        perms_set = {}
        roles = {}
        for role_name, perms_info in self.role_model.model_fields.items():
            perms_set = perms_set | perms_info.default.dict.keys()
            roles.update(
                {
                    role_name: [i for i in perms_info.default.dict.keys()
                                if perms_info.default.dict[i] is True]
                }
            )
        if 'default' in self.role_model.model_config.keys():
            roles.update(
                {
                    'default': [*self.role_model.model_config['default'].dict]
                }
            )
            perms_set = perms_set | set(roles['default'])
        else:
            roles.update(
                {
                    'default': []
                }
            )

        self.perms_set = perms_set
        self.roles = roles

        return self.perms_set, self.roles

    def parse_user(self) -> None:
        identity_found = 0
        for c_name, c_info in self.user_model.model_fields.items():
            if self.user_identity is None:
                if isinstance(c_info.default, IdentityField):
                    identity_found += 1
                    self.user_identity = {
                        'c_name': c_name,
                        'type': type_dict[c_info.annotation]
                    }
                elif isinstance(c_info.default, tuple):
                    for i in c_info.default:
                        if isinstance(i, IdentityField):
                            identity_found += 1
                            self.user_identity = {
                                'c_name': c_name,
                                'type': type_dict[c_info.annotation]
                            }
        if identity_found > 1:
            raise InvalidModel('Only one IdentityField() required')
        if not self.user_identity:
            self.user_identity = {'c_name': 'id', 'type': type_dict[int]}

        for c_name, c_info in self.user_model.model_fields.items():
            if isinstance(c_info.default, ContactField):
                self.contacts.update(
                    {
                        c_name: c_info.default.dict['confirm_required']
                    }
                )
            if isinstance(c_info.default, tuple):
                for i in c_info.default:
                    if isinstance(i, ContactField):
                        self.contacts.update(
                            {
                                c_name: i.dict['confirm_required']
                            }
                        )

        for c_name, c_info in self.user_model.model_fields.items():
            if isinstance(c_info.default, tuple):
                field = c_info.default[0]
            elif isinstance(c_info.default, BaseField):
                field = c_info.default
            elif c_info.default is not PydanticUndefined:
                field = BaseField(default=c_info.default)
            else:
                field = BaseField(required=False)
            self.user_fields.update(field(c_name, Union[c_info.annotation, None], False))

        types = {LoginField: self.login_fields, RegisterField: self.register_fields}
        for _type in types.keys():
            for c_name, c_info in self.user_model.model_fields.items():
                field = None
                if isinstance(c_info.default, tuple):
                    for i in c_info.default:
                        if isinstance(i, _type):
                            field = i
                if isinstance(c_info.default, _type):
                    field = c_info.default
                if field:
                    types[_type].update(field(c_name, c_info.annotation))
                    self.add_validators(c_name, field)

    def build_schema(
            self,
            by_field_type: LoginField | RegisterField | BaseField = None
    ) -> BaseModel:
        _validators = {}
        types = {LoginField: 'login_schema', RegisterField: 'register_schema'}
        if by_field_type in types.keys():
            for i in range(len(self.validators[types[by_field_type]]['required_xor'])):
                _validators.update(
                    {
                        f'req_xor_{i}': xor_fields_maker(
                            *self.validators[types[by_field_type]]['required_xor'][i]
                        )
                    }
                )
            for c_name, hash_func in self.validators[types[by_field_type]]['hash'].items():
                _validators.update(
                    {
                        f'{c_name}_hash': hash_validator_maker(c_name, hash_func)
                    }
                )

        types = {
            LoginField: self.login_fields,
            RegisterField: self.register_fields,
            BaseField: self.user_fields
        }

        names = {
            LoginField: 'LoginUser',
            RegisterField: 'RegiserUser',
            BaseField: 'User'
        }

        return create_model(
            names[by_field_type],
            __config__={'arbitrary_types_allowed': True, 'from_attributes': True},
            __validators__=_validators,
            **types[by_field_type]
        )

    def build_schemas(self) -> Tuple[BaseModel, BaseModel, BaseModel]:
        user_schema = self.build_schema(BaseField)
        login_schema = self.build_schema(LoginField)
        register_schema = self.build_schema(RegisterField)
        return user_schema, login_schema, register_schema

    def build_sql_user_dict(self):
        for c_name, c_info in self.user_model.model_fields.items():
            nullable = True
            unique = False

            if 'nullable' in self.user_model.model_config['database_schema'].keys():
                if c_name in self.user_model.model_config['database_schema']['nullable']:
                    nullable = True

            if 'unique' in self.user_model.model_config['database_schema'].keys():
                if c_name in self.user_model.model_config['database_schema']['unique']:
                    unique = True

            self.user_sql_dict.update(
                {
                    c_name: {
                        'args': [
                            type_dict[c_info.annotation]
                        ],
                        'kwargs':
                            {
                                'unique': unique,
                                'nullable': nullable
                            }
                    }
                }
            )
        if self.user_identity['type'] is uuid.UUID:
            self.user_sql_dict.update(
                {
                    self.user_identity['c_name']: {
                        'args': [
                            self.user_identity['type']
                        ],
                        'kwargs':
                            {
                                'primary_key': True,
                                'default': uuid.uuid4
                            }
                    }
                }
            )
        elif self.user_identity['type'] is int:
            self.user_sql_dict.update(
                {
                    self.user_identity['c_name']: {
                        'args': [
                            self.user_identity['type'],
                            Identity(always=True)
                        ],
                        'kwargs':
                            {
                                'primary_key': True,
                            }
                    }
                }
            )
        else:
            self.user_sql_dict.update(
                {
                    self.user_identity['c_name']: {
                        'args': [
                            self.user_identity['type'],
                        ],
                        'kwargs':
                            {
                                'primary_key': True,
                            }
                    }
                }
            )

    def build_sql_models(
            self,
            schema_name: str = None
    ) -> Tuple[declarative_base, Table, Table]:

        self.build_sql_user_dict()

        class DbUser(self.Base):
            __tablename__ = self.user_model.__name__.lower()

            if schema_name:
                __table_args__ = {'schema': schema_name}

            for c_name, c_info in self.user_sql_dict.items():
                locals()[c_name] = Column(*c_info['args'], **c_info['kwargs'])
            if self.contacts:
                for contact, contact_confirm in self.contacts.items():
                    if contact_confirm:
                        locals()[f'{contact}_confirmed'] = Column(type_dict[bool], default=False)
            del locals()['c_name']
            del locals()['c_info']

        right_list = Table(
            'rights',
            self.metadata,
            Column('id', type_dict[int], Identity(always=True), primary_key=True),
            Column('name', type_dict[str], unique=True)
        )

        user_rights = Table(
            'user_rights',
            self.metadata,
            Column(
                'user_id',
                self.user_identity['type'],
                ForeignKey(f"{self.user_model.__name__.lower()}.{self.user_identity['c_name']}")),
            Column('right_id', type_dict[int], ForeignKey(right_list.c.id)),
            schema=schema_name,
        )

        return DbUser, user_rights, right_list, self.user_identity['c_name']

    def build_session_storage(self, schema_name: str = None) -> declarative_base:
        class Session(self.Base):
            __tablename__ = 'sessions'
            if schema_name:
                __table_args__ = {'schema': schema_name}

            id = Column(type_dict[uuid.UUID], primary_key=True, default=uuid.uuid4)
            user_id = Column(
                self.user_identity['type'],
                ForeignKey(f"{self.user_model.__name__.lower()}.{self.user_identity['c_name']}"),
                unique=True
            )
            access = Column(type_dict[uuid.UUID], unique=True, default=uuid.uuid4)
            refresh = Column(type_dict[uuid.UUID], unique=True, default=uuid.uuid4)

        return Session




