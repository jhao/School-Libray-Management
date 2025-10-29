"""Minimal Flask-Login compatible helpers.

This lightweight implementation provides the subset of Flask-Login
functionality that the application relies on.  It supports storing the
current user in the session, protecting views with the ``login_required``
 decorator and exposing the ``current_user`` proxy used in templates.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional

from flask import abort, g, redirect, request, session, url_for
from werkzeug.local import LocalProxy


_UserLoader = Callable[[str], Any]


class AnonymousUser:
    """Represents an unauthenticated user."""

    is_active = False
    is_anonymous = True

    @property
    def is_authenticated(self) -> bool:
        return False

    def get_id(self) -> Optional[str]:
        return None


class UserMixin:
    """Mixin providing default implementations used by the app."""

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_active(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:  # type: ignore[override]
        return False

    def get_id(self) -> str:
        # Flask-Login expects the identifier to be a string.
        return str(getattr(self, "id"))


class LoginManager:
    """Stores configuration used to manage authenticated users."""

    def __init__(self) -> None:
        self.login_view: Optional[str] = None
        self._user_callback: Optional[_UserLoader] = None

    def init_app(self, app) -> None:  # type: ignore[override]
        """Register request hooks for the given Flask application."""
        global _login_manager
        _login_manager = self

        @app.before_request
        def load_user() -> None:
            g._login_user = self._load_user_from_session()  # type: ignore[attr-defined]

        @app.context_processor
        def inject_user() -> dict[str, Any]:
            return {"current_user": current_user}

    def user_loader(self, callback: _UserLoader) -> _UserLoader:
        self._user_callback = callback
        return callback

    # Internal helpers -------------------------------------------------
    def _load_user_from_session(self) -> Any:
        if self._user_callback is None:
            return AnonymousUser()

        user_id = session.get("_user_id")
        if user_id is None:
            return AnonymousUser()

        user = self._user_callback(user_id)
        if user is None:
            session.pop("_user_id", None)
            return AnonymousUser()
        return user


_login_manager: Optional[LoginManager] = None


def _get_current_user() -> Any:
    user = getattr(g, "_login_user", None)
    if user is None:
        user = AnonymousUser()
        g._login_user = user  # type: ignore[attr-defined]
    return user


current_user = LocalProxy(_get_current_user)


def login_user(user: Any) -> None:
    """Persist the given user in the session for subsequent requests."""
    session["_user_id"] = user.get_id()
    g._login_user = user  # type: ignore[attr-defined]


def logout_user() -> None:
    session.pop("_user_id", None)
    g._login_user = AnonymousUser()  # type: ignore[attr-defined]


def login_required(func: Callable[..., Any]) -> Callable[..., Any]:
    """View decorator that redirects anonymous users to the login page."""

    @wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if current_user.is_authenticated:
            return func(*args, **kwargs)

        if _login_manager and _login_manager.login_view:
            return redirect(url_for(_login_manager.login_view, next=request.url))

        abort(401)

    return wrapped


__all__ = [
    "AnonymousUser",
    "LoginManager",
    "UserMixin",
    "current_user",
    "login_required",
    "login_user",
    "logout_user",
]
