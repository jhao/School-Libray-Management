from typing import Dict, List, Optional, Sequence, Set, TypedDict

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

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


@bp.route("/bulk-edit", methods=["GET", "POST"])
@login_required
def bulk_edit_categories():
    category_tree = _load_category_tree()
    if request.method == "POST":
        bulk_text = request.form.get("bulk_text", "")
        try:
            parsed_nodes = _parse_bulk_text(bulk_text)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template(
                "categories/bulk_edit.html",
                bulk_text=bulk_text,
            )

        _apply_bulk_changes(parsed_nodes)
        db.session.commit()
        flash("分类已批量更新", "success")
        return redirect(url_for("categories.list_categories"))

    bulk_text = "\n".join(_format_category_tree(category_tree))
    return render_template("categories/bulk_edit.html", bulk_text=bulk_text)


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
    if current_user.level != "admin":
        flash("只有管理员可以执行删除操作", "danger")
        return redirect(url_for("categories.list_categories"))
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


class ParsedCategoryNode(TypedDict):
    name: str
    children: List["ParsedCategoryNode"]


def _parse_bulk_text(text: str) -> List[ParsedCategoryNode]:
    nodes: List[ParsedCategoryNode] = []
    stack: List[ParsedCategoryNode] = []
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        if not line.strip():
            continue
        leading = len(line) - len(line.lstrip(" "))
        if leading % 2 != 0:
            raise ValueError(f"第 {index} 行的缩进不是两个空格的倍数")
        if "\t" in line[:leading]:
            raise ValueError(f"第 {index} 行不能使用制表符缩进")
        depth = leading // 2
        name = line.strip()
        if not name:
            raise ValueError(f"第 {index} 行缺少分类名称")
        if depth > len(stack):
            raise ValueError(f"第 {index} 行的缩进层级不合法")

        stack = stack[:depth]
        node: ParsedCategoryNode = {"name": name, "children": []}
        if depth == 0:
            nodes.append(node)
        else:
            stack[-1]["children"].append(node)

        stack.append(node)
    return nodes


def _format_category_tree(nodes: Sequence[CategoryNode], depth: int = 0) -> List[str]:
    lines: List[str] = []
    for node in nodes:
        category = node["category"]
        lines.append(f"{'  ' * depth}{category.name}")
        lines.extend(_format_category_tree(node["children"], depth + 1))
    return lines


def _apply_bulk_changes(nodes: List[ParsedCategoryNode]) -> None:
    existing_categories = (
        Category.query.filter_by(is_deleted=False)
        .order_by(Category.sort, Category.name, Category.id)
        .all()
    )
    categories_by_name: Dict[str, List[Category]] = {}
    for category in existing_categories:
        categories_by_name.setdefault(category.name, []).append(category)

    def _sync(children: List[ParsedCategoryNode], parent_id: Optional[int]) -> None:
        for sort_index, node in enumerate(children):
            name = node["name"]
            candidates = categories_by_name.get(name, [])
            category: Optional[Category] = None
            if candidates:
                preferred_index = next(
                    (i for i, item in enumerate(candidates) if item.parent_id == parent_id),
                    None,
                )
                if preferred_index is not None:
                    category = candidates.pop(preferred_index)
                else:
                    category = candidates.pop(0)

            if category is None:
                category = Category(name=name, parent_id=parent_id, sort=sort_index)
                db.session.add(category)
                db.session.flush()
            else:
                category.name = name
            category.parent_id = parent_id
            category.sort = sort_index
            category.is_deleted = False
            _sync(node["children"], category.id)

    _sync(nodes, None)

    for remaining in categories_by_name.values():
        for category in remaining:
            category.is_deleted = True

