"""Database schema facade.

The concrete bootstrap, migration-repair, default-row, search-index, and seed helpers
live in focused schema_* modules. This module keeps the historic import path stable.
"""

from __future__ import annotations

from .schema_core import init_db
from .schema_defaults import (
    ensure_moderation_macro_defaults,
    ensure_registration_defaults,
    ensure_site_settings_defaults,
)
from .schema_maintenance import ensure_column, ensure_database_schema
from .schema_search import ensure_search_index_schema
from .schema_seed import seed_sections

__all__ = [
    "ensure_column",
    "ensure_database_schema",
    "ensure_moderation_macro_defaults",
    "ensure_registration_defaults",
    "ensure_search_index_schema",
    "ensure_site_settings_defaults",
    "init_db",
    "seed_sections",
]
