import io
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from openpyxl import Workbook, load_workbook

from ..extensions import db
from ..models import Book, Category


bp = Blueprint("books", __name__, url_prefix="/books")


@bp.route("/")
@login_required
def list_books():
    keyword = request.args.get("q", "").strip()
    query = Book.query.filter_by(is_deleted=False)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter((Book.name.like(like)) | (Book.isbn.like(like)))
    books = query.order_by(Book.updated_at.desc()).all()
    categories = Category.query.filter_by(is_deleted=False).order_by(Category.name).all()
    return render_template("books/list.html", books=books, categories=categories, keyword=keyword)


@bp.route("/create", methods=["POST"])
@login_required
def create_book():
    form = request.form
    isbn = form.get("isbn", "").strip()
    if not isbn:
        flash("ISBN不能为空", "danger")
        return redirect(url_for("books.list_books"))
    if Book.query.filter_by(isbn=isbn).first():
        flash("该ISBN已存在", "danger")
        return redirect(url_for("books.list_books"))

    book = Book(
        name=form.get("name", "未命名图书"),
        isbn=isbn,
        position=form.get("position"),
        category_id=int(form.get("category_id")) if form.get("category_id") else None,
        amount=int(form.get("amount", 1) or 1),
        lend_amount=int(form.get("lend_amount", 0) or 0),
        price=form.get("price") or 0,
        publisher=form.get("publisher"),
        author=form.get("author"),
        version=form.get("version"),
        source=form.get("source"),
        index_id=form.get("index_id"),
        pages=form.get("pages") or None,
        images=form.get("images"),
        summary=form.get("summary"),
        input_num=form.get("input_num") or None,
        remark=form.get("remark"),
    )
    db.session.add(book)
    db.session.commit()
    flash("图书创建成功", "success")
    return redirect(url_for("books.list_books"))


@bp.route("/<int:book_id>/update", methods=["POST"])
@login_required
def update_book(book_id: int):
    book = Book.query.get_or_404(book_id)
    form = request.form
    book.name = form.get("name", book.name)
    book.isbn = form.get("isbn", book.isbn)
    book.position = form.get("position")
    book.category_id = int(form.get("category_id")) if form.get("category_id") else None
    book.amount = int(form.get("amount", book.amount) or book.amount)
    book.lend_amount = int(form.get("lend_amount", book.lend_amount) or book.lend_amount)
    book.price = form.get("price") or book.price
    book.publisher = form.get("publisher")
    book.author = form.get("author")
    book.version = form.get("version")
    book.source = form.get("source")
    book.index_id = form.get("index_id")
    book.pages = form.get("pages") or book.pages
    book.images = form.get("images")
    book.summary = form.get("summary")
    book.input_num = form.get("input_num") or book.input_num
    book.remark = form.get("remark")
    db.session.commit()
    flash("图书信息已更新", "success")
    return redirect(url_for("books.list_books"))


@bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id: int):
    book = Book.query.get_or_404(book_id)
    book.is_deleted = True
    db.session.commit()
    flash("图书已删除", "success")
    return redirect(url_for("books.list_books"))


@bp.route("/import", methods=["POST"])
@login_required
def import_books():
    file = request.files.get("file")
    if not file:
        flash("请选择Excel文件", "danger")
        return redirect(url_for("books.list_books"))

    try:
        wb = load_workbook(file, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        count = 0
        for row in rows:
            if not row:
                continue
            isbn = str(row[1]).strip() if row[1] else None
            if not isbn or Book.query.filter_by(isbn=isbn).first():
                continue
            book = Book(
                name=row[0] or "未命名图书",
                isbn=isbn,
                position=row[2],
                amount=int(row[3] or 1),
                price=row[4] or 0,
                publisher=row[5],
                author=row[6],
                summary=row[7],
            )
            db.session.add(book)
            count += 1
        db.session.commit()
        flash(f"成功导入 {count} 条图书记录", "success")
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        flash(f"导入失败: {exc}", "danger")

    return redirect(url_for("books.list_books"))


@bp.route("/export")
@login_required
def export_books():
    wb = Workbook()
    ws = wb.active
    ws.append([
        "图书名称",
        "ISBN",
        "位置",
        "总数量",
        "已借出",
        "价格",
        "出版社",
        "作者",
        "简介",
    ])
    for book in Book.query.filter_by(is_deleted=False).order_by(Book.name).all():
        ws.append(
            [
                book.name,
                book.isbn,
                book.position,
                book.amount,
                book.lend_amount,
                float(book.price or 0),
                book.publisher,
                book.author,
                book.summary,
            ]
        )

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"books-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
