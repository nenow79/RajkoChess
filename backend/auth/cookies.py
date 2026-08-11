from fastapi import Response

from settings import get_settings


def set_auth_cookies(
    response: Response, *, session_token: str, csrf_token: str
) -> None:
    settings = get_settings()
    max_age = settings.auth_session_absolute_days * 24 * 60 * 60
    common = {
        "max_age": max_age,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=session_token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        **common,
    )


def set_csrf_cookie(response: Response, *, csrf_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=csrf_token,
        max_age=settings.auth_session_absolute_days * 24 * 60 * 60,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name, httponly in (
        (settings.auth_cookie_name, True),
        (settings.auth_csrf_cookie_name, False),
    ):
        response.delete_cookie(
            key=name,
            path="/",
            secure=settings.auth_cookie_secure,
            httponly=httponly,
            samesite="lax",
        )
