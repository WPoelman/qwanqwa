import json
from pathlib import Path

from pydantic import BaseModel


class PycountryISO6393Entry(BaseModel):
    alpha_3: str
    name: str
    inverted_name: str | None = None
    scope: str  # TODO: figure out what this means (I?)
    type: str  # TODO: figure out what this means, see L or E (living, extinct?)


class PycountryISO6395Entry(BaseModel):
    alpha_3: str
    name: str


class PycountryISO31661Entry(BaseModel):
    alpha_2: str  # two letter country code
    alpha_3: str  # three letter country code
    flag: str  # emoji of the flag
    name: str
    numeric: int


class PycountryISO31662Entry(BaseModel):
    code: str
    name: str
    type: str


class PycountryISO31663Entry(BaseModel):
    alpha_2: str
    alpha_3: str
    alpha_4: str
    comment: str | None = None
    name: str
    numeric: int | None = None
    withdrawal_date: str


class PycountryISO15924Entry(BaseModel):
    alpha_4: str
    name: str
    numeric: int


# TODO: there's a lot of repetition here, maybe find better way


def get_pycountry_6393_entries(path: Path) -> list[PycountryISO6393Entry]:
    return [PycountryISO6393Entry(**item) for item in json.loads(path.read_bytes())["639-3"]]


def get_pycountry_6395_entries(path: Path) -> list[PycountryISO6395Entry]:
    return [PycountryISO6395Entry(**item) for item in json.loads(path.read_bytes())["639-5"]]


def get_pycountry_31661_entries(path: Path) -> list[PycountryISO31661Entry]:
    return [PycountryISO31661Entry(**item) for item in json.loads(path.read_bytes())["3166-1"]]


def get_pycountry_31662_entries(path: Path) -> list[PycountryISO31662Entry]:
    return [PycountryISO31662Entry(**item) for item in json.loads(path.read_bytes())["3166-2"]]


def get_pycountry_31663_entries(path: Path) -> list[PycountryISO31663Entry]:
    return [PycountryISO31663Entry(**item) for item in json.loads(path.read_bytes())["3166-3"]]


def get_pycountry_15924_entries(path: Path) -> list[PycountryISO15924Entry]:
    return [PycountryISO15924Entry(**item) for item in json.loads(path.read_bytes())["15924"]]
