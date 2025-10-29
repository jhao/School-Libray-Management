from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    Book,
    Class,
    Grade,
    Lend,
    Reader,
    ReturnRecord,
    find_book_by_isbn,
    find_reader_by_card,
)
from ..utils.pagination import get_page_args


bp = Blueprint("lending", __name__, url_prefix="/lending")


@bp.route("/borrow", methods=["GET", "POST"])
@login_required
def borrow():
    if request.method == "POST":
        card_no = request.form.get("card_no", "").strip()
        isbn = request.form.get("isbn", "").strip()
        amount = int(request.form.get("amount", 1) or 1)
        due_days = int(request.form.get("due_days", 30) or 30)

        reader = find_reader_by_card(card_no)
        if not reader:
            flash("未找到读者信息", "danger")
            return redirect(url_for("lending.borrow"))
        book = find_book_by_isbn(isbn)
        if not book:
            flash("未找到对应图书", "danger")
            return redirect(url_for("lending.borrow"))
        if book.available_amount() < amount:
            flash("库存不足", "danger")
            return redirect(url_for("lending.borrow"))

        lend = Lend(
            book=book,
            reader=reader,
            amount=amount,
            due_date=datetime.utcnow() + timedelta(days=due_days),
        )
        book.lend_amount += amount
        db.session.add(lend)
        db.session.commit()
        flash("借阅成功", "success")
        return redirect(url_for("lending.borrow"))

    lends = (
        Lend.query.filter_by(is_deleted=False)
        .order_by(Lend.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template("lending/borrow.html", lends=lends)


@bp.route("/return", methods=["GET", "POST"])
@login_required
def return_book():
    if request.method == "POST":
        card_no = request.form.get("card_no", "").strip()
        isbn = request.form.get("isbn", "").strip()
        amount = int(request.form.get("amount", 1) or 1)

        reader = find_reader_by_card(card_no)
        if not reader:
            flash("未找到读者信息", "danger")
            return redirect(url_for("lending.return_book"))
        book = find_book_by_isbn(isbn)
        if not book:
            flash("未找到对应图书", "danger")
            return redirect(url_for("lending.return_book"))

        lend = (
            Lend.query.filter_by(reader=reader, book=book, status="lent", is_deleted=False)
            .order_by(Lend.created_at.asc())
            .first()
        )
        if not lend:
            flash("未找到借阅记录", "danger")
            return redirect(url_for("lending.return_book"))

        return_record = ReturnRecord(lend=lend, amount=amount)
        lend.mark_returned()
        book.lend_amount = max(book.lend_amount - amount, 0)
        db.session.add(return_record)
        db.session.commit()
        flash("归还成功", "success")
        return redirect(url_for("lending.return_book"))

    returns = ReturnRecord.query.order_by(ReturnRecord.created_at.desc()).limit(20).all()
    return render_template("lending/return.html", returns=returns)


@bp.route("/records")
@login_required
def records():
    card_no = request.args.get("card_no", "").strip()
    isbn = request.args.get("isbn", "").strip()
    reader_name = request.args.get("reader_name", "").strip()
    book_name = request.args.get("book_name", "").strip()
    grade_id_raw = request.args.get("grade_id", "").strip()
    class_id_raw = request.args.get("class_id", "").strip()
    status = request.args.get("status", "all").strip() or "all"
    start_date_raw = request.args.get("start_date", "").strip()
    end_date_raw = request.args.get("end_date", "").strip()

    grade_id = int(grade_id_raw) if grade_id_raw.isdigit() else None
    class_id = int(class_id_raw) if class_id_raw.isdigit() else None

    query = (
        Lend.query.options(
            selectinload(Lend.reader)
            .selectinload(Reader.reader_class)
            .selectinload(Class.grade),
            selectinload(Lend.book),
        )
        .join(Reader, Lend.reader)
        .join(Book, Lend.book)
        .outerjoin(Class, Reader.reader_class)
        .outerjoin(Grade, Class.grade)
        .filter(Lend.is_deleted.is_(False))
    )

    if card_no:
        query = query.filter(Reader.card_no.like(f"%{card_no}%"))
    if reader_name:
        query = query.filter(Reader.name.like(f"%{reader_name}%"))
    if isbn:
        query = query.filter(Book.isbn.like(f"%{isbn}%"))
    if book_name:
        query = query.filter(Book.name.like(f"%{book_name}%"))
    if grade_id is not None:
        query = query.filter(Grade.id == grade_id)
    if class_id is not None:
        query = query.filter(Class.id == class_id)
    if status == "lent":
        query = query.filter(Lend.status == "lent")
    elif status == "returned":
        query = query.filter(Lend.status == "returned")

    if start_date_raw:
        try:
            start_date = datetime.strptime(start_date_raw, "%Y-%m-%d")
            query = query.filter(Lend.created_at >= start_date)
        except ValueError:
            start_date_raw = ""
    if end_date_raw:
        try:
            end_date = datetime.strptime(end_date_raw, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Lend.created_at < end_date)
        except ValueError:
            end_date_raw = ""

    page, per_page = get_page_args()
    pagination = query.order_by(Lend.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    grades = (
        Grade.query.filter_by(is_deleted=False)
        .order_by(Grade.name)
        .all()
    )
    classes_query = (
        Class.query.filter_by(is_deleted=False)
        .join(Grade)
        .filter(Grade.is_deleted.is_(False))
    )
    if grade_id is not None:
        classes_query = classes_query.filter(Class.grade_id == grade_id)
    classes = classes_query.order_by(Grade.name, Class.name).all()

    filters = {
        "card_no": card_no,
        "isbn": isbn,
        "reader_name": reader_name,
        "book_name": book_name,
        "grade_id": grade_id,
        "class_id": class_id,
        "status": status,
        "start_date": start_date_raw,
        "end_date": end_date_raw,
    }

    return render_template(
        "lending/records.html",
        records=pagination.items,
        pagination=pagination,
        grades=grades,
        classes=classes,
        filters=filters,
    )
