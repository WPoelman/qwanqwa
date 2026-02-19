from importlib.metadata import version

__version__ = version("qwanqwa")

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
