import json
import os
import random
import shutil
from datetime import date, datetime, timedelta
from typing import List, Optional, Set

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine.url import make_url
from sqlalchemy.sql import func

from ..constants import DEFAULT_BRAND_COLOR
from ..extensions import db
from ..models import (
    Book,
    Class,
    Grade,
    Lend,
    Reader,
    ReturnRecord,
    SystemSetting,
    TestDataBatch,
    User,
)
from ..utils.pagination import get_page_args


bp = Blueprint("system", __name__, url_prefix="/system")


def admin_required():
    if current_user.level != "admin":
        flash("只有管理员可以执行此操作", "danger")
        return False
    return True


def _ensure_super_admin() -> User:
    user = User.query.filter_by(username="超级管理员").first()
    if user:
        if user.level != "admin":
            user.level = "admin"
            db.session.commit()
        return user
    user = User(username="超级管理员", level="admin")
    user.set_password("testdata123")
    db.session.add(user)
    db.session.commit()
    return user


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _pick_random_datetime(
    start_day: date,
    end_day: date,
    excluded: Set[str],
    min_datetime: Optional[datetime] = None,
) -> Optional[datetime]:
    if start_day > end_day:
        return None
    days: List[date] = []
    cursor = start_day
    while cursor <= end_day:
        if cursor.strftime("%Y-%m-%d") not in excluded:
            days.append(cursor)
        cursor += timedelta(days=1)
    if not days:
        return None
    chosen_day = random.choice(days)
    day_start = datetime.combine(chosen_day, datetime.min.time())
    day_end = day_start + timedelta(days=1, seconds=-1)
    lower_bound = day_start
    if min_datetime and chosen_day == min_datetime.date():
        lower_bound = max(lower_bound, min_datetime)
    if lower_bound > day_end:
        return lower_bound
    span = int((day_end - lower_bound).total_seconds())
    offset = random.randint(0, span if span > 0 else 0)
    return lower_bound + timedelta(seconds=offset)


def _build_grade_tree() -> List[dict]:
    grades = (
        Grade.query.filter_by(is_deleted=False)
        .order_by(Grade.name)
        .all()
    )
    tree: List[dict] = []
    for grade in grades:
        classes = [
            {"id": klass.id, "name": klass.name}
            for klass in sorted(grade.classes, key=lambda c: c.name)
            if not klass.is_deleted
        ]
        tree.append({"id": grade.id, "name": grade.name, "classes": classes})
    return tree


def _normalize_id_list(values: Optional[List]) -> List[int]:
    result: List[int] = []
    if not values:
        return result
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _delete_super_admin_data(super_admin: User) -> int:
    deleted_count = 0
    returns = ReturnRecord.query.filter(
        ReturnRecord.operator_id == super_admin.id
    ).all()
    for record in returns:
        db.session.delete(record)
        deleted_count += 1

    lends = (
        Lend.query.filter(
            (Lend.borrow_operator_id == super_admin.id)
            | (Lend.return_operator_id == super_admin.id)
        )
        .all()
    )
    for lend in lends:
        if lend.status != "returned" and lend.book:
            lend.book.lend_amount = max(lend.book.lend_amount - lend.amount, 0)
        db.session.delete(lend)
        deleted_count += 1
    db.session.commit()
    return deleted_count


@bp.route("/users")
@login_required
def list_users():
    if not admin_required():
        return redirect(url_for("stats.dashboard"))
    page, per_page = get_page_args()
    pagination = User.query.order_by(User.username).paginate(page=page, per_page=per_page, error_out=False)
    return render_template("system/users.html", users=pagination.items, pagination=pagination)


