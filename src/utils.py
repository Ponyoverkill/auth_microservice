import hashlib
from functools import wraps
from typing import Callable, Any

from pydantic import field_validator, model_validator

from fastapi_auth.src.exceptions import ArgumentsError


def hash_sha256(some_string: str) -> str:
    return hashlib.sha3_256(some_string.encode('utf-8')).hexdigest()


def xor_fields_maker(*field_names: str):
    def check_xor_fields(data: Any):
        count = 0
        for f_name in field_names:
            if getattr(data, f_name) is not None:
                count += 1
            if count > 1:
                break

        if count == 0:
            raise ValueError('fields required')
        if count == 1:
            return data
        if count > 1:
            raise ValueError('Only one field required!')
    return model_validator(mode='after')(check_xor_fields)


def hash_validator_maker(field_name: str, hash_func: Callable[[str], str]):
    if not callable(hash_func):
        raise ValueError(f'hash_func must be callable, not {type(hash_func)}')
    return field_validator(field_name)(hash_func)


def get_current_user():
    pass

