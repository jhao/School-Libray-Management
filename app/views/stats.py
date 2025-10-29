from datetime import datetime, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from ..extensions import db
from ..models import Book, Class, Grade, Lend, Reader, ReturnRecord


bp = Blueprint("stats", __name__)


@bp.route("/")
@login_required
def dashboard():
    end_date = request.args.get("end")
    start_date = request.args.get("start")
    default_end = datetime.utcnow()
    default_start = default_end - timedelta(days=30)

    if start_date:
        default_start = datetime.fromisoformat(start_date)
    if end_date:
        default_end = datetime.fromisoformat(end_date)

    lend_stats = (
        db.session.query(func.date(Lend.created_at), func.count(Lend.id))
        .filter(Lend.created_at.between(default_start, default_end), Lend.is_deleted.is_(False))
        .group_by(func.date(Lend.created_at))
        .all()
    )
    return_stats = (
        db.session.query(func.date(ReturnRecord.created_at), func.count(ReturnRecord.id))
        .filter(ReturnRecord.created_at.between(default_start, default_end), ReturnRecord.is_deleted.is_(False))
        .group_by(func.date(ReturnRecord.created_at))
        .all()
    )

    grade_stats = (
        db.session.query(
            Grade.name.label("grade"),
            Class.name.label("class"),
            func.count(func.distinct(Lend.id)).label("lend_count"),
            func.count(func.distinct(ReturnRecord.id)).label("return_count"),
        )
        .join(Class, Class.grade_id == Grade.id)
        .outerjoin(Reader, Reader.class_id == Class.id)
        .outerjoin(Lend, Lend.reader_id == Reader.id)
        .outerjoin(ReturnRecord, ReturnRecord.lend_id == Lend.id)
        .filter(Grade.is_deleted.is_(False), Class.is_deleted.is_(False))
        .group_by(Grade.name, Class.name)
        .all()
    )

    book_inventory_total = (
        db.session.query(func.coalesce(func.sum(Book.amount - Book.lend_amount), 0))
        .filter(Book.is_deleted.is_(False))
        .scalar()
        or 0
    )
    book_isbn_total = (
        db.session.query(func.count(func.distinct(Book.isbn)))
        .filter(Book.is_deleted.is_(False))
        .scalar()
        or 0
    )
    reader_total = (
        db.session.query(func.count(Reader.id)).filter(Reader.is_deleted.is_(False)).scalar() or 0
    )
    active_reader_total = (
        db.session.query(func.count(func.distinct(Lend.reader_id)))
        .filter(Lend.status == "lent", Lend.is_deleted.is_(False))
        .scalar()
        or 0
    )
    popular_books_query = (
        db.session.query(Book.name, func.sum(Lend.amount).label("total"))
        .join(Lend, Lend.book_id == Book.id)
        .filter(Book.is_deleted.is_(False))
        .group_by(Book.id)
        .order_by(func.sum(Lend.amount).desc())
        .limit(50)
        .all()
    )
    popular_books = [
        {"name": name, "total": total or 0}
        for name, total in popular_books_query
    ]

    overdue_1y = get_overdue_count(365)
    overdue_6_12 = get_overdue_between(180, 365)
    overdue_6 = get_overdue_between(30, 180)
    overdue_1m = get_overdue_between(0, 30)
    recent_unreturned = get_recent_borrowed_unreturned(30)

    return render_template(
        "stats/dashboard.html",
        lend_stats=lend_stats,
        return_stats=return_stats,
        grade_stats=grade_stats,
        book_inventory_total=book_inventory_total,
        book_isbn_total=book_isbn_total,
        reader_total=reader_total,
        active_reader_total=active_reader_total,
        popular_books=popular_books,
        default_start=default_start.date(),
        default_end=default_end.date(),
        overdue_1y=overdue_1y,
        overdue_6_12=overdue_6_12,
        overdue_6=overdue_6,
        overdue_1m=overdue_1m,
        recent_unreturned=recent_unreturned,
    )


def get_overdue_count(days: int) -> int:
    deadline = datetime.utcnow() - timedelta(days=days)
    return (
        db.session.query(func.count(Lend.id))
        .filter(Lend.status == "lent", Lend.due_date <= deadline, Lend.is_deleted.is_(False))
        .scalar()
        or 0
    )


def get_overdue_between(min_days: int, max_days: int) -> int:
    now = datetime.utcnow()
    min_deadline = now - timedelta(days=max_days)
    max_deadline = now - timedelta(days=min_days)
    return (
        db.session.query(func.count(Lend.id))
        .filter(
            Lend.status == "lent",
            Lend.due_date >= min_deadline,
            Lend.due_date < max_deadline,
            Lend.is_deleted.is_(False),
        )
        .scalar()
        or 0
    )


def get_recent_borrowed_unreturned(days: int) -> int:
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.session.query(func.count(Lend.id))
        .filter(
            Lend.status == "lent",
            Lend.created_at >= since,
            Lend.is_deleted.is_(False),
        )
        .scalar()
        or 0
    )
