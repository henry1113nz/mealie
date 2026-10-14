"""Incremental Tortoise model graph.

These mappings coexist with the legacy SQLAlchemy models during the staged
migration. The Stage 3 baseline covers groups, households and users. It keeps
the legacy table and column names and mirrors their current key constraints:

* ``groups.name`` and ``groups.slug`` are unique (and indexed).
* Household names and slugs are unique within a group; both are indexed.
* User usernames and emails are globally unique and indexed.
* Group and household ownership foreign keys are indexed.

The SQLite mappings use Tortoise UUID fields and are also compatible with
PostgreSQL UUID columns. PostgreSQL schema creation and constraint behavior
still requires a separate backend smoke check.
"""

from .group import Group
from .household import Household
from .user import AuthMethod, User

__all__ = ["AuthMethod", "Group", "Household", "User"]
