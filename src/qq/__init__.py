from importlib.metadata import version

__version__ = version("qwanqwa")

from qq.interface import GeographicRegion, Languoid, Script

__all__ = [
    "GeographicRegion",
    "Languoid",
    "Script",
]
