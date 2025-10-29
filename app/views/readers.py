import io
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from openpyxl import Workbook, load_workbook

from ..extensions import db
from ..models import Class, Grade, Reader


bp = Blueprint("readers", __name__, url_prefix="/readers")


@bp.route("/")
@login_required
def list_readers():
    keyword = request.args.get("q", "").strip()
    query = Reader.query.filter_by(is_deleted=False)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter((Reader.name.like(like)) | (Reader.card_no.like(like)))
    readers = query.order_by(Reader.updated_at.desc()).all()
    grades = Grade.query.filter_by(is_deleted=False).order_by(Grade.name).all()
    classes = Class.query.filter_by(is_deleted=False).order_by(Class.name).all()
    return render_template(
        "readers/list.html",
        readers=readers,
        grades=grades,
        classes=classes,
        keyword=keyword,
    )


@bp.route("/create", methods=["POST"])
@login_required
def create_reader():
    form = request.form
    card_no = form.get("card_no", "").strip()
    if not card_no:
        flash("读者卡号不能为空", "danger")
        return redirect(url_for("readers.list_readers"))
    if Reader.query.filter_by(card_no=card_no).first():
        flash("卡号已存在", "danger")
        return redirect(url_for("readers.list_readers"))
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
    file = request.files.get("file")
    if not file:
        flash("请选择Excel文件", "danger")
        return redirect(url_for("readers.list_readers"))

    try:
        wb = load_workbook(file, data_only=True)
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


@bp.route("/export")
@login_required
def export_readers():
    wb = Workbook()
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


@bp.route("/grades", methods=["GET", "POST"])
@login_required
def manage_grades():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("年级名称不能为空", "danger")
            return redirect(url_for("readers.manage_grades"))
        grade = Grade(name=name)
        db.session.add(grade)
        db.session.commit()
        flash("年级创建成功", "success")
        return redirect(url_for("readers.manage_grades"))
    grades = Grade.query.filter_by(is_deleted=False).order_by(Grade.name).all()
    return render_template("readers/grades.html", grades=grades)


@bp.route("/grades/<int:grade_id>/delete", methods=["POST"])
@login_required
def delete_grade(grade_id: int):
    grade = Grade.query.get_or_404(grade_id)
    grade.is_deleted = True
    db.session.commit()
    flash("年级已删除", "success")
    return redirect(url_for("readers.manage_grades"))


@bp.route("/classes", methods=["GET", "POST"])
@login_required
def manage_classes():
    grades = Grade.query.filter_by(is_deleted=False).order_by(Grade.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        grade_id = request.form.get("grade_id") or None
        if not name or not grade_id:
            flash("班级名称与所属年级不能为空", "danger")
            return redirect(url_for("readers.manage_classes"))
        klass = Class(name=name, grade_id=grade_id)
        db.session.add(klass)
        db.session.commit()
        flash("班级创建成功", "success")
        return redirect(url_for("readers.manage_classes"))
    classes = Class.query.filter_by(is_deleted=False).order_by(Class.name).all()
    return render_template("readers/classes.html", grades=grades, classes=classes)


@bp.route("/classes/<int:class_id>/delete", methods=["POST"])
@login_required
def delete_class(class_id: int):
    klass = Class.query.get_or_404(class_id)
    klass.is_deleted = True
    db.session.commit()
    flash("班级已删除", "success")
    return redirect(url_for("readers.manage_classes"))
