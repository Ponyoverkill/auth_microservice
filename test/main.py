from src import AuthApp
from fastapi import FastAPI

from database import async_session
from schemas import User, Roles
from config import SECRET_KEY
app = FastAPI

auth = AuthApp(
    database=async_session,
    user_model=User,
    role_model=Roles,
    prefix='auth',
    use_jwt_auth=True,
    jwt_secret_key=SECRET_KEY
)

app.include_router(auth.router)


@app.post('/hello-admin')
@auth.login_required(roles=['admin'])
async def hello_admin():
    return 'hello, im admin!'


@app.post('/hello-client')
@auth.login_required(roles=['client'])
async def hello_client(client: auth.user_model):
    return client


@app.post('/do-action-1')
@auth.login_required(perms=['action_1'])
async def do_action_1(user: auth.user_model):
    print(user)
    return 'action 1 done!'

