from fastapi import APIRouter, Depends, FastAPI

route = APIRouter(
    prefix="/user",
    tags=["user"],
    dependencies=[Depends()],
    responses={404: {"description": "Not found"},
               403: {"description": "dasfds"}}
                  )

route.get
