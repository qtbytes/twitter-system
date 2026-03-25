from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.comment import Comment
from app.models.like import Like
from app.models.tweet import Tweet


def create_tweet(db: Session, author_id: int, content: str) -> Tweet | None:
    """
    Create a tweet and reload it with author information.

    Why reload?
    - API response usually needs author data.
    - This avoids a later lazy-load when serializing the tweet.
    """
    tweet = Tweet(user_id=author_id, content=content)
    db.add(tweet)
    db.commit()
    db.refresh(tweet)

    return db.scalar(
        select(Tweet).options(joinedload(Tweet.author)).where(Tweet.id == tweet.id)
    )


def get_tweet(db: Session, tweet_id: int) -> Tweet | None:
    """
    Load one tweet with author information.
    """
    return db.scalar(
        select(Tweet).options(joinedload(Tweet.author)).where(Tweet.id == tweet_id)
    )


def list_tweets_by_authors(
    db: Session,
    author_ids: list[int],
    limit: int,
    cursor_created_at: datetime | None = None,
    cursor_id: int | None = None,
) -> list[dict]:
    """
    Read tweets for fan-out on read timeline.

    Interview focus:
    - Uses cursor pagination instead of offset pagination.
    - Avoids N+1 by eager-loading author and aggregating like/comment counts
      in the same query.
    - Orders by (created_at DESC, id DESC) so pagination stays stable even
      when multiple tweets have the same timestamp.

    Returns:
        A list of dictionaries shaped for the timeline service:
        {
            "tweet": Tweet,
            "like_count": int,
            "comment_count": int,
            "cursor_created_at": datetime,
            "cursor_id": int,
        }
    """
    if not author_ids:
        return []

    like_counts = (
        select(
            Like.tweet_id,
            func.count().label("like_count"),
        )
        .group_by(Like.tweet_id)
        .subquery()
    )

    comment_counts = (
        select(
            Comment.tweet_id,
            func.count().label("comment_count"),
        )
        .group_by(Comment.tweet_id)
        .subquery()
    )

    stmt = (
        select(
            Tweet,
            func.coalesce(like_counts.c.like_count, 0).label("like_count"),
            func.coalesce(comment_counts.c.comment_count, 0).label("comment_count"),
        )
        .options(joinedload(Tweet.author))
        .outerjoin(like_counts, like_counts.c.tweet_id == Tweet.id)
        .outerjoin(comment_counts, comment_counts.c.tweet_id == Tweet.id)
        .where(Tweet.user_id.in_(author_ids))
        .order_by(Tweet.created_at.desc(), Tweet.id.desc())
        .limit(limit + 1)
    )

    if cursor_created_at is not None and cursor_id is not None:
        stmt = stmt.where(
            or_(
                Tweet.created_at < cursor_created_at,
                and_(
                    Tweet.created_at == cursor_created_at,
                    Tweet.id < cursor_id,
                ),
            )
        )

    rows = db.execute(stmt).all()

    return [
        {
            "tweet": tweet,
            "like_count": int(like_count),
            "comment_count": int(comment_count),
            "cursor_created_at": tweet.created_at,
            "cursor_id": tweet.id,
        }
        for tweet, like_count, comment_count in rows
    ]
