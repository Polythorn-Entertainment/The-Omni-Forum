"""Thread content API facade over focused thread handler mixins."""

from __future__ import annotations

from .api_content_thread_create import CreateThreadContentApiMixin
from .api_content_thread_delete import DeleteThreadContentApiMixin
from .api_content_thread_membership import MembershipThreadContentApiMixin
from .api_content_thread_polls import PollThreadContentApiMixin
from .api_content_thread_split import SplitThreadContentApiMixin
from .api_content_thread_update import UpdateThreadContentApiMixin
from .api_content_thread_view import ViewThreadContentApiMixin


class ThreadContentApiMixin(
    CreateThreadContentApiMixin,
    ViewThreadContentApiMixin,
    UpdateThreadContentApiMixin,
    SplitThreadContentApiMixin,
    DeleteThreadContentApiMixin,
    MembershipThreadContentApiMixin,
    PollThreadContentApiMixin,
):
    pass
