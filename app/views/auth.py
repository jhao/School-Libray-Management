import secrets
import string

from flask import Blueprint, redirect, render_template, request, url_for, flash, jsonify, session
from flask_login import current_user, login_required, login_user, logout_user

from ..models import User
from ..extensions import db


bp = Blueprint("auth", __name__)


def _generate_captcha_code(length: int = 5) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _refresh_login_captcha() -> str:
    code = _generate_captcha_code()
    session["login_captcha"] = code
    return code


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("stats.dashboard"))

    captcha_code = session.get("login_captcha")
    if not captcha_code:
        captcha_code = _refresh_login_captcha()

    if request.method == "POST":
        submitted_captcha = request.form.get("captcha", "").strip().upper()
        stored_captcha = session.get("login_captcha", "")

        if not stored_captcha or submitted_captcha != stored_captcha:
            flash("验证码错误", "danger")
            captcha_code = _refresh_login_captcha()
            return render_template("auth/login.html", captcha_code=captcha_code)

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session.pop("login_captcha", None)
            login_user(user)
            return redirect(url_for("stats.dashboard"))
        flash("用户名或密码错误", "danger")
        captcha_code = _refresh_login_captcha()

    return render_template("auth/login.html", captcha_code=captcha_code)


@bp.route("/login/captcha", methods=["POST"])
def refresh_captcha():
    return jsonify({"captcha": _refresh_login_captcha()})


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
