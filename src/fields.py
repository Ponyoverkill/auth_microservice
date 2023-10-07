from typing import Tuple, Set, Type, Callable

from pydantic import BaseModel
from pydantic.fields import FieldInfo


class Permission:
    def __init__(self, **permissions):
        self.dict = permissions


class BaseField:

    def __init__(
            self,
            *,
            required: bool = True,
            required_xor: Set[str] = None,
            **kwargs
    ) -> None:
        self.dict = {}
        self._required = required

        if 'default' in kwargs.keys():
            self._default = kwargs['default']
            self._required = False
            self.dict.update(
                {
                    'default': self._default,
                    'required': self._required
                }
            )
        elif not self._required:
            self._default = None
            self.dict.update(
                {
                    'default': self._default
                }
            )
        if required_xor:
            self._required_xor = required_xor
            self._required = False
            self._default = None
            self.dict.update(
                {
                    'required': self._required,
                    'required_xor': self._required_xor,
                    'default': self._default
                }
            )
        self.dict.update({'required': self._required})
        self.dict.update(**kwargs)

    def __call__(self, name: str, type: Type, required: bool = None):
        if required is True:
            return {name: (type, FieldInfo(annotation=type, required=True))}
        if required is False:
            if 'default' in self.dict.keys():
                return {name: (
                    type,
                    FieldInfo(annotation=type, required=False, default=self._default)
                )
                }
            return {name:
                    (type, FieldInfo(annotation=type, required=False, default=None))
                    }
        if required is None:
            if 'default' not in self.dict.keys():
                if self._required:
                    return {name:
                            (type, FieldInfo(annotation=type, required=self._required))
                            }
                return {name:
                        (type, FieldInfo(annotation=type, required=False, default=None))
                        }
            return {name:
                    (type,
                     FieldInfo(
                         annotation=type,
                         required=self._required,
                         default=self._default)
                     )
                    }
        # @dataclass
        # class SchemaField:
        #     locals()['__annotations__'] = {field_name: field_type}
        #     if not self._required:
        #         if self._default:
        #             locals()[field_name] = self._default
        #         else:
        #             locals()[field_name] = None
        #
        #
        # @dataclass
        # class SqlField:
        #     pass
        #
        # self.schema_field = SchemaField
        # self.sql_field = SqlField
# class RoleField(BaseField):
#     def __init__(self, *args, **kwargs):
#


class IdentityField(BaseField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ContactField(BaseField):
    def __init__(
            self,
            confirm_required: bool = False,
            required: bool = False,
            required_xor: Set[str] = None,
            **kwargs
    ):
        super().__init__(
            required_xor=None,
            required=required,
            confirm_required=confirm_required,
            **kwargs
        )


class LoginField(BaseField):

    def __init__(
            self,
            required_xor: Set[str] = None,
            hash_func: Callable[[str], str] = None,
            **kwargs
    ):
        super().__init__(
            required_xor=required_xor,
            hash_func=hash_func,
            **kwargs
        )


class RegisterField(BaseField):
    def __init__(
            self,
            required: bool = True,
            required_xor: Tuple[str] = None,
            hash_func: Callable[[str], str] = None,
            **kwargs
    ):
        super().__init__(
            required=required,
            required_xor=required_xor,
            hash_func=hash_func,
            **kwargs
        )


class UserViewField(BaseField):
    def __init__(
            self,
            *args,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
