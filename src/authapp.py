import datetime
from functools import wraps
from typing import Union, AsyncGenerator, Callable, Generator, Any, Annotated
from uuid import UUID
from contextlib import asynccontextmanager

import jwt
import sqlalchemy
from fastapi import Depends, APIRouter, Cookie
from pydantic import BaseModel
from sqlalchemy import Column, select
from sqlalchemy.exc import NoResultFound
# from sqlalchemy.orm.session import se
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse
import jwt

from .build_route import build_async
from .class_builder import ClassBuilder
from .exceptions import DataBaseNotFound, DatabaseError, ArgumentsError
from .method_builders import SyncMethodBuilder, AsyncMethodBuilder
from .schemas import User, Roles


# class GlobalStorage:
#     def __init__(self, **kwargs):
#         for k, v in kwargs.items():
#             setattr(self, k, v)
#         print(self.__dict__)
#
#
# global_storage = GlobalStorage(sessionMaker=None, session=None)


class AuthApp:

    get_session = None

    def __init__(
            self,
            *,
            prefix: str = '/user',
            session_maker: sessionmaker = None,
            sql_schema_name: str = None,
            async_usage: bool = None,
            user_model: BaseModel = User,
            role_model: BaseModel = Roles,
            use_session_auth: bool = None,
            use_jwt_auth: bool = None,
            jwt_secret_key: str = None,
            redis: Any = None,
            ):
        self.__prefix = prefix
        if use_session_auth is not None and use_jwt_auth is not None\
                and use_jwt_auth == use_session_auth:
            raise ArgumentsError('Only one of use_session_auth, use_jwt_auth required')
        if use_session_auth is None and use_jwt_auth is None:
            use_session_auth = True
            use_jwt_auth = False
        if use_session_auth is not None:
            use_jwt_auth = not use_session_auth
        if use_jwt_auth is not None:
            use_session_auth = not use_jwt_auth

        self._use_session = use_session_auth
        self._use_jwt = use_jwt_auth
        if not sessionmaker:
            raise ArgumentsError('AuthApp needs sessionmaker argument')
        if not isinstance(session_maker, sessionmaker):
            raise ArgumentsError(
                f'AuthApp session_maker must be an instance of sqlalchemy.orm.sessionmaker,'
                f' not {type(session_maker)}')

        self.__sessionmaker = session_maker

        if issubclass(self.__sessionmaker.class_, Session):
            if async_usage is not None:
                self.async_usage = async_usage
            else:
                self.async_usage = False
            self.session = self.get_sync_session
            self.__methods_builder = SyncMethodBuilder(self._use_session, self._use_jwt)
        if issubclass(self.__sessionmaker.class_, AsyncSession):
            if async_usage is False:
                raise ArgumentsError("Can't use AsyncSession with async_usage=False")
            if async_usage is None:
                async_usage = True
            self.async_usage = async_usage
            self.session = self.get_async_session
            self.__methods_builder = AsyncMethodBuilder(self._use_session, self._use_jwt)
        elif issubclass(self.__sessionmaker.class_, AsyncSession) and self.async_usage is False:
            raise ArgumentsError("Can't use AsyncSession with async_usage=False")

        self.__sessionmaker = session_maker

        self._use_session = use_session_auth
        self._use_jwt = use_jwt_auth

        self.__class_builder = ClassBuilder(user_model=user_model, role_model=role_model)

        self.user_model, self.login_model, self.register_model = \
            self.__class_builder.build_schemas()

        self.user_db, self.user_rights_db, self.right_list, self._identity_column = \
            self.__class_builder.build_sql_models(sql_schema_name)

        if self._use_session is True:
            if redis is None:
                self._sessions = self.__class_builder.build_session_storage(sql_schema_name)
            else:
                self.get_session = self.throw_self(self.__methods_builder.build_get_session(redis=redis))
        if self._use_jwt is True:
            self._secret_key = jwt_secret_key

        self.metadata = self.__class_builder.metadata
        self.permissions, self.roles = self.__class_builder.parse_roles()

        if self.async_usage is True:
            self.router = self.__async_router()


        # self.__methods_builder = MethodBuilder(self.session,
        #                                        self.async_usage,
        #                                        self._use_session,
        #                                        self._use_jwt)
        self.get_user_by = self.throw_self(self.__methods_builder.build_get_user_by())
        self.get_users_by = self.throw_self(self.__methods_builder.build_get_users_by())
        self.create_user = self.throw_self(self.__methods_builder.build_create_user())
        self.update_user = self.throw_self(self.__methods_builder.build_update_user())
        self.delete_user = self.throw_self(self.__methods_builder.build_delete_user())
        self.login_required = self.throw_self(self.__methods_builder.build_login_required())
        self.get_user_rights = self.throw_self(self.__methods_builder.build_get_user_rights())
        self.get_rights_id_by_names = self.throw_self(self.__methods_builder.build_get_rights_id_by_names())
        #todo какая то хрень с поиском прав. Надо чтобы при логине в токен клались id, а при проверке id брались, основываясь на perms[]

    def throw_self(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            r = func(self, *args, **kwargs)
            return r
        return inner

    def get_sync_session(self):
        db = self.__sessionmaker()
        try:
            yield db
        finally:
            db.close()

    # async def get_async_session(self) -> AsyncSession:
    #     async with self.__sessionmaker() as session:
    #         yield session

    @asynccontextmanager
    async def get_async_session(self):
        conn = self.__sessionmaker()
        try:
            yield conn
        finally:
            await conn.close()

    def __async_router(self):
        route = APIRouter(prefix=self.__prefix)
        register_model = self.register_model
        login_model = self.login_model

        @route.post('/register')
        async def register(user: register_model):
            async with self.get_async_session() as db:
                r = await self.create_user(db, user)
            return JSONResponse(r)

        if self._use_session is True:
            @route.post('/login')
            async def login(user: login_model = None,
                            access: Annotated[Union[str, None], Cookie()] = None,
                            refresh: Annotated[Union[str, None], Cookie()] = None
                            ):
                async with self.get_async_session() as db:
                    if access is not None:
                        session = await self.get_session(access)
                    elif refresh is not None:
                        pass
                    elif user is not None:
                        user = await self.get_users_by(db, **user.model_dump())
                return JSONResponse({'msg': 'No data have given'}, status_code=400)

        if self._use_jwt is True:
            @route.post('/login')
            async def login(user: login_model):
                async with self.get_async_session() as db:
                    user = await self.get_user_by(db, **user.model_dump())
                    if user is None:
                        return JSONResponse({'msg': 'wrong data'},
                                            status_code=400)
                    payload = {
                        'uid': getattr(user, self._identity_column),
                        'exp': datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(minutes=15),
                        'perms': await self.get_user_rights(db, getattr(user, self._identity_column))
                    }
                token = jwt.encode(payload=payload, key=self._secret_key)
                return JSONResponse({'msg': 'Successful login!', 'token': token},
                                    status_code=200)

        return route
