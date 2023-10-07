import inspect
from functools import wraps, update_wrapper
from typing import Callable, Coroutine, Annotated, Union

from asyncpg import UndefinedColumnError
from fastapi import Depends, background, Cookie
from jwt import DecodeError, InvalidSignatureError, ExpiredSignatureError
from pydantic import BaseModel
from sqlalchemy import select, Column, insert
from sqlalchemy.exc import NoResultFound, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse
import jwt

from .exceptions import ArgumentsError

class BaseMethodBuilder:
    def __init__(
            self,
            use_session: bool = True,
            use_jwt: bool = False
    ):
        self._use_jwt = use_jwt
        self._use_session = use_session

    def build_get_user_by(self):
        pass

    def build_get_users_by(self):
        pass

    def build_create_user(self):
        pass

    def build_update_user(self):
        pass

    def build_delete_user(self):
        pass


class AsyncMethodBuilder(BaseMethodBuilder):

    def build_get_user_by(self):
        async def get_user_by(self, session: AsyncSession, **kwargs):
            conditions = []
            if not kwargs:
                raise ArgumentsError('Unique param required')
            # if len(kwargs) > 1:
            #     raise ArgumentsError('Only one unique param required.'
            #                          ' If you need get more than one user,'
            #                          ' try to use get_users_by()')
            for key, value in kwargs.items():
                conditions.append(Column(key) == value)

            query = select(self.user_db).where(*conditions)
            try:
                user = (await session.execute(query)).scalars().one()
                return user
            except NoResultFound:
                return None

        return get_user_by

    def build_get_users_by(self):
        async def get_users_by(self, session: AsyncSession, **kwargs):
            conditions = []
            for key, value in kwargs.items():
                conditions.append(Column(key) == value)
            query = select(self.user_db).where(*conditions)
            try:
                users = (await session.execute(query)).scalars().all()
                return users
            except NoResultFound:
                return []
            except:
                return []
        return get_users_by

    def build_create_user(self):
        async def create_user(
                self,
                db: AsyncSession,
                user: BaseModel,
                confirm_func: Coroutine[None, BaseModel, None] | Callable[[BaseModel], None] = None,
                perms: list = [],
                role: str = 'default'
        ):
            if role not in self.roles.keys():
                raise ValueError(f'{role} not in roles')
            for p in perms:
                if p not in self.permissions:
                    raise ValueError(f'{p} not in permissions')

            if not isinstance(user, self.register_model):
                raise ArgumentsError(f"user must be an instance of {self.register_model},"
                                     f" not {type(user)}")

            rights = set()
            for p in perms:
                rights.add(p)
            for p in self.roles[role]:
                rights.add(p)
            query = select(self.right_list.c.id).where(self.right_list.c.name.in_(rights))
            rights = (await db.execute(query)).scalars().all()
            user = self.user_db(**user.model_dump(exclude_defaults=True))
            try:
                db.add(user)
                await db.commit()
                await db.refresh(user)
                # user = self.user_model.model_validate(user)
                # self
                # if confirm_func is not None:
                #     background.BackgroundTasks.add_task(confirm_func, user)
                # background.BackgroundTasks.add_task(print, 'task task task')
                # await db.aclose()
                # return {self._identity_column: getattr(user, self._identity_column)}
            except IntegrityError:
                await db.rollback()
                await db.commit()
                return {"msg": "This data is invalid!"}

            # print(rights)
            values = []
            for r in rights:
                values.append({'user_id': getattr(user, self._identity_column),
                               'right_id': r})
            query = insert(self.user_rights_db).values(values)
            await db.execute(query)
            await db.commit()
            return {self._identity_column: getattr(user, self._identity_column)}

        return create_user

    def build_update_user(self):
        async def update_user(self, session: AsyncSession, user, confirm_func=None):
            if not isinstance(user, self.user_model):
                raise ArgumentsError(f"user must be an instance of {self.user_model},"
                                     f" not {type(user)}")
            try:
                user = self.user_db(**user.model_fields())
                await session.begin()
                await session.add(user)
                await session.commit()
                return {"msg": "success updated"}
            except IntegrityError:
                return {"msg": "This data is invalid"}
            except:
                return {"msg": "Unexpected error!"}
        return update_user

    def build_delete_user(self):
        async def delete_user(self, db: AsyncSession, user, confirm_func=None):
            if not isinstance(user, self.user_model):
                raise ArgumentsError(f"user must be an instance of {self.user_model},"
                                     f" not {type(user)}")
            try:
                user = self.user_db(**user.model_fields())
                await db.begin()
                await db.delete(user)
                await db.commit()
            except IntegrityError:
                return {"msg": "Can't, delete!"}
            except:
                return {"msg": "Unexpected error!"}
        return delete_user

    def build_login_required(self):
        # print(self._use_jwt)
        if self._use_jwt:
            def login_required(self, perms: list = [], roles: list = []):
                for r in roles:
                    if r not in self.roles.keys():
                        raise ValueError(f'{r} not in roles')
                for p in perms:
                    if p not in self.permissions:
                        raise ValueError(f'{p} not in permissions')

                def real_wrapper(func):
                    @wraps(func)
                    async def wrapper(*args,
                                      access,
                                      **kwargs):
                        if access is not None:
                            try:
                                payload = jwt.decode(access,
                                                   key=self._secret_key,
                                                   algorithms=['HS256'])
                            except DecodeError or InvalidSignatureError:
                                return JSONResponse({'msg': 'Invalid access token'},
                                                    status_code=403)
                            except ExpiredSignatureError:
                                return JSONResponse({'msg': 'access token expired'},
                                                    status_code=403)
                        else:
                            return JSONResponse({'msg': 'access token not found'},
                                                status_code=400)
                        getter_roles = []
                        async with self.get_async_session() as db:
                            permissions = await self.get_rights_id_by_names(db, perms)
                            kw = {self._identity_column: payload['uid']}
                            user = await self.get_user_by(db, **kw)
                            for r in roles:
                                getter_roles.append(await self.get_rights_id_by_names(db, self.roles[r]))

                        if user is None:
                            return JSONResponse({'msg': 'Invalid access token'},
                                                status_code=403)

                        user = self.user_model.model_validate(user)

                        if self.user_model in func.__annotations__.values():
                            for k, v in func.__annotations__.items():
                                if v == self.user_model:
                                    kwargs.update(
                                        {k: user}
                                    )
                        for p in permissions:
                            if p not in payload['perms']:
                                return JSONResponse({'msg': 'not enough rights'},
                                                    status_code=403)

                        missed = 0
                        for r in getter_roles:
                            for p in r:
                                if p not in payload['perms']:
                                    missed += 1
                                    break

                        if missed == len(getter_roles) and len(getter_roles) != 0:
                            return JSONResponse({'msg': 'not enough rights'},
                                                status_code=403)

                        r = await func(*args, **kwargs)
                        return r

                    sig = inspect.signature(func)
                    params = list(sig.parameters.values())
                    params.append(inspect.Parameter(name='access',
                                                    kind=inspect.Parameter.KEYWORD_ONLY,
                                                    annotation=Annotated[Union[str, None], Cookie()],
                                                    default=None
                                                    ))
                    sig = sig.replace(parameters=tuple(params))
                    wrapper.__signature__ = sig
                    return wrapper
                return real_wrapper
        return login_required

    def build_get_session(self, redis=None):
        if redis is None:
            async def get_session_by(self, db: AsyncSession, **kwargs):
                conditions = []
                for k, v in kwargs.items():
                    conditions.append(Column(k) == v)
                query = select(self._sessions).where(*conditions)
                try:
                    session = (await db.execute(query)).scalars().one()
                    return session
                except NoResultFound:
                    return []
                except:
                    return []
        else:
            pass
        return get_session_by

    def build_get_rights_id_by_names(self):
        async def get_rights_id_by_names(self, db: AsyncSession, perms: list):
            query = select(self.right_list.c.id).where(self.right_list.c.name.in_(perms))
            try:
                permissions = (await db.execute(query)).scalars().all()
                # print(permissions)
                return permissions
            except NoResultFound:
                return []
        return get_rights_id_by_names

    def build_get_user_rights(self):
        async def get_user_rights(self, db: AsyncSession, uid):
            subquery = select(self.user_rights_db.c.right_id)
            query = subquery.where(self.user_rights_db.c.user_id == uid)
            # print('get_user_rights!!!')
            # print(query)
            try:
                rights = (await db.execute(query)).scalars().all()
                # print(rights)
                return rights
            except NoResultFound:
                return []

        return get_user_rights


