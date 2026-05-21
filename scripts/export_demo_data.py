from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import qq  # noqa: E402
from qq import Database  # noqa: E402
from qq.constants import SOURCES_DIR  # noqa: E402
from qq.interface import GeographicRegion, Languoid, Script  # noqa: E402
from qq.sources.source_config import SourceConfig  # noqa: E402


DATA_DIR = ROOT / "demo" / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
NAME_BUCKETS_DIR = DATA_DIR / "names"
LEGACY_OUTPUT_PATH = ROOT / "demo" / "data.js"
BUCKET_COUNT = 128
NAME_BUCKET_COUNT = 256

SCOPE_LABELS = {
    "I": "Individual",
    "M": "Macrolanguage",
    "S": "Special",
}

STATUS_LABELS = {
    "L": "Living",
    "H": "Historical",
    "A": "Ancient",
    "C": "Constructed",
    "E": "Extinct",
    "S": "Special",
}

DEPRECATION_REASON_LABELS = {
    "C": "Change",
    "M": "Merge",
    "D": "Duplicate",
    "S": "Split",
    "N": "Non-existent",
}

CODE_TYPE_LABELS = {
    "bcp_47": "BCP-47",
    "iso_639_1": "ISO 639-1",
    "iso_639_2b": "ISO 639-2B",
    "iso_639_2t": "ISO 639-2T",
    "iso_639_3": "ISO 639-3",
    "iso_639_5": "ISO 639-5",
    "glottocode": "Glottocode",
    "wikidata_id": "Wikidata",
    "wikipedia": "Wikipedia",
}


