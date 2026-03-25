from app.models.user import User
from sqlalchemy import select
from sqlalchemy.orm import Session


def create_user(db: Session, username: str) -> User:
    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        raise ValueError("username already exists")

    user = User(username=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))
