import argparse
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, func, insert, select

from app.db.database import Base, SessionLocal, engine
from app.models import FeedItem, Follow, Tweet, User
from app.services.timeline_service import run_feed_fanout_job


@dataclass
class BenchmarkResult:
    follower_count: int
    batch_size: int
    user_create_seconds: float
    follow_create_seconds: float
    tweet_create_seconds: float
    fanout_seconds: float
    delivered_rows: int
    throughput_rows_per_second: float


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark celebrity fan-out latency.\n\n"
            "Goal:\n"
            "Measure how long it takes for one celebrity's new tweet to be "
            "delivered into followers' timelines using the current fan-out-on-write "
            "implementation.\n\n"
            "Example:\n"
            "python -m scripts.benchmark_celebrity_fanout "
            "--followers 100000 --batch-size 10000 --drop-existing"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--followers",
        type=int,
        default=100000,
        help="Number of followers for the celebrity.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for inserting users and follow rows.",
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop and recreate all tables before benchmarking.",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep benchmark data instead of clearing old rows first.",
    )
    parser.add_argument(
        "--tweet-content",
        type=str,
        default="benchmark celebrity tweet",
        help="Tweet content to use for the benchmark post.",
    )
    parser.add_argument(
        "--use-direct-insert",
        action="store_true",
        help=(
            "Benchmark a bulk SQL insert path instead of the current application "
            "fan-out job. Useful to compare current implementation vs a more "
            "database-oriented approach."
        ),
    )
    return parser


def reset_database(drop_existing: bool) -> None:
    if drop_existing:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def clear_existing_data() -> None:
    with SessionLocal() as db:
        db.execute(delete(FeedItem))
        db.execute(delete(Follow))
        db.execute(delete(Tweet))
        db.execute(delete(User))
        db.commit()


def chunked_ids(start_id: int, count: int, size: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    current = start_id
    remaining = count

    while remaining > 0:
        chunk_size = min(size, remaining)
        ranges.append((current, current + chunk_size - 1))
        current += chunk_size
        remaining -= chunk_size

    return ranges


def create_celebrity_and_followers(
    follower_count: int,
    batch_size: int,
) -> tuple[int, list[int], float, float]:
    started_users = time.perf_counter()

    with SessionLocal() as db:
        celebrity = User(username="celebrity_benchmark")
        db.add(celebrity)
        db.commit()
        db.refresh(celebrity)

        follower_ids: list[int] = []
        created_followers = 0

        while created_followers < follower_count:
            current_batch_size = min(batch_size, follower_count - created_followers)
            users = [
                User(username=f"fan_{created_followers + offset:07d}")
                for offset in range(current_batch_size)
            ]
            db.add_all(users)
            db.flush()
            follower_ids.extend(user.id for user in users)
            db.commit()
            created_followers += current_batch_size

    user_create_seconds = time.perf_counter() - started_users

    started_follows = time.perf_counter()

    with SessionLocal() as db:
        created_follows = 0
        celebrity_id = db.scalar(
            select(User.id).where(User.username == "celebrity_benchmark")
        )
        if celebrity_id is None:
            raise RuntimeError("failed to load celebrity benchmark user")

        while created_follows < follower_count:
            current_batch_ids = follower_ids[
                created_follows : created_follows + batch_size
            ]
            payload = [
                {"follower_id": follower_id, "followee_id": celebrity_id}
                for follower_id in current_batch_ids
            ]
            db.execute(insert(Follow), payload)
            db.commit()
            created_follows += len(current_batch_ids)

    follow_create_seconds = time.perf_counter() - started_follows
    return celebrity_id, follower_ids, user_create_seconds, follow_create_seconds


def create_benchmark_tweet(author_id: int, content: str) -> tuple[int, datetime, float]:
    started = time.perf_counter()

    with SessionLocal() as db:
        tweet = Tweet(user_id=author_id, content=content)
        db.add(tweet)
        db.commit()
        db.refresh(tweet)

        tweet_id = tweet.id
        created_at = tweet.created_at

    return tweet_id, created_at, time.perf_counter() - started


def count_delivered_rows(tweet_id: int) -> int:
    with SessionLocal() as db:
        return int(
            db.scalar(
                select(func.count())
                .select_from(FeedItem)
                .where(FeedItem.tweet_id == tweet_id)
            )
            or 0
        )


def run_direct_bulk_fanout(
    *,
    tweet_id: int,
    author_id: int,
    created_at: datetime,
) -> None:
    with SessionLocal() as db:
        follower_ids = (
            db.execute(
                select(Follow.follower_id).where(Follow.followee_id == author_id)
            )
            .scalars()
            .all()
        )

        owner_ids = [author_id, *follower_ids]
        payload = [
            {
                "owner_id": owner_id,
                "tweet_id": tweet_id,
                "actor_id": author_id,
                "created_at": created_at,
            }
            for owner_id in owner_ids
        ]
        db.execute(insert(FeedItem), payload)
        db.commit()


def benchmark_fanout(
    *,
    tweet_id: int,
    author_id: int,
    created_at: datetime,
    use_direct_insert: bool,
) -> float:
    started = time.perf_counter()

    if use_direct_insert:
        run_direct_bulk_fanout(
            tweet_id=tweet_id,
            author_id=author_id,
            created_at=created_at,
        )
    else:
        run_feed_fanout_job(tweet_id=tweet_id, author_id=author_id)

    return time.perf_counter() - started


def format_number(value: int | float) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.2f}"


