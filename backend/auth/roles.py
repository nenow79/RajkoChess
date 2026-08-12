from typing import Protocol, TypeVar

from db.models import SystemRole, User
from fastapi import HTTPException, status


class AuthLike(Protocol):
    @property
    def user(self) -> User: ...


TCurrentAuth = TypeVar("TCurrentAuth", bound=AuthLike)


def is_admin(user: User) -> bool:
    return user.system_role == SystemRole.ADMIN


def ensure_admin(current: TCurrentAuth) -> TCurrentAuth:
    if not is_admin(current.user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wymagana jest rola administratora",
        )
    return current
