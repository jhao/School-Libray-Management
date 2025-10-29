import os
from pathlib import Path

from flask import Flask, request
from flask_login import current_user

from .constants import DEFAULT_BRAND_COLOR
from .extensions import db, migrate, login_manager
from .models import SystemSetting, User
from .utils.pagination import (
    PER_PAGE_OPTIONS,
    build_pagination_links,
    build_pagination_url,
)


NAV_SECTIONS = [
    {
        "key": "common",
        "title": "借阅管理",
        "items": [
            {"endpoint": "stats.dashboard", "label": "统计分析"},
            {"endpoint": "lending.borrow", "label": "借书"},
            {"endpoint": "lending.return_book", "label": "还书"},
            {"endpoint": "lending.records", "label": "借阅记录"},
        ],
        "prefixes": ["stats.", "lending."],
    },
    {
        "key": "books",
        "title": "图书管理",
        "items": [
            {"endpoint": "books.list_books", "label": "图书列表"},
            {"endpoint": "books.create_book", "label": "新增图书"},
            {"endpoint": "categories.list_categories", "label": "分类列表"},
            {"endpoint": "categories.create_category", "label": "新增分类"},
        ],
        "prefixes": ["books.", "categories."],
    },
    {
        "key": "readers",
        "title": "读者管理",
        "items": [
            {"endpoint": "readers.list_readers", "label": "读者列表"},
            {"endpoint": "readers.create_reader", "label": "新增读者"},
            {"endpoint": "readers.manage_grades", "label": "年级列表"},
            {"endpoint": "readers.create_grade", "label": "新增年级"},
            {"endpoint": "readers.manage_classes", "label": "班级列表"},
            {"endpoint": "readers.create_class", "label": "新增班级"},
        ],
        "prefixes": ["readers."],
    },
    {
        "key": "system",
        "title": "系统设置",
        "items": [
            {"endpoint": "system.list_users", "label": "用户列表"},
            {"endpoint": "system.create_user", "label": "新增用户"},
            {"endpoint": "system.system_settings", "label": "系统外观"},
            {"endpoint": "system.backup_restore", "label": "备份与恢复"},
            {"endpoint": "system.test_data", "label": "测试数据", "admin_only": True},
        ],
        "prefixes": ["system."],
    },
]


def _resolve_active_section(endpoint: str) -> str:
    if not NAV_SECTIONS:
        return ""
    if not endpoint:
        return NAV_SECTIONS[0]["key"]
    for section in NAV_SECTIONS:
        if any(item["endpoint"] == endpoint for item in section["items"]):
            return section["key"]
    for section in NAV_SECTIONS:
        for prefix in section.get("prefixes", []):
            if endpoint.startswith(prefix):
                return section["key"]
    return NAV_SECTIONS[0]["key"]

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
        topbar_color = SystemSetting.get_value("topbar_color") or DEFAULT_BRAND_COLOR
        current_endpoint = request.endpoint or ""
        nav_sections = []
        for section in NAV_SECTIONS:
            filtered_items = []
            for item in section["items"]:
                if item.get("admin_only"):
                    if not current_user.is_authenticated or current_user.level != "admin":
                        continue
                filtered_items.append(item)
            if not filtered_items:
                continue
            nav_sections.append(
                {
                    "key": section["key"],
                    "title": section["title"],
                    "items": filtered_items,
                }
            )
        return {
            "system_logo_path": logo_path,
            "system_topbar_color": topbar_color,
            "system_sidebar_color": topbar_color,
            "system_nav_sections": nav_sections,
            "system_active_nav_key": _resolve_active_section(current_endpoint),
        }

    @app.context_processor
    def inject_pagination_helpers():
        return {
            "pagination_per_page_options": PER_PAGE_OPTIONS,
            "build_pagination_links": build_pagination_links,
            "pagination_build_url": build_pagination_url,
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