def stringify(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def clean_list(values: list[str | None]) -> list[str]:
    return [value for value in values if value]


def clean_none(values: list[Any]) -> list[Any]:
    return [value for value in values if value is not None]


def clean_none_dict(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def bucket_for(entity_id: str) -> str:
    total = 0
    for index, char in enumerate(entity_id):
        total += (index + 1) * ord(char)
    return f"{total % BUCKET_COUNT:02x}"


def name_bucket_for(value: str) -> str:
    lowered = value.lower()
    return f"{ord(lowered[0]) % NAME_BUCKET_COUNT:02x}"


def make_property(value: Any) -> str | None:
    text = stringify(value)
    if text is None or text == "":
        return None
    return text


def enum_or_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def map_label(value: Any, mapping: dict[str, str]) -> str | None:
    raw = enum_or_value(value)
    if raw is None:
        return None
    return mapping.get(str(raw), str(raw))


def resolve_deprecated_targets(db: Database, entity: Languoid, deprecated: Any) -> list[str]:
    if deprecated.split_into:
        resolved: list[str] = []
        for code in deprecated.split_into:
            try:
                replacement = db.guess(code)
            except Exception:
                replacement = None
            if replacement is not None and replacement.id not in resolved:
                resolved.append(replacement.id)
        if resolved:
            return resolved
    return [entity.id]


def build_deprecated_replacement_index(db: Database) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for entity in db.all_languoids:
        for deprecated in entity.deprecated_codes or []:
            if not deprecated.code:
                continue
            key = deprecated.code.lower()
            targets = resolve_deprecated_targets(db, entity, deprecated)
            bucket = index.setdefault(key, [])
            for target_id in targets:
                if target_id not in bucket:
                    bucket.append(target_id)
    return index


def build_replaced_from_index(db: Database, deprecated_replacement_index: dict[str, list[str]]) -> dict[str, list[str]]:
    replaced_from: dict[str, list[str]] = {}
    for entity in db.all_languoids:
        own_codes = clean_list(
            [entity.bcp_47, entity.iso_639_1, entity.iso_639_2b, entity.iso_639_3, entity.iso_639_5, entity.glottocode]
        )
        targets: list[str] = []
        for code in own_codes:
            for target_id in deprecated_replacement_index.get(code.lower(), []):
                if target_id != entity.id and target_id not in targets:
                    targets.append(target_id)
        for target_id in targets:
            bucket = replaced_from.setdefault(target_id, [])
            if entity.id not in bucket:
                bucket.append(entity.id)
    return replaced_from


def relation_group(label: str, entities: list[Any]) -> dict[str, Any] | None:
    unique = {entity.id: entity for entity in entities}
    if label == "Family tree":
        items = []
        for entity in entities:
            if entity.id not in items:
                items.append(entity.id)
    else:
        items = sorted(
            unique,
            key=lambda entity_id: ((unique[entity_id].name or unique[entity_id].id).lower(), entity_id),
        )
    if not items:
        return None
    return {"l": label, "i": items}


def export_languoid_summary(entity: Languoid) -> dict[str, Any]:
    wikipedia = entity.wikipedia
    deprecated_codes = clean_list(
        [deprecated.code for deprecated in (entity.deprecated_codes or []) if deprecated.code]
    )
    identifiers = clean_list(
        [
            entity.bcp_47,
            entity.iso_639_1,
            entity.iso_639_2b,
            entity.iso_639_3,
            entity.iso_639_5,
            entity.glottocode,
            entity.wikidata_id,
            wikipedia.code if wikipedia else None,
            *deprecated_codes,
        ]
    )
    names = clean_list([entity.name, entity.endonym])
    search_terms = clean_list(
        [
            *names,
            *identifiers,
        ]
    )
    return {
        "t": "languoid",
        "n": entity.name or entity.bcp_47 or entity.iso_639_3 or entity.id,
        "s": " / ".join(clean_list([entity.bcp_47, entity.iso_639_3, entity.glottocode])),
        "q": " ".join(search_terms).lower(),
        "i": identifiers,
        "m": names,
        "d": deprecated_codes,
        "b": bucket_for(entity.id),
    }


def export_languoid_detail(
    db: Database,
    entity: Languoid,
    deprecated_replacement_index: dict[str, list[str]],
    replaced_from_index: dict[str, list[str]],
) -> dict[str, Any]:
    wikipedia = entity.wikipedia
    replaced_by: list[str] = []
    own_codes = clean_list(
        [entity.bcp_47, entity.iso_639_1, entity.iso_639_2b, entity.iso_639_3, entity.iso_639_5, entity.glottocode]
    )
    for code in own_codes:
        for target_id in deprecated_replacement_index.get(code.lower(), []):
            if target_id != entity.id and target_id not in replaced_by:
                replaced_by.append(target_id)
    return {
        "p": clean_none_dict(
            {
                "name": make_property(entity.name),
                "endonym": make_property(entity.endonym),
                "bcp_47": make_property(entity.bcp_47),
                "iso_639_1": make_property(entity.iso_639_1),
                "iso_639_2b": make_property(entity.iso_639_2b),
                "iso_639_3": make_property(entity.iso_639_3),
                "iso_639_5": make_property(entity.iso_639_5),
                "glottocode": make_property(entity.glottocode),
                "wikidata_id": make_property(entity.wikidata_id),
                "wikipedia_code": make_property(wikipedia.code if wikipedia else None),
                "wikipedia_url": make_property(wikipedia.url if wikipedia else None),
                "wikipedia_article_count": make_property(wikipedia.article_count if wikipedia else None),
                "wikipedia_active_users": make_property(wikipedia.active_users if wikipedia else None),
                "speaker_count": make_property(entity.speaker_count),
                "latitude": make_property(entity.latitude),
                "longitude": make_property(entity.longitude),
                "level": make_property(entity.level),
                "scope": make_property(map_label(entity.scope, SCOPE_LABELS)),
                "status": make_property(map_label(entity.status, STATUS_LABELS)),
                "endangerment_status": make_property(entity.endangerment_status),
                "description": make_property(entity.description),
                "id": make_property(entity.id),
            }
        ),
        "r": clean_none(
            [
                relation_group("Parent", [entity.parent] if entity.parent else []),
                relation_group("Children", entity.children),
                relation_group("Siblings", entity.siblings),
                relation_group("Family tree", entity.family_tree),
                relation_group("Scripts", entity.scripts),
                relation_group("Regions", entity.regions),
                relation_group("Macrolanguage", [entity.macrolanguage] if entity.macrolanguage else []),
                relation_group("Individual languages", entity.individual_languages),
            ]
        ),
        "deprecated": [
            clean_none_dict(
                {
                    "code": make_property(deprecated.code),
                    "code_type": make_property(
                        map_label(deprecated.code_type, CODE_TYPE_LABELS) if deprecated.code_type else None
                    ),
                    "reason": make_property(
                        map_label(deprecated.reason, DEPRECATION_REASON_LABELS) if deprecated.reason else None
                    ),
                    "name": make_property(deprecated.name),
                    "effective": make_property(deprecated.effective),
                    "remedy": make_property(deprecated.remedy),
                    "split_into": ", ".join(deprecated.split_into) if deprecated.split_into else None,
                    "target_ids": resolve_deprecated_targets(db, entity, deprecated),
                }
            )
            for deprecated in (entity.deprecated_codes or [])
            if deprecated.code
        ],
        "replaced_by": replaced_by,
        "replaced_from": replaced_from_index.get(entity.id, []),
    }


def export_script_summary(entity: Script) -> dict[str, Any]:
    identifiers = clean_list([entity.iso_15924])
    names = clean_list([entity.name, entity.full_name])
    return {
        "t": "script",
        "n": entity.name or entity.iso_15924 or entity.id,
        "s": " / ".join(clean_list([entity.iso_15924, entity.full_name])),
        "q": " ".join(clean_list([*names, *identifiers])).lower(),
        "i": identifiers,
        "m": names,
        "b": bucket_for(entity.id),
    }


def export_script_detail(entity: Script) -> dict[str, Any]:
    return {
        "p": clean_none_dict(
            {
                "name": make_property(entity.name),
                "full_name": make_property(entity.full_name),
                "iso_15924": make_property(entity.iso_15924),
                "is_historical": make_property(entity.is_historical),
                "languoid_count": make_property(entity.languoid_count),
                "id": make_property(entity.id),
            }
        ),
        "r": clean_none(
            [
                relation_group("Canonical languoids", entity.canonical_languoids),
                relation_group("Languoids", entity.languoids),
            ]
        ),
    }


def export_region_summary(entity: GeographicRegion) -> dict[str, Any]:
    identifiers = clean_list([entity.country_code, entity.subdivision_code])
    names = clean_list([entity.name, entity.official_name])
    return {
        "t": "region",
        "n": entity.name or entity.country_code or entity.id,
        "s": " / ".join(clean_list([entity.country_code, entity.subdivision_code])),
        "q": " ".join(clean_list([*names, *identifiers])).lower(),
        "i": identifiers,
        "m": names,
        "b": bucket_for(entity.id),
    }


def export_region_detail(entity: GeographicRegion) -> dict[str, Any]:
    return {
        "p": clean_none_dict(
            {
                "name": make_property(entity.name),
                "country_code": make_property(entity.country_code),
                "official_name": make_property(entity.official_name),
                "subdivision_code": make_property(entity.subdivision_code),
                "subdivision_type": make_property(entity.subdivision_type),
                "parent_country_code": make_property(entity.parent_country_code),
                "is_historical": make_property(entity.is_historical),
                "id": make_property(entity.id),
            }
        ),
        "r": clean_none(
            [
                relation_group("Parent region", [entity.parent_region] if entity.parent_region else []),
                relation_group("Child regions", entity.child_regions),
                relation_group("Subdivisions", entity.subdivisions),
                relation_group("Languoids", entity.languoids),
                relation_group("Scripts", entity.scripts),
            ]
        ),
    }


def write_script(path: Path, global_name: str, key: str | None, payload: Any) -> None:
    if key is None:
        text = f"window.{global_name} = {json.dumps(payload, ensure_ascii=False)};\n"
    else:
        text = (
            f"window.{global_name} = window.{global_name} || {{}};\n"
            f"window.{global_name}[{json.dumps(key)}] = {json.dumps(payload, ensure_ascii=False)};\n"
        )
    path.write_text(text, encoding="utf-8")


def export_sources_metadata() -> list[dict[str, str]]:
    sources = []
    for provider in SourceConfig.get_providers(SOURCES_DIR):
        meta = provider.metadata
        item = clean_none_dict(
            {
                "name": provider.name.title() if len(provider.name) > 4 else provider.name.upper(),
                "source_url": meta.source_url,
                "license": meta.license,
                "paper_url": meta.paper_url,
                "website_url": meta.website_url if meta.website_url != meta.source_url else None,
                "last_updated": meta._last_updated.strftime("%d-%m-%Y") if meta._last_updated else None,
                "notes": meta.notes,
            }
        )
        sources.append(item)
    return sorted(sources, key=lambda item: item["name"].lower())


def main() -> None:
    db = Database.load()
    sources = export_sources_metadata()

    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    if LEGACY_OUTPUT_PATH.exists():
        LEGACY_OUTPUT_PATH.unlink()
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    NAME_BUCKETS_DIR.mkdir(parents=True, exist_ok=True)

    summaries: dict[str, dict[str, str]] = {}
    buckets: dict[str, dict[str, Any]] = {f"{index:02x}": {} for index in range(BUCKET_COUNT)}
    name_buckets: dict[str, list[list[str]]] = {f"{index:02x}": [] for index in range(NAME_BUCKET_COUNT)}
    deprecated_replacement_index = build_deprecated_replacement_index(db)
    replaced_from_index = build_replaced_from_index(db, deprecated_replacement_index)

    for entity in db.all_languoids:
        summary = export_languoid_summary(entity)
        summaries[entity.id] = summary
        buckets[summary["b"]][entity.id] = export_languoid_detail(
            db, entity, deprecated_replacement_index, replaced_from_index
        )

    for entity in db.all_scripts:
        summary = export_script_summary(entity)
        summaries[entity.id] = summary
        buckets[summary["b"]][entity.id] = export_script_detail(entity)

    for entity in db.all_regions:
        summary = export_region_summary(entity)
        summaries[entity.id] = summary
        buckets[summary["b"]][entity.id] = export_region_detail(entity)

    if db.store.name_cache:
        for entity in db.all_languoids:
            names = db.store.name_cache.get(entity.id)
            if not names:
                continue
            seen_names = {value.lower() for value in clean_list([entity.name, entity.endonym])}
            for locale_id, name_data in names.items():
                name = make_property(name_data.name)
                if not name:
                    continue
                normalized = name.lower()
                if normalized in seen_names:
                    continue
                seen_names.add(normalized)
                name_buckets[name_bucket_for(name)].append([name, entity.id, locale_id])

    available_name_buckets: dict[str, int] = {}
    for bucket, payload in name_buckets.items():
        if not payload:
            continue
        payload.sort(key=lambda entry: (entry[0].lower(), entry[1], entry[2]))
        write_script(NAME_BUCKETS_DIR / f"{bucket}.js", "QQ_DEMO_NAME_BUCKETS", bucket, payload)
        available_name_buckets[bucket] = len(payload)

    write_script(
        DATA_DIR / "index.js",
        "QQ_DEMO_INDEX",
        None,
        {
            "meta": {
                "defaultId": "lang:006448",
                "counts": {
                    "languoids": len(db.all_languoids),
                    "scripts": len(db.all_scripts),
                    "regions": len(db.all_regions),
                    "entities": len(summaries),
                    "buckets": BUCKET_COUNT,
                    "nameBuckets": available_name_buckets,
                    "sources": sources,
                    "dbVersion": qq.__version__,
                },
            },
            "entities": summaries,
        },
    )

    for bucket, payload in buckets.items():
        write_script(CHUNKS_DIR / f"{bucket}.js", "QQ_DEMO_CHUNKS", bucket, payload)

    print(f"Wrote {DATA_DIR}")


if __name__ == "__main__":
    main()
