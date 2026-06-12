from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from qq.data_model import ExternalResourceGroup, IdType


class ExternalResourceFileFormat(Enum):
    CSV = "csv"
    DSPACE_ITEM_JSON = "dspace_item_json"
    HUGGINGFACE_TAGS_JSON = "huggingface_tags_json"
    WIKIDATA_SPARQL_BINDINGS_JSON = "wikidata_sparql_bindings_json"


@dataclass(frozen=True)
class ExternalResourceDefinition:
    label: str
    group: ExternalResourceGroup
    url_template: str
    source_name: str | None = None
    filename: str | None = None
    file_format: ExternalResourceFileFormat = ExternalResourceFileFormat.CSV
    match_column: str | None = None
    match_id_type: IdType | None = None
    code_column: str | None = None
    url_column: str | None = None
    unique_per_languoid: bool = False
