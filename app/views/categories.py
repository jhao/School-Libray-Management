from typing import List, Set

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import Category
from ..utils.category_tree import CategoryNode, build_category_tree, flatten_category_tree


bp = Blueprint("categories", __name__, url_prefix="/categories")


@bp.route("/")
@login_required
def list_categories():
    category_tree = _load_category_tree()
    category_rows = list(flatten_category_tree(category_tree))
    return render_template("categories/list.html", category_rows=category_rows)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_category():
    category_tree = _load_category_tree()
    category_options = list(flatten_category_tree(category_tree))
    if request.method == "GET":
        return render_template("categories/create.html", category_options=category_options)

    name = request.form.get("name", "").strip()
    if not name:
        flash("分类名称不能为空", "danger")
        return redirect(url_for("categories.create_category"))
    category = Category(
        name=name,
        parent_id=request.form.get("parent_id") or None,
        sort=int(request.form.get("sort") or 0),
    )
    db.session.add(category)
    db.session.commit()
    flash("分类创建成功", "success")
    return redirect(url_for("categories.list_categories"))


@bp.route("/<int:category_id>/edit")
@login_required
def edit_category(category_id: int):
    category = Category.query.get_or_404(category_id)
    category_tree = _load_category_tree()
    excluded_ids = _collect_subtree_ids(category_tree, category.id)
    filtered_tree = _filter_category_tree(category_tree, excluded_ids)
    category_options = list(flatten_category_tree(filtered_tree))
    return render_template(
        "categories/edit.html",
        category=category,
        category_options=category_options,
    )


@bp.route("/<int:category_id>/update", methods=["POST"])
@login_required
def update_category(category_id: int):
    category = Category.query.get_or_404(category_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("分类名称不能为空", "danger")
        return redirect(url_for("categories.edit_category", category_id=category.id))

    category_tree = _load_category_tree()
    excluded_ids = _collect_subtree_ids(category_tree, category.id)

    parent_id_value = request.form.get("parent_id") or None
    if parent_id_value:
        parent_id = int(parent_id_value)
        if parent_id in excluded_ids:
            flash("无法将父分类设置为当前分类或其子分类", "danger")
            return redirect(url_for("categories.edit_category", category_id=category.id))
        category.parent_id = parent_id
    else:
        category.parent_id = None

    category.name = name
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


def _load_category_tree() -> List[CategoryNode]:
    categories = (
        Category.query.filter_by(is_deleted=False)
        .order_by(Category.sort, Category.name)
        .all()
    )
    return build_category_tree(categories)


def _collect_subtree_ids(nodes: List[CategoryNode], target_id: int) -> Set[int]:
    for node in nodes:
        if node["category"].id == target_id:
            ids: Set[int] = set()
            _gather_subtree_ids(node, ids)
            return ids
        child_ids = _collect_subtree_ids(node["children"], target_id)
        if child_ids:
            return child_ids
    return {target_id}


def _gather_subtree_ids(node: CategoryNode, buffer: Set[int]) -> None:
    buffer.add(node["category"].id)
    for child in node["children"]:
        _gather_subtree_ids(child, buffer)


def _filter_category_tree(
    nodes: List[CategoryNode], excluded_ids: Set[int]
) -> List[CategoryNode]:
    filtered: List[CategoryNode] = []
    for node in nodes:
        if node["category"].id in excluded_ids:
            continue
        filtered_children = _filter_category_tree(node["children"], excluded_ids)
        filtered.append({"category": node["category"], "children": filtered_children})
    return filtered
