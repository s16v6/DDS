from databases import Database
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite+aiosqlite:///./dds.db"

database = Database(DATABASE_URL)
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()
