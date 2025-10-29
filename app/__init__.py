import os
from pathlib import Path

from flask import Flask

from .extensions import db, migrate, login_manager
from .models import SystemSetting, User

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    default_sqlite_path = Path(app.instance_path) / "library.sqlite"

    database_uri = os.environ.get("DATABASE_URI", "")
    if not database_uri.strip():
        database_uri = f"sqlite:///{default_sqlite_path}"

    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key or not secret_key.strip():
        secret_key = "dev-secret-key"

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=database_uri,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    # Ensure the instance folder exists so SQLite can create the database file.
    default_sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    if test_config:
        app.config.update(test_config)

    register_extensions(app)
    register_blueprints(app)
    register_commands(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_system_settings():
        logo_path = SystemSetting.get_value("system_logo") or ""
        topbar_color = SystemSetting.get_value("topbar_color") or "#1f2d3d"
        return {
            "system_logo_path": logo_path,
            "system_topbar_color": topbar_color,
        }

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"


def register_blueprints(app: Flask) -> None:
    from .views import auth, books, categories, readers, lending, stats, system

    app.register_blueprint(auth.bp)
    app.register_blueprint(books.bp)
    app.register_blueprint(categories.bp)
    app.register_blueprint(readers.bp)
    app.register_blueprint(lending.bp)
    app.register_blueprint(stats.bp)
    app.register_blueprint(system.bp)


def register_commands(app: Flask) -> None:
    from .models import ensure_seed_data
    from .extensions import db

    @app.cli.command("seed")
    def seed() -> None:
        """Seed the database with an initial administrator user."""
        ensure_seed_data()
        print("Seed data ensured.")

    @app.cli.command("init-db")
    def init_db() -> None:
        """Create database tables based on the current models."""
        db.create_all()
        print("Database tables created.")
