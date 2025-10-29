from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import User


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
    users = User.query.order_by(User.username).all()
    return render_template("system/users.html", users=users)


@bp.route("/users", methods=["POST"])
@login_required
def create_user():
    if not admin_required():
        return redirect(url_for("system.list_users"))
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    level = request.form.get("level", "operator")
    if not username or not password:
        flash("用户名和密码不能为空", "danger")
        return redirect(url_for("system.list_users"))
    if User.query.filter_by(username=username).first():
        flash("用户名已存在", "danger")
        return redirect(url_for("system.list_users"))
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
