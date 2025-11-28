import json
from pathlib import Path

from pydantic import BaseModel


# TODO: find a way to get this info in a nice format: https://en.wikipedia.org/wiki/List_of_Wikipedias#Active_editions
class WikipediaEntry(BaseModel):
    wikipedia_id: str
    alpha3: str  # iso 639 3 code
    scripts: list[str]  # iso
    language: str  # English name


def get_wikipedia_entries(path: Path) -> list[WikipediaEntry]:
    return [WikipediaEntry(wikipedia_id=w_id, **entry) for w_id, entry in json.loads(path.read_bytes()).items()]
