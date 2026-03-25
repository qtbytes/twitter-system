from app.db.database import get_db
from app.repositories import user_repository
from app.schemas.user import UserCreate, UserSummary
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserSummary:
    """
    Create a user.

    Why keep this route simple?
    - The interview focus for this project is timeline/feed design.
    - A lightweight user route lets you create test users quickly.
    """
    try:
        user = user_repository.create_user(db, username=payload.username)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserSummary.model_validate(user)
