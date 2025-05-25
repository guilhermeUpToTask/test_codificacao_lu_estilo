from sqlmodel import SQLModel, select, create_engine, Session
from sqlalchemy.engine import URL
#need to import all models to proper create tables in db
from app.models.user import User, UserCreate, UserRole
from app.core.config import settings
from app.core.user_crud import create_user

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
    
    user = session.exec(
        select(User).where(User.email == settings.ADMIN_USER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.ADMIN_USER,
            password=settings.ADMIN_PASSWORD,
            role=UserRole.ADMIN
        )
        user = create_user(session=session, user_create=user_in)

