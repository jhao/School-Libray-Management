"""Application-wide Flask extensions."""

from __future__ import annotations

import importlib.util
import warnings
from typing import Any

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy


def _resolve_migrate() -> Any:
    """Return the Flask-Migrate ``Migrate`` class or a graceful fallback.

    The production application expects :mod:`flask_migrate` to be available, but
    some local environments might omit the optional dependency. Importing the
    extension in that scenario raises :class:`ModuleNotFoundError` and prevents
    the Flask application from initialising, which in turn hides the custom CLI
    commands (for example ``flask init-db``).  To keep the CLI usable even
    without the dependency, we detect the module's presence ahead of time and
    provide a no-op stand-in when necessary.
    """

    if importlib.util.find_spec("flask_migrate") is not None:
        from flask_migrate import Migrate  # type: ignore[import-not-found]

        return Migrate

    class _FallbackMigrate:
        """Minimal ``Migrate`` replacement used when Flask-Migrate is missing."""

        def init_app(self, app: Any, _: Any) -> None:  # pragma: no cover - trivial
            warnings.warn(
                "Flask-Migrate is not installed. Migration commands are unavailable.",
                RuntimeWarning,
                stacklevel=2,
            )
            app.logger.warning(  # type: ignore[attr-defined]
                "Flask-Migrate is not installed. Migration commands are unavailable.",
            )

    return _FallbackMigrate


Migrate = _resolve_migrate()


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
