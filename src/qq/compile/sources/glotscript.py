from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, BeforeValidator
from typing_extensions import Annotated


def split_script_codes(item: str | None) -> list[str] | None:
    if isinstance(item, str):
        if item_s := item.strip():
            return item_s.split(", ")
    return None


class GlotScriptEntry(BaseModel):
    iso639_3: str  # iso 639 3 code
    iso15924_main: Annotated[list[str] | None, BeforeValidator(split_script_codes)] = None
    wiki_aux: str | None = None  # conflicting information, only wiki agrees
    sil_aux: str | None = None  # conflicting information, only sil agrees
    lrec2800_aux: str | None = None  # conflicting information, only lrec 2008 agrees
    sil2_aux: str | None = None  # conflicting information between language tag and script source


def get_glotscript_entries(path: Path) -> list[GlotScriptEntry]:
    return [
        GlotScriptEntry(**item)
        for item in pd.read_csv(path, sep="\t")
        .rename(columns=lambda col: col.replace("-", "_").lower())
        .dropna(subset=["iso639_3"])  # not sure why this is in there
        .replace({np.nan: None})
        .to_dict("records")
    ]
