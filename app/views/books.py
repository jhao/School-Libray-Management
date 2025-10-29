import io
from datetime import datetime
from importlib import import_module
from importlib.util import find_spec
from typing import TYPE_CHECKING, List, Optional, Tuple

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from markupsafe import Markup
from sqlalchemy.orm import joinedload

if TYPE_CHECKING:  # pragma: no cover - used solely for type checkers
    from openpyxl import Workbook as WorkbookType
    from openpyxl import load_workbook as LoadWorkbookType
else:  # pragma: no cover - executed at runtime but simply provides aliases
    WorkbookType = object
    LoadWorkbookType = object

_OPENPYXL_CACHE: Tuple[Optional[WorkbookType], Optional[LoadWorkbookType], bool]
_OPENPYXL_CACHE = (None, None, False)


def _ensure_openpyxl() -> Tuple[Optional[WorkbookType], Optional[LoadWorkbookType], bool]:
    """Attempt to import openpyxl lazily.

    Returns the Workbook class, load_workbook callable and a boolean indicating
    whether the dependency is available. The result is cached to avoid repeated
    import attempts during a single request lifecycle.
    """

    global _OPENPYXL_CACHE
    workbook_cls, load_workbook_fn, has_attempted = _OPENPYXL_CACHE
    if has_attempted:
        return workbook_cls, load_workbook_fn, workbook_cls is not None and load_workbook_fn is not None

    if find_spec("openpyxl") is None:  # pragma: no cover - optional dependency may be absent
        _OPENPYXL_CACHE = (None, None, True)
        return None, None, False

    module = import_module("openpyxl")

    workbook_cls = getattr(module, "Workbook", None)
    load_workbook_fn = getattr(module, "load_workbook", None)
    _OPENPYXL_CACHE = (workbook_cls, load_workbook_fn, True)
    return workbook_cls, load_workbook_fn, workbook_cls is not None and load_workbook_fn is not None

from ..extensions import db
from ..models import Book, Category
from ..utils.category_tree import build_category_tree, flatten_category_tree
from ..utils.pagination import get_page_args


bp = Blueprint("books", __name__, url_prefix="/books")


def _category_options():
    categories = (
        Category.query.filter_by(is_deleted=False)
        .order_by(Category.sort, Category.name)
        .all()
    )
    category_tree = build_category_tree(categories)
    return list(flatten_category_tree(category_tree))


