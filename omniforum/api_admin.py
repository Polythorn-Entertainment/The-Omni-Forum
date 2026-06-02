"""Admin API facade over focused admin handler mixins."""

from __future__ import annotations

from .api_admin_backups import BackupAdminApiMixin
from .api_admin_data import DataAdminApiMixin
from .api_admin_exporting import ExportAdminApiMixin
from .api_admin_plugins import PluginAdminApiMixin
from .api_admin_registration import RegistrationAdminApiMixin
from .api_admin_settings import SettingsAdminApiMixin
from .api_admin_status import StatusAdminApiMixin


class AdminApiMixin(
    PluginAdminApiMixin,
    StatusAdminApiMixin,
    BackupAdminApiMixin,
    SettingsAdminApiMixin,
    ExportAdminApiMixin,
    RegistrationAdminApiMixin,
    DataAdminApiMixin,
):
    pass
