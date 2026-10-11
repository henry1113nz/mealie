"""Temporary relationship/filter metadata for domains awaiting C5-C6.

Application group CRUD uses native Tortoise models from models.group.
These projections exist only for unconverted domains and legacy bootstrap.
"""

from .ai_providers import *
from .exports import *
from .group import *
from .preferences import *
from .report import *
