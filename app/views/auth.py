from flask import Blueprint, redirect, render_template, request, url_for, flash
from flask_login import current_user, login_required, login_user, logout_user

from ..models import User
from ..extensions import db


bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("stats.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("stats.dashboard"))
        flash("用户名或密码错误", "danger")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_password or not new_password or not confirm_password:
            flash("请完整填写所有字段", "danger")
            return redirect(url_for("auth.change_password"))

        if not current_user.check_password(current_password):
            flash("当前密码错误", "danger")
            return redirect(url_for("auth.change_password"))

        if new_password != confirm_password:
            flash("两次输入的新密码不一致", "danger")
            return redirect(url_for("auth.change_password"))

        if len(new_password) < 6:
            flash("新密码长度至少为6位", "danger")
            return redirect(url_for("auth.change_password"))

        current_user.set_password(new_password)
        db.session.commit()
        flash("密码修改成功", "success")
        return redirect(url_for("stats.dashboard"))

    return render_template("auth/change_password.html")
