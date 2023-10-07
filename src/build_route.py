from fastapi import APIRouter
from pydantic import BaseModel


def build_async(prefix, tags):

    route = APIRouter(prefix=prefix, tags=tags)

    @route.post('/register')
    async def hi():
        return 'hi'

    return route


# def build_sync():
#     route = APIRouter(prefix=prefix, tags=tags)