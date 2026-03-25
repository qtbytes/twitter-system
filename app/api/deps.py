from typing import Annotated

from fastapi import Header, HTTPException, status


def get_current_user_id(
    x_user_id: Annotated[int | None, Header(alias="X-User-Id")] = None,
) -> int:
    """
    Interview-friendly auth shortcut.

    Instead of wiring JWT/session auth first, use the X-User-Id header so you
    can focus on timeline, feed, pagination, cache, and high-concurrency design.

    Production note:
    Replace this with real authentication middleware / dependency later.
    """
    if x_user_id is None or x_user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-User-Id header.",
        )
    return x_user_id
