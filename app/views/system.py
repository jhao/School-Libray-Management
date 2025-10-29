import os
import shutil
from datetime import datetime
from typing import List, Optional

from flask import (
    Blueprint,
    current_app,
    flash,
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

from ..constants import DEFAULT_BRAND_COLOR
from ..extensions import db
from ..models import SystemSetting, User
from ..utils.pagination import get_page_args


bp = Blueprint("system", __name__, url_prefix="/system")


def admin_required():
    if current_user.level != "admin":
        flash("只有管理员可以执行此操作", "danger")
        return False
    return True


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
