"""Output package - caching and format writing.

IMPORT RULES:
- Can import: models, config, logger, output.*
- Cannot import: processors, alternations, parsers, analyze
"""

from output.cache import CacheEntry, ResultCache
from output.writers import OutputWriter, AutoOutputWriter
from output.formats import (
    OutputFormatter,
    StreamingFormatter,
    TxtFormatter,
    CsvFormatter,
    JsonFormatter,
    JsonlFormatter,
)

__all__ = [
    # Cache
    "CacheEntry",
    "ResultCache",
    # Writers
    "OutputWriter",
    "AutoOutputWriter",
    # Formatters
    "OutputFormatter",
    "StreamingFormatter",
    "TxtFormatter",
    "CsvFormatter",
    "JsonFormatter",
    "JsonlFormatter",
]
