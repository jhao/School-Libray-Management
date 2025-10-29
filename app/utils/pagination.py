"""Pagination utilities shared across views and templates."""
from __future__ import annotations

from typing import List

from flask import Request, request, session, url_for

PER_PAGE_OPTIONS: tuple[int, ...] = (10, 20, 50, 100, 200)
DEFAULT_PER_PAGE: int = 20


def _resolve_per_page(per_page: int) -> int:
    """Return a safe per-page value limited to the configured options."""

    if per_page in PER_PAGE_OPTIONS:
        return per_page
    return DEFAULT_PER_PAGE


def get_page_args(req: Request | None = None) -> tuple[int, int]:
    """Return sanitized pagination arguments from the given request.

    The page number is clamped to 1 and the per-page value is restricted to
    the allowed options to avoid accidentally requesting huge page sizes.
    """

    req = req or request
    page = req.args.get("page", 1, type=int)
    per_page_arg = req.args.get("per_page", type=int)
    if per_page_arg is not None:
        per_page = _resolve_per_page(per_page_arg)
        session["pagination_per_page"] = per_page
    else:
        per_page = session.get("pagination_per_page", DEFAULT_PER_PAGE)
        per_page = _resolve_per_page(per_page)
    page = max(page, 1)
    return page, per_page


def build_pagination_links(pagination) -> List[int | None]:
    """Generate a compact list of page numbers (with gaps) for navigation."""

    total_pages = pagination.pages or 1
    current_page = pagination.page or 1

    if total_pages <= 1:
        return [1]

    block_start = max(min(current_page - 1, total_pages - 2), 1)
    block_end = min(block_start + 2, total_pages)

    pages = {1, total_pages}
    pages.update(range(block_start, block_end + 1))

    ordered_pages = sorted(pages)
    result: List[int | None] = []
    last_number: int | None = None
    for number in ordered_pages:
        if last_number is not None and number - last_number > 1:
            result.append(None)
        result.append(number)
        last_number = number
    return result


def build_pagination_url(page: int, per_page: int | None = None) -> str:
    """Build a URL pointing to a specific page while preserving query args."""

    args = request.args.to_dict()
    args["page"] = page
    if per_page is not None:
        args["per_page"] = per_page
    view_args = dict(request.view_args or {})
    return url_for(request.endpoint, **view_args, **args)
