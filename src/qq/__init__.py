import logging
from importlib.metadata import version

from qq.access import Database, DeprecatedCodeWarning
from qq.data_model import (
    DeprecatedCode,
    EndangermentStatus,
    IdType,
    LanguageScope,
    LanguageStatus,
    LanguoidLevel,
    NameData,
    NameEntry,
    WikipediaInfo,
)
from qq.interface import GeographicRegion, Languoid, Script

__version__ = version("qwanqwa")
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "Database",
    "DeprecatedCode",
    "DeprecatedCodeWarning",
    "EndangermentStatus",
    "GeographicRegion",
    "IdType",
    "LanguageScope",
    "LanguageStatus",
    "Languoid",
    "LanguoidLevel",
    "NameData",
    "NameEntry",
    "Script",
    "WikipediaInfo",
]
