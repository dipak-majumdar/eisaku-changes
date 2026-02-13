from contextlib import contextmanager
from typing import Annotated, AsyncGenerator
from fastapi import Depends
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from core.config import DATABASE_URL


connect_args = {
    # "check_same_thread": False,
}

# Sync Engine (for scripts and legacy support)
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

# Async Engine
ASYNC_DATABASE_URL = DATABASE_URL.replace("mysql+pymysql", "mysql+aiomysql")
async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, future=True)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


# For middleware and scripts (Sync)
@contextmanager
def get_sync_session():
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    print("Creating database tables...")
    SQLModel.metadata.create_all(engine)


SessionDep = Annotated[AsyncSession, Depends(get_session)]