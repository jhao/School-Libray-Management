"""Helpers for working with category hierarchies."""

from __future__ import annotations

from typing import Dict, Iterable, Iterator, List, TypedDict

from ..models import Category


class CategoryNode(TypedDict):
    """Represents a node in a category tree."""

    category: Category
    children: List["CategoryNode"]


class FlattenedCategory(TypedDict):
    """A flattened tree item with hierarchy metadata."""

    category: Category
    depth: int
    has_children: bool


def build_category_tree(categories: Iterable[Category]) -> List[CategoryNode]:
    """Build a nested tree from the provided categories."""

    nodes: Dict[int, CategoryNode] = {}
    for category in categories:
        nodes[category.id] = {"category": category, "children": []}
    roots: List[CategoryNode] = []

    for category in categories:
        node = nodes[category.id]
        if category.parent_id and category.parent_id in nodes:
            nodes[category.parent_id]["children"].append(node)
        else:
            roots.append(node)

    _sort_nodes(roots)
    return roots


def flatten_category_tree(nodes: Iterable[CategoryNode], depth: int = 0) -> Iterator[FlattenedCategory]:
    """Yield flattened nodes with depth metadata for rendering."""

    for node in nodes:
        category = node["category"]
        children = node["children"]
        yield FlattenedCategory(
            category=category,
            depth=depth,
            has_children=bool(children),
        )
        yield from flatten_category_tree(children, depth + 1)


def _sort_nodes(nodes: List[CategoryNode]) -> None:
    """Recursively sort nodes by ``sort`` then ``name`` fields."""

    nodes.sort(key=lambda item: (item["category"].sort, item["category"].name))
    for node in nodes:
        _sort_nodes(node["children"])