@bp.route("/")
@login_required
def list_books():
    keyword = request.args.get("q", "").strip()
    call_number = request.args.get("call_number", "").strip()
    position = request.args.get("position", "").strip()
    category_id_raw = request.args.get("category_id", "").strip()
    category_id = int(category_id_raw) if category_id_raw.isdigit() else None
    page, per_page = get_page_args()
    query = (
        Book.query.filter_by(is_deleted=False)
        .options(joinedload(Book.category), joinedload(Book.updated_by))
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.filter((Book.name.like(like)) | (Book.isbn.like(like)))
    if call_number:
        query = query.filter(Book.call_number.like(f"%{call_number}%"))
    if position:
        query = query.filter(Book.position.like(f"%{position}%"))
    if category_id is not None:
        query = query.filter(Book.category_id == category_id)
    pagination = query.order_by(Book.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template(
        "books/list.html",
        books=pagination.items,
        filters={
            "keyword": keyword,
            "call_number": call_number,
            "position": position,
            "category_id": category_id,
        },
        pagination=pagination,
        category_options=_category_options(),
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_book():
    if request.method == "GET":
        category_options = _category_options()
        return render_template("books/create.html", category_options=category_options)

    form = request.form
    name = form.get("name", "").strip()
    if not name:
        flash("图书名称不能为空", "danger")
        return redirect(url_for("books.create_book"))

    isbn = form.get("isbn", "").strip()
    if not isbn:
        flash("ISBN不能为空", "danger")
        return redirect(url_for("books.create_book"))

    amount_raw = (form.get("amount") or "").strip()
    if not amount_raw:
        flash("数量不能为空", "danger")
        return redirect(url_for("books.create_book"))
    try:
        amount = int(amount_raw)
    except ValueError:
        flash("数量必须为数字", "danger")
        return redirect(url_for("books.create_book"))
    if amount <= 0:
        flash("数量必须大于0", "danger")
        return redirect(url_for("books.create_book"))

    call_number = form.get("call_number") or None
    position = form.get("position")
    category_id_value = int(form.get("category_id")) if form.get("category_id") else None
    lend_amount = int(form.get("lend_amount", 0) or 0)
    price = form.get("price") or 0
    publisher = form.get("publisher")
    author = form.get("author")
    version = form.get("version")
    source = form.get("source")
    index_id = form.get("index_id")
    pages = form.get("pages") or None
    images = form.get("images")
    summary = form.get("summary")
    input_num = form.get("input_num") or None
    remark = form.get("remark")

    existing_active = Book.query.filter_by(isbn=isbn, is_deleted=False).first()
    if existing_active:
        flash("该ISBN已存在", "danger")
        return redirect(url_for("books.create_book"))

    existing_deleted = Book.query.filter_by(isbn=isbn, is_deleted=True).first()
    if existing_deleted:
        existing_deleted.name = name
        existing_deleted.isbn = isbn
        existing_deleted.call_number = call_number
        existing_deleted.position = position
        existing_deleted.category_id = category_id_value
        existing_deleted.amount = amount
        existing_deleted.lend_amount = lend_amount
        existing_deleted.price = price
        existing_deleted.publisher = publisher
        existing_deleted.author = author
        existing_deleted.version = version
        existing_deleted.source = source
        existing_deleted.index_id = index_id
        existing_deleted.pages = pages
        existing_deleted.images = images
        existing_deleted.summary = summary
        existing_deleted.input_num = input_num
        existing_deleted.remark = remark
        existing_deleted.updated_by_id = current_user.id
        existing_deleted.is_deleted = False
        db.session.commit()
        flash("图书创建成功", "success")
        return redirect(url_for("books.list_books"))

    book = Book(
        name=name,
        isbn=isbn,
        call_number=call_number,
        position=position,
        category_id=category_id_value,
        amount=amount,
        lend_amount=lend_amount,
        price=price,
        publisher=publisher,
        author=author,
        version=version,
        source=source,
        index_id=index_id,
        pages=pages,
        images=images,
        summary=summary,
        input_num=input_num,
        remark=remark,
    )
    book.updated_by_id = current_user.id
    db.session.add(book)
    db.session.commit()
    flash("图书创建成功", "success")
    return redirect(url_for("books.list_books"))


@bp.route("/<int:book_id>/update", methods=["POST"])
@login_required
def update_book(book_id: int):
    book = Book.query.get_or_404(book_id)
    form = request.form
    name = form.get("name", "").strip()
    isbn = form.get("isbn", "").strip()
    amount_raw = (form.get("amount") or "").strip()

    if not name:
        flash("图书名称不能为空", "danger")
        return redirect(url_for("books.list_books"))
    if not isbn:
        flash("ISBN不能为空", "danger")
        return redirect(url_for("books.list_books"))
    if not amount_raw:
        flash("数量不能为空", "danger")
        return redirect(url_for("books.list_books"))

    try:
        amount = int(amount_raw)
    except ValueError:
        flash("数量必须为数字", "danger")
        return redirect(url_for("books.list_books"))

    if amount <= 0:
        flash("数量必须大于0", "danger")
        return redirect(url_for("books.list_books"))

    book.name = name
    book.isbn = isbn
    book.call_number = form.get("call_number") or None
    book.position = form.get("position")
    book.category_id = int(form.get("category_id")) if form.get("category_id") else None
    book.amount = amount
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
    book.updated_by_id = current_user.id
    db.session.commit()
    flash("图书信息已更新", "success")
    return redirect(url_for("books.list_books"))


@bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id: int):
    if current_user.level != "admin":
        flash("只有管理员可以执行删除操作", "danger")
        return redirect(url_for("books.list_books"))
    book = Book.query.get_or_404(book_id)
    book.is_deleted = True
    book.updated_by_id = current_user.id
    db.session.commit()
    flash("图书已删除", "success")
    return redirect(url_for("books.list_books"))


@bp.route("/import", methods=["POST"])
@login_required
def import_books():
    _, load_workbook_fn, has_openpyxl = _ensure_openpyxl()
    if not has_openpyxl or load_workbook_fn is None:
        flash("未安装 openpyxl 库，无法导入。请先运行 pip install openpyxl。", "danger")
        return redirect(url_for("books.list_books"))

    if request.form.get("template_confirmed") != "1":
        flash("请先下载导入模板并确认后再上传数据。", "warning")
        return redirect(url_for("books.list_books"))

    file = request.files.get("file")
    if not file:
        flash("请选择Excel文件", "danger")
        return redirect(url_for("books.list_books"))

    try:
        wb = load_workbook_fn(file, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        created_count = 0
        restored_count = 0
        skipped: List[str] = []

        for index, row in enumerate(rows, start=2):
            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                continue

            name_value = str(row[0]).strip() if len(row) > 0 and row[0] else "未命名图书"
            isbn = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            if not isbn:
                skipped.append(f"第{index}行: ISBN 不能为空")
                continue

            existing_active = Book.query.filter_by(isbn=isbn, is_deleted=False).first()
            if existing_active:
                skipped.append(f"第{index}行(ISBN {isbn}): 已存在未删除的图书")
                continue

            position = row[2] if len(row) > 2 else None
            raw_amount = row[3] if len(row) > 3 else None
            try:
                if raw_amount in (None, ""):
                    amount = 1
                else:
                    amount = int(float(raw_amount))
            except (TypeError, ValueError):
                skipped.append(f"第{index}行(ISBN {isbn}): 数量格式不正确")
                continue
            if amount <= 0:
                skipped.append(f"第{index}行(ISBN {isbn}): 数量必须大于0")
                continue

            price = row[4] if len(row) > 4 else 0
            publisher = row[5] if len(row) > 5 else None
            author = row[6] if len(row) > 6 else None
            summary = row[7] if len(row) > 7 else None

            existing_deleted = Book.query.filter_by(isbn=isbn, is_deleted=True).first()
            if existing_deleted:
                existing_deleted.name = name_value or existing_deleted.name or "未命名图书"
                existing_deleted.position = position
                existing_deleted.amount = amount
                existing_deleted.lend_amount = 0
                existing_deleted.price = price or 0
                existing_deleted.publisher = publisher
                existing_deleted.author = author
                existing_deleted.summary = summary
                existing_deleted.updated_by_id = current_user.id
                existing_deleted.is_deleted = False
                restored_count += 1
                continue

            book = Book(
                name=name_value,
                isbn=isbn,
                position=position,
                amount=amount,
                price=price or 0,
                publisher=publisher,
                author=author,
                summary=summary,
            )
            book.updated_by_id = current_user.id
            db.session.add(book)
            created_count += 1

        db.session.commit()

        success_parts = []
        if created_count:
            success_parts.append(f"成功导入 {created_count} 条图书记录")
        if restored_count:
            success_parts.append(f"恢复 {restored_count} 条已删除图书记录")
        if success_parts:
            flash("，".join(success_parts), "success")

        if skipped:
            preview = skipped[:100]
            if len(skipped) > 100:
                preview.append(f"……共 {len(skipped)} 条错误，仅显示前100条")
            flash(Markup("部分数据导入失败：<br>" + "<br>".join(preview)), "danger")
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        flash(f"导入失败: {exc}", "danger")

    return redirect(url_for("books.list_books"))


@bp.route("/import-template")
@login_required
def download_import_template():
    workbook_cls, _, has_openpyxl = _ensure_openpyxl()
    if not has_openpyxl or workbook_cls is None:
        flash("未安装 openpyxl 库，无法生成模板。请先运行 pip install openpyxl。", "danger")
        return redirect(url_for("books.list_books"))

    wb = workbook_cls()
    ws = wb.active
    ws.append(["图书名称", "ISBN", "位置", "数量", "价格", "出版社", "作者", "简介"])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return send_file(
        stream,
        as_attachment=True,
        download_name="book-import-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/export")
@login_required
def export_books():
    workbook_cls, _, has_openpyxl = _ensure_openpyxl()
    if not has_openpyxl or workbook_cls is None:
        flash("未安装 openpyxl 库，无法导出。请先运行 pip install openpyxl。", "danger")
        return redirect(url_for("books.list_books"))

    wb = workbook_cls()
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
