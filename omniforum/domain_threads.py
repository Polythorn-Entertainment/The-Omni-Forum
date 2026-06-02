"""Thread domain facade.

Bookmark/subscription, section, thread-record, listing, and post helpers live in
focused domain_thread* modules. This module keeps the historic imports stable.
"""

from __future__ import annotations

from .domain_posts import get_posts_for_thread, list_post_edit_history, serialize_post_history_item
from .domain_sections import (
    get_category_by_slug,
    get_next_section_sort_order,
    get_section_by_slug,
    get_sections_with_stats,
    serialize_section_summary,
)
from .domain_thread_lists import (
    get_featured_threads,
    get_related_threads,
    get_trending_threads,
    list_threads_for_section,
)
from .domain_thread_membership import (
    ensure_thread_subscription,
    list_saved_threads,
    thread_first_post_id,
    thread_user_flags,
    toggle_thread_membership,
)
from .domain_thread_records import (
    add_thread_note,
    get_thread_by_id,
    list_thread_notes,
    serialize_thread,
    serialize_thread_note,
)

__all__ = [
    "add_thread_note",
    "ensure_thread_subscription",
    "get_category_by_slug",
    "get_featured_threads",
    "get_next_section_sort_order",
    "get_posts_for_thread",
    "get_related_threads",
    "get_section_by_slug",
    "get_sections_with_stats",
    "get_thread_by_id",
    "get_trending_threads",
    "list_post_edit_history",
    "list_saved_threads",
    "list_thread_notes",
    "list_threads_for_section",
    "serialize_post_history_item",
    "serialize_section_summary",
    "serialize_thread",
    "serialize_thread_note",
    "thread_first_post_id",
    "thread_user_flags",
    "toggle_thread_membership",
]
