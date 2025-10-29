from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required
from sqlalchemy import case, func
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
    isbn_prefill = request.args.get("isbn", "").strip()
    if request.method == "POST":
        card_no = request.form.get("card_no", "").strip()
        isbn = request.form.get("isbn", "").strip()
        amount = int(request.form.get("amount", 1) or 1)
        due_days = int(request.form.get("due_days", 30) or 30)

        reader = find_reader_by_card(card_no)
        if not reader:
            flash("未找到读者信息", "danger")
            return redirect(url_for("lending.borrow", isbn=isbn))
        book = find_book_by_isbn(isbn)
        if not book:
            flash("未找到对应图书", "danger")
            return redirect(url_for("lending.borrow", isbn=isbn))
        if book.available_amount() < amount:
            flash("库存不足", "danger")
            return redirect(url_for("lending.borrow", isbn=isbn))

        lend = Lend(
            book=book,
            reader=reader,
            amount=amount,
            due_date=datetime.utcnow() + timedelta(days=due_days),
            borrow_operator=current_user,
        )
        book.lend_amount += amount
        db.session.add(lend)
        db.session.commit()
        flash("借阅成功", "success")
        return redirect(url_for("lending.borrow"))

    lends = (
        Lend.query.filter_by(is_deleted=False)
        .options(
            selectinload(Lend.reader),
            selectinload(Lend.book),
            selectinload(Lend.borrow_operator),
            selectinload(Lend.return_operator),
        )
        .order_by(Lend.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "lending/borrow.html",
        lends=lends,
        isbn_prefill=isbn_prefill,
        current_time=datetime.utcnow(),
    )


@bp.route("/borrow/records")
@login_required
def borrow_records():
    card_no = request.args.get("card_no", "").strip()

    query = (
        Lend.query.filter_by(is_deleted=False)
        .options(
            selectinload(Lend.reader),
            selectinload(Lend.book),
            selectinload(Lend.borrow_operator),
        )
        .order_by(Lend.created_at.desc())
    )

    if card_no:
        reader = find_reader_by_card(card_no)
        if not reader:
            return jsonify({"lends": []})
        query = query.filter(Lend.reader == reader)

    lends = query.limit(20).all()
    current_time = datetime.utcnow()

    def build_due_info(lend: Lend):
        if not lend.due_date:
            return "", ""
        if lend.status == "returned":
            due_class = "due-returned"
        else:
            days_diff = (lend.due_date.date() - current_time.date()).days
            if days_diff >= 30:
                due_class = "due-safe"
            elif days_diff >= 10:
                due_class = "due-warning"
            elif days_diff >= 0:
                due_class = "due-urgent"
            else:
                due_class = "due-overdue"
        return lend.due_date.strftime("%Y-%m-%d"), due_class

    payload = []
    for lend in lends:
        due_text, due_class = build_due_info(lend)
        payload.append(
            {
                "id": lend.id,
                "created_at": lend.created_at.strftime("%Y-%m-%d %H:%M")
                if lend.created_at
                else "—",
                "reader": f"{lend.reader.name} ({lend.reader.card_no})"
                if lend.reader
                else "—",
                "book": f"{lend.book.name} ({lend.book.isbn})"
                if lend.book
                else "—",
                "amount": lend.amount,
                "due_date": due_text,
                "due_class": due_class,
                "borrow_operator": lend.borrow_operator.username
                if lend.borrow_operator
                else "—",
                "status_text": "已归还" if lend.status == "returned" else "借出中",
            }
        )

    return jsonify({"lends": payload})


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

        return_record = ReturnRecord(lend=lend, amount=amount, operator=current_user)
        lend.mark_returned()
        lend.return_operator = current_user
        book.lend_amount = max(book.lend_amount - amount, 0)
        db.session.add(return_record)
        db.session.commit()
        flash("归还成功", "success")
        return redirect(url_for("lending.return_book"))

    returns = (
        ReturnRecord.query.options(
            selectinload(ReturnRecord.lend)
            .selectinload(Lend.reader)
            .selectinload(Reader.reader_class)
            .selectinload(Class.grade),
            selectinload(ReturnRecord.lend).selectinload(Lend.book),
            selectinload(ReturnRecord.operator),
        )
        .order_by(ReturnRecord.created_at.desc())
        .limit(20)
        .all()
    )
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
        .options(
            selectinload(Lend.borrow_operator),
            selectinload(Lend.return_operator),
            selectinload(Lend.returns),
        )
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
    stats_result = (
        query.with_entities(
            func.count(Lend.id),
            func.coalesce(func.sum(Lend.amount), 0),
            func.coalesce(func.sum(case((Lend.status == "lent", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Lend.status == "returned", 1), else_=0)), 0),
        )
        .order_by(None)
        .first()
    )

    summary = {
        "total_records": stats_result[0] if stats_result else 0,
        "total_amount": stats_result[1] if stats_result else 0,
        "lent_count": stats_result[2] if stats_result else 0,
        "returned_count": stats_result[3] if stats_result else 0,
    }

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
        summary=summary,
        current_time=datetime.utcnow(),
    )


@bp.route("/<int:lend_id>/return", methods=["POST"])
@login_required
def return_from_record(lend_id: int):
    lend = Lend.query.options(selectinload(Lend.book)).filter_by(
        id=lend_id, is_deleted=False
    ).first_or_404()

    if lend.status != "lent":
        flash("该借阅记录已归还", "warning")
        next_url = request.form.get("next")
        return redirect(next_url or url_for("lending.records"))

    return_record = ReturnRecord(lend=lend, amount=lend.amount, operator=current_user)
    lend.mark_returned()
    lend.return_operator = current_user
    if lend.book:
        lend.book.lend_amount = max(lend.book.lend_amount - lend.amount, 0)
    db.session.add(return_record)
    db.session.commit()
    flash("归还成功", "success")

    next_url = request.form.get("next")
    return redirect(next_url or url_for("lending.records"))
