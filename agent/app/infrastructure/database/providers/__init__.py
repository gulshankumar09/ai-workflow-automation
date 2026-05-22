"""
Database infrastructure package for provider abstraction layer.

This package provides database provider abstractions that enable switching between
different database backends (Supabase, PostgreSQL, SQLite) while maintaining
a consistent interface across the application.
"""

from .base import AbstractDatabaseProvider
from .factory import DatabaseProviderFactory, DatabaseProviderManager
from .supabase import SupabaseDatabaseProvider

__all__ = [
    "AbstractDatabaseProvider",
    "DatabaseProviderFactory", 
    "DatabaseProviderManager",
    "SupabaseDatabaseProvider",
] 