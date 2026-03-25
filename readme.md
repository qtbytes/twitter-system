🥈 项目二：微博 / 推特系统（强烈推荐）

1. 功能

- 发帖（类似 tweet）

- 关注 / 取关

- 时间线（重点）

- 点赞 / 评论

2. 技术点（重点）

- 数据库设计（关注表 / feed 表）

- 分页（cursor vs offset）

- N+1 查询优化

- Redis 缓存

3. 面试核心问题

- 如何设计“时间线”？

拉模式（fan-out on read）

推模式（fan-out on write）

- 如何优化性能？

Redis 缓存 feed

分页优化

索引设计

- 高并发怎么办？

异步任务（Celery / BackgroundTasks）

限流

- Other problems

0. What's response_model
1. For interactions, how to handle high concurrnecy?
2. What's the N+1 problem
3. What's the differance from cursor pagination with offset pagination.
4. redis method like `get`, `setex` are awaitable, why don't need await
5. Now the implement of run_feed_fanout_job is just bulk insert into db, I want know at what scale will performance issues occur? And I like rq, try to use rq to solve this problem. I have heard kafka, what's kafka?
6. why user model need this relationship, what's back_populates and cascade mean, and why need cascade.

```
    tweets = relationship(
        "Tweet", back_populates="author", cascade="all, delete-orphan"
    )
```

7. Tweets model, why need a union index on these three column

```
    __table_args__ = (
        Index("ix_tweets_user_created_id", "user_id", "created_at", "id"),
    )
```

8. Feed model, why index on owner, not actor?
9. unfollow_user function, `result.rowcount > 0` Object of type `Result[Any]` has no attribute `rowcount`, i fixed with ` return len(result.all()) > 0`
10. `create_tweet()` why need `db.refresh()`
11. in `list_tweets_by_authors()`, why should ` Tweet.created_at < cursor_created_at`, not >. And here you used `in` ` .where(Tweet.user_id.in_(author_ids))`, does it have performance problem?

```
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
```

12. what is idempotent, how to make sure idempotent
13. `list_feed_tweets()` is almost same with `list_tweets_by_authors()`, what's the differ?

14. in `create_comment()`, If we refresh db, do i can getk

```
   db.add(comment)
   db.commit()
   db.refresh(comment)

   return comment, author
```

15. why need schemas? And the name is Conventional? like xxxCreate, xxxOut?
16. why TimelinePage need next_cursor?

```
class TimelinePage(BaseModel):
    items: list[TweetOut]
    next_cursor: str | None = None
    strategy: Literal["read", "write"]
```

17. why `get_db()` should be a generater?
18. I want see a real rate_limiter.
