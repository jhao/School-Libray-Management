import os
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from sqlalchemy.exc import OperationalError

from ..extensions import db
from ..models import SystemSetting, User


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
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
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
    current_color = SystemSetting.get_value("topbar_color") or "#1f2d3d"

    if request.method == "POST":
        color = request.form.get("topbar_color", current_color).strip() or "#1f2d3d"
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
    )
