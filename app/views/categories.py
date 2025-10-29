from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Category


bp = Blueprint("categories", __name__, url_prefix="/categories")


@bp.route("/")
@login_required
def list_categories():
    categories = Category.query.filter_by(is_deleted=False).order_by(Category.sort, Category.name).all()
    return render_template("categories/list.html", categories=categories)


@bp.route("/create", methods=["POST"])
@login_required
def create_category():
    name = request.form.get("name", "").strip()
    if not name:
        flash("分类名称不能为空", "danger")
        return redirect(url_for("categories.list_categories"))
    category = Category(
        name=name,
        parent_id=request.form.get("parent_id") or None,
        sort=int(request.form.get("sort") or 0),
    )
    db.session.add(category)
    db.session.commit()
    flash("分类创建成功", "success")
    return redirect(url_for("categories.list_categories"))


@bp.route("/<int:category_id>/update", methods=["POST"])
@login_required
def update_category(category_id: int):
    category = Category.query.get_or_404(category_id)
    category.name = request.form.get("name", category.name)
    category.parent_id = request.form.get("parent_id") or None
    if request.form.get("sort") is not None:
        category.sort = int(request.form.get("sort") or 0)
    db.session.commit()
    flash("分类已更新", "success")
    return redirect(url_for("categories.list_categories"))


@bp.route("/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id: int):
    category = Category.query.get_or_404(category_id)
    category.is_deleted = True
    db.session.commit()
    flash("分类已删除", "success")
    return redirect(url_for("categories.list_categories"))
