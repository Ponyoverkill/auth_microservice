from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import DB_URL


engine = create_async_engine(DB_URL)
async_session = sessionmaker(engine,
                             class_=AsyncSession,
                             expire_on_commit=False
                             )


async def get_async_session() -> AsyncSession:
    async with async_session() as session:
        yield session



