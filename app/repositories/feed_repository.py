from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.comment import Comment
from app.models.feed import FeedItem
from app.models.like import Like
from app.models.tweet import Tweet


def bulk_insert_feed_items(
    db: Session,
    owner_ids: list[int],
    tweet_id: int,
    actor_id: int,
    created_at: datetime,
) -> int:
    """
    Fan-out on write:
    insert one feed row per timeline owner.

    Notes for interview:
    - We deduplicate owner_ids first.
    - We check existing rows to keep the operation idempotent.
    - In high-concurrency production systems, this is often moved to
      a background worker and may use bulk SQL / upsert.
    """
    unique_owner_ids = list(dict.fromkeys(owner_ids))
    if not unique_owner_ids:
        return 0

    existing_owner_ids = {
        owner_id
        for (owner_id,) in db.execute(
            select(FeedItem.owner_id).where(
                FeedItem.tweet_id == tweet_id,
                FeedItem.owner_id.in_(unique_owner_ids),
            )
        ).all()
    }

    payload = [
        FeedItem(
            owner_id=owner_id,
            tweet_id=tweet_id,
            actor_id=actor_id,
            created_at=created_at,
        )
        for owner_id in unique_owner_ids
        if owner_id not in existing_owner_ids
    ]

    if not payload:
        return 0

    db.add_all(payload)
    db.commit()
    return len(payload)


def list_feed_tweets(
    db: Session,
    owner_id: int,
    limit: int,
    cursor_created_at: datetime | None = None,
    cursor_id: int | None = None,
) -> list[dict]:
    """
    Read precomputed home timeline rows for fan-out on write.

    Why this query matters in interviews:
    - It uses cursor pagination instead of offset pagination.
    - It avoids N+1 for author data with joinedload.
    - It aggregates likes/comments in SQL instead of per-row queries.
    """
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
            FeedItem,
            Tweet,
            func.coalesce(like_counts.c.like_count, 0),
            func.coalesce(comment_counts.c.comment_count, 0),
        )
        .join(Tweet, Tweet.id == FeedItem.tweet_id)
        .options(joinedload(Tweet.author))
        .outerjoin(like_counts, like_counts.c.tweet_id == Tweet.id)
        .outerjoin(comment_counts, comment_counts.c.tweet_id == Tweet.id)
        .where(FeedItem.owner_id == owner_id)
        .order_by(FeedItem.created_at.desc(), FeedItem.id.desc())
        .limit(limit + 1)
    )

    if cursor_created_at is not None and cursor_id is not None:
        stmt = stmt.where(
            or_(
                FeedItem.created_at < cursor_created_at,
                and_(
                    FeedItem.created_at == cursor_created_at,
                    FeedItem.id < cursor_id,
                ),
            )
        )

    rows = db.execute(stmt).all()

    return [
        {
            "tweet": tweet,
            "like_count": int(like_count),
            "comment_count": int(comment_count),
            "cursor_created_at": feed_item.created_at,
            "cursor_id": feed_item.id,
        }
        for feed_item, tweet, like_count, comment_count in rows
    ]
