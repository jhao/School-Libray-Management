from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Book, Lend, ReturnRecord, find_book_by_isbn, find_reader_by_card


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
