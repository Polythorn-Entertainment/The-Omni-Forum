"""Compatibility facade for focused moderation API mixins."""

from __future__ import annotations

from .api_moderation_reports import ReportModerationApiMixin
from .api_moderation_appeals import AppealModerationApiMixin
from .api_moderation_users import UserModerationApiMixin


class ModerationApiMixin(ReportModerationApiMixin, AppealModerationApiMixin, UserModerationApiMixin):
    pass