def print_result(result: BenchmarkResult, use_direct_insert: bool) -> None:
    strategy_name = "direct bulk insert" if use_direct_insert else "current fan-out job"

    print()
    print("=" * 72)
    print("Celebrity Fan-out Benchmark Result")
    print("=" * 72)
    print(f"followers:                  {format_number(result.follower_count)}")
    print(f"batch_size:                 {format_number(result.batch_size)}")
    print(f"fanout_strategy:            {strategy_name}")
    print(f"user_create_seconds:        {result.user_create_seconds:.2f}")
    print(f"follow_create_seconds:      {result.follow_create_seconds:.2f}")
    print(f"tweet_create_seconds:       {result.tweet_create_seconds:.4f}")
    print(f"fanout_seconds:             {result.fanout_seconds:.2f}")
    print(f"delivered_rows:             {format_number(result.delivered_rows)}")
    print(
        f"throughput_rows_per_second: "
        f"{format_number(result.throughput_rows_per_second)}"
    )
    print("=" * 72)
    print()

    if result.delivered_rows != result.follower_count + 1:
        print("WARNING: delivered row count does not match expected owners.")
        print(
            f"Expected {format_number(result.follower_count + 1)} rows, got "
            f"{format_number(result.delivered_rows)} rows."
        )
        print()

    estimated_for_1m = (
        1_000_001 / result.throughput_rows_per_second
        if result.throughput_rows_per_second > 0
        else math.inf
    )
    print("Interpretation")
    print("-" * 72)
    print(
        f"- Measured latency for this run: {result.fanout_seconds:.2f}s "
        f"to deliver one tweet to {format_number(result.delivered_rows)} timelines."
    )
    print(
        f"- Effective throughput: about "
        f"{format_number(result.throughput_rows_per_second)} feed rows / second."
    )
    print(
        f"- If throughput stayed similar, 1,000,001 timeline deliveries "
        f"(1 celebrity + 1e6 followers) would take about {estimated_for_1m:.2f}s."
    )
    print()
    print("Important caveat")
    print("-" * 72)
    print(
        "- This benchmark measures database-side fan-out latency in one process. "
        "It does not include queue backlog, multiple workers, network hops, "
        "replication lag, cache invalidation storms, or client-visible read delay."
    )
    print(
        "- If you want a truer production-style number, run this benchmark "
        "against Postgres/MySQL instead of local SQLite, and compare one worker "
        "vs multiple workers."
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.followers <= 0:
        raise SystemExit("--followers must be greater than 0")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be greater than 0")

    print("Preparing database...")
    reset_database(drop_existing=args.drop_existing)

    if not args.keep_data:
        print("Clearing existing rows...")
        clear_existing_data()

    print(f"Creating celebrity and {args.followers:,} followers...")
    celebrity_id, follower_ids, user_create_seconds, follow_create_seconds = (
        create_celebrity_and_followers(
            follower_count=args.followers,
            batch_size=args.batch_size,
        )
    )

    print("Creating benchmark tweet...")
    tweet_id, created_at, tweet_create_seconds = create_benchmark_tweet(
        author_id=celebrity_id,
        content=args.tweet_content,
    )

    print("Running fan-out benchmark...")
    fanout_seconds = benchmark_fanout(
        tweet_id=tweet_id,
        author_id=celebrity_id,
        created_at=created_at,
        use_direct_insert=args.use_direct_insert,
    )

    delivered_rows = count_delivered_rows(tweet_id)
    throughput_rows_per_second = (
        delivered_rows / fanout_seconds if fanout_seconds > 0 else 0.0
    )

    result = BenchmarkResult(
        follower_count=len(follower_ids),
        batch_size=args.batch_size,
        user_create_seconds=user_create_seconds,
        follow_create_seconds=follow_create_seconds,
        tweet_create_seconds=tweet_create_seconds,
        fanout_seconds=fanout_seconds,
        delivered_rows=delivered_rows,
        throughput_rows_per_second=throughput_rows_per_second,
    )

    print_result(result, use_direct_insert=args.use_direct_insert)


if __name__ == "__main__":
    main()
