from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import get_settings

security = HTTPBasic(auto_error=False)


def require_access(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> str:
    settings = get_settings()
    if not settings.stewy_password:
        return settings.stewy_username

    username_ok = credentials is not None and secrets.compare_digest(
        credentials.username, settings.stewy_username
    )
    password_ok = credentials is not None and secrets.compare_digest(
        credentials.password, settings.stewy_password
    )
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    return settings.stewy_username
