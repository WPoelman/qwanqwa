from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, BeforeValidator
from typing_extensions import Annotated


class GlottologLanguoidLevel(str, Enum):
    language = "language"
    dialect = "dialect"
    family = "family"


# The glottolog info is distributed in a csv file.
# We transform it first into dicts and then into classes to make the workflow easier.
#


def split_country_ids(item: str | None) -> list[str] | None:
    if isinstance(item, str):
        if item_s := item.strip():
            return item_s.split()
    return None


class GlottologEntry(BaseModel):
    id: str  # internal id from glottolog
    name: str  # English name
    level: GlottologLanguoidLevel
    bookkeeping: bool  # Used for internal bookkeeping, so not relevant
    child_family_count: int  # sub-families below this one
    child_language_count: int
    child_dialect_count: int
    family_id: str | None = None  # glottocode for which family this language belongs to
    parent_id: str | None = None  # glottocode of direct ancestor
    latitude: float | None = None
    longitude: float | None = None
    iso639P3code: str | None = None  # iso-636-9 code
    description: str | None = None  # English description, mostly empty
    markup_description: str | None = None
    # I think these are ISO 3166-1 country codes
    country_ids: Annotated[list[str] | None, BeforeValidator(split_country_ids)] = None


def get_glottolog_entries(path: Path) -> list[GlottologEntry]:
    return [GlottologEntry(**item) for item in pd.read_csv(path).replace({np.nan: None}).to_dict("records")]
