from sqlmodel import Field, SQLModel, create_engine, Session
from sqlalchemy.engine import URL
#need to import all models to proper create tables in db

from app.core.config import settings


## Should be using settings package, latter on we will learn how to use it


url_object = URL.create(
    "postgresql+psycopg2",
    username=settings.DATABASE_USERNAME,
    password=settings.DATABASE_PASSWORD, 
    host=settings.DATABASE_HOST,
    database=settings.DATABASE_NAME,
)


engine = create_engine(url_object, echo=True)


def init_db(session: Session) -> None:
    SQLModel.metadata.create_all(engine)