class SyncMethodBuilder(BaseMethodBuilder):

    def build_get_user_by(self):
        def get_user_by(self, session: Session, **kwargs):
            conditions = []
            if not kwargs:
                raise ArgumentsError('Unique param required')
            if len(kwargs) > 1:
                raise ArgumentsError('Only one unique param required.'
                                     ' If you need get more than one user,'
                                     ' try to use get_users_by()')
            for key, value in kwargs.items():
                conditions.append(Column(key) == value)

            query = select(self.user_db).where(*conditions)
            try:
                user = session.execute(query).scalars().one()
                return user
            except NoResultFound:
                return None

        return get_user_by

    def build_get_users_by(self):
        def get_users_by(self, session: Session, **kwargs):
            conditions = []
            for key, value in kwargs.items():
                conditions.append(Column(key) == value)
            query = select(self.user_db).where(*conditions)
            try:
                users = session.execute(query).scalars().all()
                return users
            except NoResultFound:
                return []
            except:
                return []
        return get_users_by

    def build_create_user(self):
        def create_user(self, session: Session, user, confirm_func=None):
            if not isinstance(user, self.register_user):
                raise ArgumentsError(f"user must be an instance of {self.register_user},"
                                     f" not {type(user)}")
            user = self.user_db(**user)
            try:
                session.begin()
                session.add(**user)
                session.commit()
                session.refresh(user)
                return getattr(user, self.__identity_column)
            except IntegrityError:
                return {"msg": "This data is invalid!"}
            except:
                return {"msg": "Unexpected error!"}
        return create_user

    def build_update_user(self):
        def update_user(self, session: Session, user, confirm_func=None):
            if not isinstance(user, self.user_model):
                raise ArgumentsError(f"user must be an instance of {self.user_model},"
                                     f" not {type(user)}")
            try:
                user = self.user_db(**user.model_fields())
                session.begin()
                session.add(user)
                session.commit()
                return {"msg": "success updated"}
            except IntegrityError:
                return {"msg": "This data is invalid"}
            except:
                return {"msg": "Unexpected error!"}
        return update_user

    def build_delete_user(self):
        def delete_user(self, session: Session, user, confirm_func=None):
            if not isinstance(user, self.user_model):
                raise ArgumentsError(f"user must be an instance of {self.user_model},"
                                     f" not {type(user)}")
            try:
                user = self.user_db(**user.model_fields())
                session.begin()
                session.delete(user)
                session.commit()
                return {"msg": "Success deleted"}
            except IntegrityError:
                return {"msg": "Can't, delete!"}
            except:
                return {"msg": "Unexpected error!"}
        return delete_user







