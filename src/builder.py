import uuid
from typing import Any, Tuple
from uuid import UUID

from pydantic import BaseModel, create_model
from pydantic_core import PydanticUndefined
from sqlalchemy import Column, Identity, Table, ForeignKey, MetaData
from sqlalchemy.ext.declarative import declarative_base

from src.config import type_dict
from src.exceptions import InvalidModel
from src.fields import LoginField, BaseField, RegisterField, IdentityField
from src.utils import xor_fields_maker, hash_validator_maker


class Builder:
    def __init__(
            self,
            *args,
            **kwargs
    ):
        self.metadata = MetaData()
        self.Base = declarative_base(metadata=self.metadata)

    @staticmethod
    def build_schema(model, field_class: Any) -> BaseModel:
        _dict = {}
        _validators_info = {'required_xor_fields': [], 'hash_validators': {}}
        _validators = {}

        if field_class is BaseField:
            for field_name, field_info in model.model_fields.items():
                if isinstance(field_info.default, tuple):
                    field = field_info.default[0]
                elif isinstance(field_info.default, BaseField):
                    field = field_info.default
                else:
                    if field_info.default is not PydanticUndefined:
                        field = BaseField(required=False, default=field_info.default)
                    else:
                        field = BaseField()
                _dict.update(field(name=field_name,
                                   type=field_info.annotation,
                                   required=False))

            _schema = create_model('User',
                                   __config__={'arbitrary_types_allowed': True},
                                   **_dict
            )
            return _schema

        for field_name, field_info in model.model_fields.items():
            field_found = False
            if isinstance(field_info.default, tuple):
                for i in field_info.default:
                    if isinstance(i, field_class):
                        field_found = True
                        field = i
            elif isinstance(field_info.default, field_class):
                field_found = True
                field = model.mofield_info
            if field_found:
                _dict.update(field(name=field_name, type=field_info.annotation))

                if 'required_xor_fields' in field.dict.keys():
                    xor_fields = {field_name} | field.dict['required_xor_fields']
                    if xor_fields not in _validators_info['required_xor_fields']:
                        _validators_info['required_xor_fields'].append(xor_fields)
                if field.dict['hash_func'] is not None:
                    _validators_info['hash_validators'].update(
                        {
                            field_name: field.dict['hash_func']
                        }
                    )

        _validators = {}
        for i in range(len(_validators_info['required_xor_fields'])):
            _validators.update(
                {
                    f'xor_validator{i}': xor_fields_maker(
                        *_validators_info['required_xor_fields'][i]
                    )
                }
            )
        for field_name, field_info in _validators_info['hash_validators'].items():
            _validators.update(
                {
                    f'{field_name}_hash_func': hash_validator_maker(
                        field_name,
                        field_info
                    )
                }
            )
        _schema = create_model(
            field_class.__name__,
            __config__={'arbitrary_types_allowed': True},
            __validators__=_validators,
            **_dict
        )
        return _schema

    def build_schemas(self, user_model: BaseModel) -> Tuple[BaseModel, BaseModel, BaseModel]:
        if issubclass(user_model, BaseModel):
            user_schema = self.build_schema(user_model, BaseField)
            login_schema = self.build_schema(user_model, LoginField)
            register_schema = self.build_schema(user_model, RegisterField)

            return user_schema, login_schema, register_schema
        raise InvalidModel('User model must be subclass of pydantic.BaseModel')

    def build_sql_models(
            self,
            user_model,
            role_model,
            schema_name: str = None
    ) -> Tuple[declarative_base, declarative_base, Table]:
        if not issubclass(user_model, BaseModel):
            raise InvalidModel('User schema must be subclass of BaseModel')
        if not issubclass(role_model, BaseModel):
            raise InvalidModel('Role schema must be subclass of BaseModel')
        user_dict = {}
        for c_name, c_info in user_model.model_fields.items():
            nullable = True
            unique = False
            if 'nullable' in user_model.model_config['database_schema'].keys():
                if c_name in user_model.model_config['database_schema']['nullable']:
                    nullable = True
            if 'unique' in user_model.model_config['database_schema'].keys():
                if c_name in user_model.model_config['database_schema']['unique']:
                    unique = True
            user_dict.update(
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
            if isinstance(c_info.default, IdentityField):
                _identity = (c_name, type_dict[c_info.annotation])
                if c_info.annotation is UUID:
                    user_dict.update(
                        {
                            c_name: {
                                'args': [
                                    type_dict[c_info.annotation]
                                ],
                                'kwargs':
                                    {
                                        'primary_key': True,
                                        'default': uuid.uuid4
                                }
                            }
                        }
                    )
                elif c_info.annotation is int:
                    user_dict.update(
                        {
                            c_name: {
                                'args': [
                                    type_dict[c_info.annotation],
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
                    user_dict.update(
                        {
                            c_name: {
                                'args': [
                                    type_dict[c_info.annotation],
                                ],
                                'kwargs':
                                    {
                                        'primary_key': True,
                                }
                            }
                        }
                    )

        if _identity is None:
            raise InvalidModel('Identity field required in user model')

        class DbUser(self.Base):
            __tablename__ = 'user'

            if schema_name:
                __table_args__ = {'schema': schema_name}

            for c_name, c_info in user_dict.items():
                locals()[c_name] = Column(*c_info['args'], **c_info['kwargs'])
            del locals()['c_name']
            del locals()['c_info']

        db_user = DbUser
        perms_set = {}
        for role_name, perms_info in role_model.model_fields.items():
            perms_set = perms_set | perms_info.default.dict.keys()

        class Rights(self.Base):
            __tablename__ = 'rights'
            if schema_name:
                __table_args__ = {'schema': schema_name}
            locals()['id'] = Column(
                type_dict[int],
                Identity(always=True),
                primary_key=True
            )
            locals()['right_name'] = Column(type_dict[str], unique=True)

        user_rights = Table(
            'user_rights',
            self.metadata,
            Column('user_id', _identity[1], ForeignKey(f'user.{_identity[0]}')),
            Column('right_id', type_dict[int], ForeignKey(Rights.id)),
            schema=schema_name,
        )

        return DbUser, Rights, user_rights







