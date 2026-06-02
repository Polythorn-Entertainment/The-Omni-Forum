"""Compatibility facade for focused API content mixins."""

from __future__ import annotations

from .api_content_sections import SectionContentApiMixin
from .api_content_threads import ThreadContentApiMixin
from .api_content_posts import PostContentApiMixin
from .api_content_reactions import ReactionContentApiMixin


class ContentApiMixin(SectionContentApiMixin, ThreadContentApiMixin, PostContentApiMixin, ReactionContentApiMixin):
    pass
