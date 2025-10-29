import io
from datetime import datetime
from importlib import import_module
from importlib.util import find_spec
from typing import TYPE_CHECKING, Optional, Tuple

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required

if TYPE_CHECKING:  # pragma: no cover - assists static analysis only
    from openpyxl import Workbook as WorkbookType
    from openpyxl import load_workbook as LoadWorkbookType
else:  # pragma: no cover - runtime alias without importing optional dependency
    WorkbookType = object
    LoadWorkbookType = object

_OPENPYXL_CACHE: Tuple[Optional[WorkbookType], Optional[LoadWorkbookType], bool]
_OPENPYXL_CACHE = (None, None, False)


def _ensure_openpyxl() -> Tuple[Optional[WorkbookType], Optional[LoadWorkbookType], bool]:
    """Lazily import openpyxl, returning its key entry points when available."""

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
from ..models import Class, Grade, Reader


bp = Blueprint("readers", __name__, url_prefix="/readers")


@bp.route("/")
@login_required
def list_readers():
    keyword = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    query = Reader.query.filter_by(is_deleted=False)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter((Reader.name.like(like)) | (Reader.card_no.like(like)))
    pagination = query.order_by(Reader.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    classes = Class.query.filter_by(is_deleted=False).order_by(Class.name).all()
    return render_template(
        "readers/list.html",
        readers=pagination.items,
        keyword=keyword,
        pagination=pagination,
        classes=classes,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_reader():
    classes = Class.query.filter_by(is_deleted=False).order_by(Class.name).all()

    if request.method == "GET":
        return render_template("readers/create.html", classes=classes)

    form = request.form
    card_no = form.get("card_no", "").strip()
    if not card_no:
        flash("读者卡号不能为空", "danger")
        return redirect(url_for("readers.create_reader"))
    if Reader.query.filter_by(card_no=card_no).first():
        flash("卡号已存在", "danger")
        return redirect(url_for("readers.create_reader"))
    reader = Reader(
        card_no=card_no,
        name=form.get("name", "未命名读者"),
        sex=form.get("sex"),
        phone=form.get("phone"),
        cert_type=form.get("cert_type"),
        cert_no=form.get("cert_no"),
        class_id=int(form.get("class_id")) if form.get("class_id") else None,
    )
    db.session.add(reader)
    db.session.commit()
    flash("读者创建成功", "success")
    return redirect(url_for("readers.list_readers"))


@bp.route("/<int:reader_id>/update", methods=["POST"])
@login_required
def update_reader(reader_id: int):
    reader = Reader.query.get_or_404(reader_id)
    form = request.form
    reader.card_no = form.get("card_no", reader.card_no)
    reader.name = form.get("name", reader.name)
    reader.sex = form.get("sex")
    reader.phone = form.get("phone")
    reader.cert_type = form.get("cert_type")
    reader.cert_no = form.get("cert_no")
    reader.class_id = int(form.get("class_id")) if form.get("class_id") else None
    db.session.commit()
    flash("读者信息已更新", "success")
    return redirect(url_for("readers.list_readers"))


@bp.route("/<int:reader_id>/delete", methods=["POST"])
@login_required
def delete_reader(reader_id: int):
    reader = Reader.query.get_or_404(reader_id)
    reader.is_deleted = True
    db.session.commit()
    flash("读者已删除", "success")
    return redirect(url_for("readers.list_readers"))


@bp.route("/import", methods=["POST"])
@login_required
def import_readers():
    _, load_workbook_fn, has_openpyxl = _ensure_openpyxl()
    if not has_openpyxl or load_workbook_fn is None:
        flash("当前环境缺少 openpyxl 依赖，无法导入读者数据。", "danger")
        return redirect(url_for("readers.list_readers"))

    if request.form.get("template_confirmed") != "1":
        flash("请先下载导入模板并确认后再上传数据。", "warning")
        return redirect(url_for("readers.list_readers"))

    file = request.files.get("file")
    if not file:
        flash("请选择Excel文件", "danger")
        return redirect(url_for("readers.list_readers"))

    try:
        wb = load_workbook_fn(file, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        count = 0
        for row in rows:
            if not row:
                continue
            card_no = str(row[0]).strip() if row[0] else None
            if not card_no or Reader.query.filter_by(card_no=card_no).first():
                continue
            reader = Reader(
                card_no=card_no,
                name=row[1] or "未命名读者",
                phone=row[2],
                sex=row[3],
            )
            db.session.add(reader)
            count += 1
        db.session.commit()
        flash(f"成功导入 {count} 条读者记录", "success")
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        flash(f"导入失败: {exc}", "danger")

    return redirect(url_for("readers.list_readers"))


@bp.route("/import-template")
@login_required
def download_reader_template():
    workbook_cls, _, has_openpyxl = _ensure_openpyxl()
    if not has_openpyxl or workbook_cls is None:
        flash("当前环境缺少 openpyxl 依赖，无法生成模板。", "danger")
        return redirect(url_for("readers.list_readers"))

    wb = workbook_cls()
    ws = wb.active
    ws.append(["卡号", "姓名", "电话", "性别"])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return send_file(
        stream,
        as_attachment=True,
        download_name="reader-import-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/export")
@login_required
def export_readers():
    workbook_cls, _, has_openpyxl = _ensure_openpyxl()
    if not has_openpyxl or workbook_cls is None:
        flash("当前环境缺少 openpyxl 依赖，无法导出读者数据。", "danger")
        return redirect(url_for("readers.list_readers"))

    wb = workbook_cls()
    ws = wb.active
    ws.append(["卡号", "姓名", "电话", "性别", "班级"])
    for reader in Reader.query.filter_by(is_deleted=False).order_by(Reader.name).all():
        ws.append(
            [
                reader.card_no,
                reader.name,
                reader.phone,
                reader.sex,
                reader.reader_class.name if reader.reader_class else "",
            ]
        )
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"readers-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/grades")
@login_required
def manage_grades():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    pagination = Grade.query.filter_by(is_deleted=False).order_by(Grade.name).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template("readers/grades.html", grades=pagination.items, pagination=pagination)


@bp.route("/grades/create", methods=["GET", "POST"])
@login_required
def create_grade():
    if request.method == "GET":
        return render_template("readers/grades_create.html")

    name = request.form.get("name", "").strip()
    if not name:
        flash("年级名称不能为空", "danger")
        return redirect(url_for("readers.create_grade"))
    grade = Grade(name=name)
    db.session.add(grade)
    db.session.commit()
    flash("年级创建成功", "success")
    return redirect(url_for("readers.manage_grades"))


@bp.route("/grades/<int:grade_id>/delete", methods=["POST"])
@login_required
def delete_grade(grade_id: int):
    grade = Grade.query.get_or_404(grade_id)
    grade.is_deleted = True
    db.session.commit()
    flash("年级已删除", "success")
    return redirect(url_for("readers.manage_grades"))


@bp.route("/classes")
@login_required
def manage_classes():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    pagination = (
        Class.query.filter_by(is_deleted=False)
        .order_by(Class.name)
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    grades = Grade.query.filter_by(is_deleted=False).order_by(Grade.name).all()
    return render_template(
        "readers/classes.html",
        classes=pagination.items,
        grades=grades,
        pagination=pagination,
    )


@bp.route("/classes/create", methods=["GET", "POST"])
@login_required
def create_class():
    grades = Grade.query.filter_by(is_deleted=False).order_by(Grade.name).all()
    if request.method == "GET":
        return render_template("readers/classes_create.html", grades=grades)

    name = request.form.get("name", "").strip()
    grade_id = request.form.get("grade_id")
    if not name or not grade_id:
        flash("班级名称与所属年级不能为空", "danger")
        return redirect(url_for("readers.create_class"))
    klass = Class(name=name, grade_id=int(grade_id))
    db.session.add(klass)
    db.session.commit()
    flash("班级创建成功", "success")
    return redirect(url_for("readers.manage_classes"))


@bp.route("/classes/<int:class_id>/delete", methods=["POST"])
@login_required
def delete_class(class_id: int):
    klass = Class.query.get_or_404(class_id)
    klass.is_deleted = True
    db.session.commit()
    flash("班级已删除", "success")
    return redirect(url_for("readers.manage_classes"))
