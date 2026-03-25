from app.api.deps import get_current_user_id
from app.core.rate_limit import rate_limiter
from app.db.database import get_db
from app.repositories import tweet_repository, user_repository
from app.schemas.tweet import TweetCreate, TweetOut
from app.services.timeline_service import TimelineService, run_feed_fanout_job
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/tweets", tags=["tweets"])


@router.post(
    "",
    response_model=TweetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(rate_limiter("post_tweet", max_requests=10, window_seconds=60))
    ],
)
def create_tweet(
    payload: TweetCreate,
    background_tasks: BackgroundTasks,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TweetOut:
    """
    Create a tweet.

    Interview points:
    - Writing a tweet should stay fast.
    - Fan-out on write is pushed to a background task.
    - Rate limiting protects the posting API under high concurrency.
    """
    if user_repository.get_user(db, current_user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )

    tweet = tweet_repository.create_tweet(
        db,
        author_id=current_user_id,
        content=payload.content,
    )

    background_tasks.add_task(
        run_feed_fanout_job,
        tweet.id,
        current_user_id,
    )

    service = TimelineService(db)
    return service.serialize_tweet(
        {
            "tweet": tweet,
            "like_count": 0,
            "comment_count": 0,
            "cursor_created_at": tweet.created_at,
            "cursor_id": tweet.id,
        }
    )