@bp.route("/users/create", methods=["GET", "POST"])
@login_required
def create_user():
    if not admin_required():
        return redirect(url_for("system.list_users"))
    if request.method == "GET":
        return render_template("system/user_create.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    level = request.form.get("level", "operator")
    if not username or not password:
        flash("用户名和密码不能为空", "danger")
        return redirect(url_for("system.create_user"))
    if User.query.filter_by(username=username).first():
        flash("用户名已存在", "danger")
        return redirect(url_for("system.create_user"))
    user = User(username=username, level=level)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash("用户创建成功", "success")
    return redirect(url_for("system.list_users"))


@bp.route("/users/<int:user_id>", methods=["POST"])
@login_required
def update_user(user_id: int):
    if not admin_required():
        return redirect(url_for("system.list_users"))
    user = User.query.get_or_404(user_id)
    user.level = request.form.get("level", user.level)
    if request.form.get("password"):
        user.set_password(request.form.get("password"))
    db.session.commit()
    flash("用户信息已更新", "success")
    return redirect(url_for("system.list_users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id: int):
    if not admin_required():
        return redirect(url_for("system.list_users"))
    if current_user.id == user_id:
        flash("不能删除当前登录用户", "danger")
        return redirect(url_for("system.list_users"))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("用户已删除", "success")
    return redirect(url_for("system.list_users"))


@bp.route("/users/<int:user_id>/reset", methods=["POST"])
@login_required
def reset_password(user_id: int):
    if not admin_required():
        return redirect(url_for("system.list_users"))
    user = User.query.get_or_404(user_id)
    user.set_password("123456")
    db.session.commit()
    flash("密码已重置为123456", "success")
    return redirect(url_for("system.list_users"))


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def system_settings():
    if not admin_required():
        return redirect(url_for("stats.dashboard"))

    current_logo = SystemSetting.get_value("system_logo") or ""
    current_color = SystemSetting.get_value("topbar_color") or DEFAULT_BRAND_COLOR

    if request.method == "POST":
        color = request.form.get("topbar_color", current_color).strip() or DEFAULT_BRAND_COLOR
        try:
            SystemSetting.set_value("topbar_color", color)
        except OperationalError:
            db.session.rollback()
            flash("数据库尚未初始化系统设置表，请先运行数据迁移。", "danger")
            return redirect(url_for("system.system_settings"))

        remove_logo = request.form.get("remove_logo") == "1"
        uploaded_file = request.files.get("logo")
        if uploaded_file and uploaded_file.filename:
            filename = secure_filename(uploaded_file.filename)
            _, ext = os.path.splitext(filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            stored_filename = f"system-logo-{timestamp}{ext or '.png'}"
            upload_folder = os.path.join(current_app.static_folder, "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, stored_filename)
            uploaded_file.save(file_path)
            if current_logo:
                existing_path = os.path.join(current_app.static_folder, current_logo)
                if os.path.exists(existing_path):
                    try:
                        os.remove(existing_path)
                    except OSError:
                        pass
            try:
                SystemSetting.set_value("system_logo", f"uploads/{stored_filename}")
            except OperationalError:
                db.session.rollback()
                flash("数据库尚未初始化系统设置表，请先运行数据迁移。", "danger")
                return redirect(url_for("system.system_settings"))
            current_logo = f"uploads/{stored_filename}"
        elif remove_logo:
            if current_logo:
                existing_path = os.path.join(current_app.static_folder, current_logo)
                if os.path.exists(existing_path):
                    try:
                        os.remove(existing_path)
                    except OSError:
                        pass
            try:
                SystemSetting.set_value("system_logo", "")
            except OperationalError:
                db.session.rollback()
                flash("数据库尚未初始化系统设置表，请先运行数据迁移。", "danger")
                return redirect(url_for("system.system_settings"))
            current_logo = ""

        flash("系统外观设置已更新", "success")
        return redirect(url_for("system.system_settings"))

    return render_template(
        "system/settings.html",
        topbar_color=current_color,
        logo_path=current_logo,
        default_topbar_color=DEFAULT_BRAND_COLOR,
    )


@bp.route("/test-data")
@login_required
def test_data():
    if not admin_required():
        return redirect(url_for("stats.dashboard"))

    grade_tree = _build_grade_tree()
    batches_query = (
        TestDataBatch.query.order_by(TestDataBatch.created_at.desc()).all()
    )
    batches = []
    for batch in batches_query:
        batches.append(
            {
                "id": batch.id,
                "created_at": batch.created_at,
                "start_date": batch.start_date,
                "end_date": batch.end_date,
                "record_count": batch.record_count,
                "excluded_dates": json.loads(batch.excluded_dates or "[]"),
                "grade_ids": json.loads(batch.grade_ids or "[]"),
                "class_ids": json.loads(batch.class_ids or "[]"),
                "return_rate": float(batch.return_rate or 0),
                "triggered_by": batch.triggered_by.username if batch.triggered_by else "",
            }
        )

    return render_template(
        "system/test_data.html",
        grade_tree=grade_tree,
        batches=batches,
        default_return_rate=0.7,
    )


@bp.route("/test-data/execute", methods=["POST"])
@login_required
def execute_test_data():
    if not admin_required():
        return jsonify({"success": False, "message": "权限不足"}), 403

    payload = request.get_json(silent=True) or {}
    start_day = _parse_date(payload.get("start_date"))
    end_day = _parse_date(payload.get("end_date"))
    if not start_day or not end_day or start_day > end_day:
        return jsonify({"success": False, "message": "请提供有效的生成时间范围"}), 400

    excluded_dates = set(payload.get("excluded_dates") or [])
    grade_ids = _normalize_id_list(payload.get("grade_ids"))
    class_ids = _normalize_id_list(payload.get("class_ids"))
    return_rate_raw = payload.get("return_rate", 0.7)
    try:
        return_rate = float(return_rate_raw)
    except (TypeError, ValueError):
        return_rate = 0.7
    return_rate = max(0.0, min(return_rate, 1.0))

    super_admin = _ensure_super_admin()

    reader_query = Reader.query.filter(Reader.is_deleted.is_(False))
    if class_ids:
        reader_query = reader_query.filter(Reader.class_id.in_(class_ids))
    elif grade_ids:
        reader_query = reader_query.join(Class, Reader.reader_class).filter(
            Class.is_deleted.is_(False), Class.grade_id.in_(grade_ids)
        )

    reader = reader_query.order_by(func.random()).first()
    if not reader:
        return jsonify({"success": False, "message": "没有符合条件的读者数据"}), 400

    book_query = Book.query.filter(
        Book.is_deleted.is_(False), Book.amount > Book.lend_amount
    )
    book = book_query.order_by(func.random()).first()
    if not book:
        return jsonify({"success": False, "message": "当前库存不足，无法生成借阅记录"}), 400

    borrow_at = _pick_random_datetime(start_day, end_day, set(excluded_dates))
    if not borrow_at:
        return jsonify({"success": False, "message": "没有可用的生成日期"}), 400

    lend = Lend(
        book=book,
        reader=reader,
        amount=1,
        due_date=borrow_at + timedelta(days=random.randint(15, 45)),
        borrow_operator=super_admin,
    )
    lend.created_at = borrow_at
    lend.updated_at = borrow_at
    db.session.add(lend)
    book.lend_amount += lend.amount

    returned = False
    return_at = None
    if random.random() <= return_rate:
        return_at = _pick_random_datetime(
            borrow_at.date(),
            end_day,
            set(excluded_dates),
            min_datetime=borrow_at + timedelta(minutes=10),
        )
        if return_at:
            lend.status = "returned"
            lend.return_operator = super_admin
            lend.updated_at = return_at
            return_record = ReturnRecord(
                lend=lend,
                amount=lend.amount,
                operator=super_admin,
            )
            return_record.created_at = return_at
            return_record.updated_at = return_at
            db.session.add(return_record)
            book.lend_amount = max(book.lend_amount - lend.amount, 0)
            returned = True

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "lend_id": lend.id,
            "returned": returned,
            "borrowed_at": borrow_at.isoformat(),
            "returned_at": return_at.isoformat() if return_at else None,
        }
    )


@bp.route("/test-data/batches", methods=["POST"])
@login_required
def create_test_data_batch():
    if not admin_required():
        return jsonify({"success": False, "message": "权限不足"}), 403

    payload = request.get_json(silent=True) or {}
    start_day = _parse_date(payload.get("start_date"))
    end_day = _parse_date(payload.get("end_date"))
    record_count = payload.get("record_count")
    excluded_dates = payload.get("excluded_dates") or []
    grade_ids = _normalize_id_list(payload.get("grade_ids"))
    class_ids = _normalize_id_list(payload.get("class_ids"))
    return_rate_raw = payload.get("return_rate", 0.7)
    try:
        return_rate = float(return_rate_raw)
    except (TypeError, ValueError):
        return_rate = 0.7
    return_rate = max(0.0, min(return_rate, 1.0))

    if not start_day or not end_day or start_day > end_day:
        return jsonify({"success": False, "message": "请提供有效的生成时间范围"}), 400
    if not isinstance(record_count, int) or record_count <= 0:
        return jsonify({"success": False, "message": "请输入生成数量"}), 400

    batch = TestDataBatch(
        start_date=start_day,
        end_date=end_day,
        record_count=record_count,
        excluded_dates=json.dumps(excluded_dates),
        grade_ids=json.dumps(grade_ids),
        class_ids=json.dumps(class_ids),
        return_rate=return_rate,
        triggered_by=current_user,
    )
    db.session.add(batch)
    db.session.commit()

    return jsonify({"success": True, "batch_id": batch.id})


@bp.route("/test-data/batches/<int:batch_id>/delete", methods=["POST"])
@login_required
def delete_test_data_batch(batch_id: int):
    if not admin_required():
        return redirect(url_for("system.test_data"))

    batch = TestDataBatch.query.get_or_404(batch_id)
    super_admin = _ensure_super_admin()
    deleted = _delete_super_admin_data(super_admin)
    db.session.delete(batch)
    db.session.commit()

    flash(f"已删除 {deleted} 条测试数据", "success")
    return redirect(url_for("system.test_data"))


@bp.route("/backup", methods=["GET", "POST"])
@login_required
def backup_restore():
    if not admin_required():
        return redirect(url_for("stats.dashboard"))

    database_path = _get_database_path()
    database_exists = bool(database_path and os.path.exists(database_path))
    if request.method == "POST" and not database_exists:
        flash("当前数据库不支持备份或数据库文件不存在。", "danger")

    if request.method == "POST":
        action = request.form.get("action")
        if action == "backup":
            if not database_exists:
                flash("无法执行备份，数据库文件不存在。", "danger")
                _append_backup_log("backup", "数据库文件不存在", success=False)
                return redirect(url_for("system.backup_restore"))

            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            download_name = f"library-backup-{timestamp}.libk"
            _append_backup_log("backup", f"下载备份 {download_name}")
            return send_file(
                database_path,
                as_attachment=True,
                download_name=download_name,
                mimetype="application/octet-stream",
            )

        if action == "restore":
            uploaded_file = request.files.get("backup_file")
            if not uploaded_file or not uploaded_file.filename:
                flash("请选择要上传的备份文件。", "danger")
                _append_backup_log("restore", "未选择文件", success=False)
                return redirect(url_for("system.backup_restore"))

            filename = secure_filename(uploaded_file.filename)
            if not filename.lower().endswith(".libk"):
                flash("请上传 .libk 格式的备份文件。", "danger")
                _append_backup_log("restore", f"无效的文件格式: {filename}", success=False)
                return redirect(url_for("system.backup_restore"))

            if not database_exists:
                flash("数据库文件不存在，无法执行恢复。", "danger")
                _append_backup_log("restore", "数据库文件不存在", success=False)
                return redirect(url_for("system.backup_restore"))

            restore_folder = os.path.join(current_app.instance_path, "restore_uploads")
            os.makedirs(restore_folder, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            temp_restore_path = os.path.join(restore_folder, f"restore-{timestamp}.sqlite")

            try:
                uploaded_file.save(temp_restore_path)
                db.session.remove()
                db.engine.dispose()
                shutil.copyfile(temp_restore_path, database_path)
            except OSError as exc:
                flash("恢复过程中出现错误，请重试。", "danger")
                _append_backup_log("restore", f"文件操作失败: {exc}", success=False)
                return redirect(url_for("system.backup_restore"))
            finally:
                if os.path.exists(temp_restore_path):
                    try:
                        os.remove(temp_restore_path)
                    except OSError:
                        pass

            _append_backup_log("restore", f"从 {filename} 恢复数据库")
            flash("数据库已成功恢复。", "success")
            return redirect(url_for("system.backup_restore"))

    logs = _read_backup_log()
    return render_template(
        "system/backup_restore.html",
        database_exists=database_exists,
        logs=logs,
    )


def _get_database_path() -> Optional[str]:
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    try:
        url = make_url(uri)
    except Exception:
        return None
    if url.drivername != "sqlite":
        return None
    database_path = url.database or ""
    if not database_path or database_path == ":memory":
        return None
    return os.path.abspath(database_path)


def _get_backup_log_path() -> str:
    log_filename = "backup_restore.log"
    os.makedirs(current_app.instance_path, exist_ok=True)
    return os.path.join(current_app.instance_path, log_filename)


def _append_backup_log(action: str, detail: str, success: bool = True) -> None:
    status = "SUCCESS" if success else "FAILED"
    username = getattr(current_user, "username", "unknown")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {status} {action.upper()} by {username}: {detail}\n"
    log_path = _get_backup_log_path()
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(line)


def _read_backup_log() -> List[str]:
    log_path = _get_backup_log_path()
    if not os.path.exists(log_path):
        return []
    with open(log_path, "r", encoding="utf-8") as log_file:
        entries = [line.strip() for line in log_file.readlines() if line.strip()]
    return list(reversed(entries))
