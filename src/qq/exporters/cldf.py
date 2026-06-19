from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from qq.exporters.context import ExportContext
from qq.interface import GeographicRegion, Languoid, Script

TERMS = "http://cldf.clld.org/v1.0/terms.rdf#"
SCRIPT_COLUMNS = [
    "ID",
    "QQ_ID",
    "Name",
    "ISO_15924",
    "Script_Type",
    "Family",
    "Sample",
    "Is_Historical",
    "Unicode_Alias",
    "Unicode_Ranges",
    "Unicode_Character_Count",
]
REGION_COLUMNS = [
    "ID",
    "QQ_ID",
    "Name",
    "Country_Code",
    "Official_Name",
    "Subdivision_Code",
    "Subdivision_Type",
    "Parent_Country_Code",
    "Is_Historical",
]
NAME_COLUMNS = ["ID", "Languoid_ID", "Locale_Languoid_ID", "Locale_BCP_47", "Name", "Is_Canonical", "Source_ID"]
IDENTIFIER_COLUMNS = [
    "ID",
    "Entity_Language_ID",
    "Entity_Script_ID",
    "Entity_Region_ID",
    "Entity_QQ_ID",
    "System",
    "Value",
    "Is_Deprecated",
    "Deprecation_Reason",
]
RESOURCE_COLUMNS = [
    "ID",
    "Languoid_ID",
    "Label",
    "Group",
    "URL",
    "Code",
    "Count",
    "Source_ID",
    "Source_File",
    "Match_Column",
    "Match_ID_Type",
    "Match_Value",
]
RELATION_COLUMNS = [
    "ID",
    "Source_Language_ID",
    "Source_Script_ID",
    "Source_Region_ID",
    "Target_Language_ID",
    "Target_Script_ID",
    "Target_Region_ID",
    "Source_QQ_ID",
    "Target_QQ_ID",
    "Relation_Type",
    "Metadata_JSON",
]
PROVENANCE_COLUMNS = [
    "ID",
    "Entity_Language_ID",
    "Entity_Script_ID",
    "Entity_Region_ID",
    "Target_Language_ID",
    "Target_Script_ID",
    "Target_Region_ID",
    "Entity_QQ_ID",
    "Target_QQ_ID",
    "Kind",
    "Field",
    "Relation_Type",
    "Source_ID",
    "Role",
    "Priority",
    "Merge_Strategy",
    "Candidate_Value_JSON",
    "Metadata_JSON",
]
SOURCE_COLUMNS = [
    "ID",
    "Name",
    "Source_URL",
    "Website_URL",
    "Version",
    "Checksum",
    "License",
    "Paper_URL",
    "Last_Updated",
    "Last_Checked",
    "Notes",
]


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def json_value(value: Any) -> str:
    def default(item):
        if isinstance(item, Enum):
            return item.value
        if is_dataclass(item):
            return asdict(item)
        return str(item)

    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=default)


def scalar(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def column(name: str, datatype: str = "string", term: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "datatype": datatype}
    if term:
        result["propertyUrl"] = TERMS + term
    return result


def foreign_key(local: str, resource: str, remote: str = "ID") -> dict[str, Any]:
    return {
        "columnReference": [local],
        "reference": {"resource": resource, "columnReference": [remote]},
    }


class CLDFExporter:
    name = "cldf"

    def export(self, context: ExportContext, output_path: Path) -> Path:
        try:
            from pycldf import Dataset  # type: ignore[unresolved-import]
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError("The CLDF exporter requires pycldf; install qwanqwa[cldf]") from exc

        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{output_path.name}-", dir=output_path.parent))
        try:
            metadata_path = self._write_package(context, temporary)
            dataset = Dataset.from_metadata(metadata_path)
            if not dataset.validate(log=None):
                raise ValueError("Generated CLDF dataset did not validate")
            self._write_manifest(temporary)
            self._replace_directory(temporary, output_path)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        return output_path

    def _write_package(self, context: ExportContext, root: Path) -> Path:
        store = context.store
        languages = sorted(store.all_of_type(Languoid), key=lambda entity: safe_id(entity.id))
        scripts = sorted(store.all_of_type(Script), key=lambda entity: safe_id(entity.id))
        regions = sorted(store.all_of_type(GeographicRegion), key=lambda entity: safe_id(entity.id))

        language_rows = [
            {
                "ID": safe_id(item.id),
                "Name": item.name,
                "Glottocode": item.glottocode,
                "ISO639P3code": item.iso_639_3,
                "Latitude": item.latitude,
                "Longitude": item.longitude,
                "QQ_ID": item.id,
                "BCP_47": item.bcp_47,
                "ISO_639_1": item.iso_639_1,
                "ISO_639_2B": item.iso_639_2b,
                "ISO_639_5": item.iso_639_5,
                "Wikidata_ID": item.wikidata_id,
                "Endonym": item.endonym,
                "Speaker_Count": item.speaker_count,
                "Level": scalar(item.level),
                "Scope": scalar(item.scope),
                "Status": scalar(item.status),
                "Endangerment_Status": scalar(item.endangerment_status),
                "Description": item.description,
            }
            for item in languages
        ]
        script_rows = [
            {
                "ID": safe_id(item.id),
                "QQ_ID": item.id,
                "Name": item.name,
                "ISO_15924": item.iso_15924,
                "Script_Type": item.script_type,
                "Family": item.family,
                "Sample": item.sample,
                "Is_Historical": item.is_historical,
                "Unicode_Alias": item.unicode_alias,
                "Unicode_Ranges": json_value(item.unicode_ranges),
                "Unicode_Character_Count": item.unicode_character_count,
            }
            for item in scripts
        ]
        region_rows = [
            {
                "ID": safe_id(item.id),
                "QQ_ID": item.id,
                "Name": item.name,
                "Country_Code": item.country_code,
                "Official_Name": item.official_name,
                "Subdivision_Code": item.subdivision_code,
                "Subdivision_Type": item.subdivision_type,
                "Parent_Country_Code": item.parent_country_code,
                "Is_Historical": item.is_historical,
            }
            for item in regions
        ]
        name_rows = self._name_rows(context)
        identifier_rows = self._identifier_rows(context)
        resource_rows = self._resource_rows(languages)
        relation_rows = self._relation_rows(context)
        source_rows = self._source_rows(context)
        provenance_rows = self._provenance_rows(context)

        tables = [
            self._table(
                "languages.csv",
                language_rows,
                [
                    column("ID", term="id"),
                    column("Name", term="name"),
                    column("Glottocode", term="glottocode"),
                    column("ISO639P3code", term="iso639P3code"),
                    column("Latitude", "decimal", "latitude"),
                    column("Longitude", "decimal", "longitude"),
                    *(
                        [
                            column(name)
                            for name in language_rows[0]
                            if name not in {"ID", "Name", "Glottocode", "ISO639P3code", "Latitude", "Longitude"}
                        ]
                        if language_rows
                        else []
                    ),
                ],
                component="LanguageTable",
            ),
            self._table("scripts.csv", script_rows, self._columns(script_rows, SCRIPT_COLUMNS)),
            self._table("regions.csv", region_rows, self._columns(region_rows, REGION_COLUMNS)),
            self._table(
                "names.csv",
                name_rows,
                self._columns(name_rows, NAME_COLUMNS),
                foreign_keys=[
                    foreign_key("Languoid_ID", "languages.csv"),
                    foreign_key("Locale_Languoid_ID", "languages.csv"),
                    foreign_key("Source_ID", "sources.csv"),
                ],
            ),
            self._table(
                "identifiers.csv",
                identifier_rows,
                self._columns(identifier_rows, IDENTIFIER_COLUMNS),
                foreign_keys=foreign_key_set("Entity", ["languages.csv", "scripts.csv", "regions.csv"]),
            ),
            self._table(
                "resources.csv",
                resource_rows,
                self._columns(resource_rows, RESOURCE_COLUMNS),
                foreign_keys=[
                    foreign_key("Languoid_ID", "languages.csv"),
                    foreign_key("Source_ID", "sources.csv"),
                ],
            ),
            self._table(
                "relations.csv",
                relation_rows,
                self._columns(relation_rows, RELATION_COLUMNS),
                foreign_keys=[
                    *foreign_key_set("Source", ["languages.csv", "scripts.csv", "regions.csv"]),
                    *foreign_key_set("Target", ["languages.csv", "scripts.csv", "regions.csv"]),
                ],
            ),
            self._table(
                "provenance.csv",
                provenance_rows,
                self._columns(provenance_rows, PROVENANCE_COLUMNS),
                foreign_keys=[
                    foreign_key("Source_ID", "sources.csv"),
                    *foreign_key_set("Entity", ["languages.csv", "scripts.csv", "regions.csv"]),
                    *foreign_key_set("Target", ["languages.csv", "scripts.csv", "regions.csv"]),
                ],
            ),
            self._table("sources.csv", source_rows, self._columns(source_rows, SOURCE_COLUMNS)),
        ]
        for table, rows in zip(
            tables,
            [
                language_rows,
                script_rows,
                region_rows,
                name_rows,
                identifier_rows,
                resource_rows,
                relation_rows,
                provenance_rows,
                source_rows,
            ],
        ):
            self._write_csv(root / table["url"], rows, [item["name"] for item in table["tableSchema"]["columns"]])

        metadata = {
            "dc:conformsTo": TERMS + "Generic",
            "dc:title": "Qwanqwa unified language metadata",
            "dc:creator": "Wessel Poelman",
            "dc:license": "https://creativecommons.org/licenses/by-sa/4.0/",
            "dc:homepage": "https://github.com/WPoelman/qwanqwa",
            "dc:accessURL": "https://github.com/WPoelman/qwanqwa",
            "dc:bibliographicCitation": f"Qwanqwa {context.qq_version}",
            "dc:accessRights": "public",
            "dc:version": context.qq_version,
            "tables": tables,
        }
        metadata_path = root / "cldf-metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        (root / "README.md").write_text(
            "# Qwanqwa CLDF export\n\n"
            "This Generic CLDF dataset combines the standard LanguageTable with CSVW tables "
            "for scripts, regions, names, identifiers, resources, graph relations, and provenance.\n\n"
            "Internal QQ identifiers are retained in `QQ_ID`; CLDF-safe primary keys replace `:` with `_`. "
            "Structured metadata is encoded as documented JSON strings.\n"
        )
        license_source = Path(__file__).resolve().parents[3] / "LICENSE_DATA"
        shutil.copy2(license_source, root / "LICENSE")
        (root / "SOURCES.md").write_text(self._source_document(context))
        return metadata_path

    def _table(self, filename, rows, columns, component=None, foreign_keys=None):
        result = {
            "url": filename,
            "tableSchema": {"columns": columns, "primaryKey": ["ID"]},
        }
        if component:
            result["dc:conformsTo"] = TERMS + component
        if foreign_keys:
            result["tableSchema"]["foreignKeys"] = foreign_keys
        return result

    def _columns(self, rows, names):
        types = {}
        for name in names:
            values = [row.get(name) for row in rows if row.get(name) is not None]
            datatype = "string"
            if values and all(isinstance(value, bool) for value in values):
                datatype = "boolean"
            elif values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
                datatype = "integer"
            elif values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
                datatype = "decimal"
            types[name] = datatype
        return [column(name, types[name]) for name in names]

    def _name_rows(self, context):
        rows = []
        index = 0
        for entity_id, entries in sorted(context.names.items()):
            for entry in sorted(entries, key=lambda item: (item.name, item.locale_id or "", item.bcp_47_code or "")):
                index += 1
                rows.append(
                    {
                        "ID": f"name_{index:08d}",
                        "Languoid_ID": safe_id(entity_id),
                        "Locale_Languoid_ID": safe_id(entry.locale_id) if entry.locale_id else None,
                        "Locale_BCP_47": entry.bcp_47_code,
                        "Name": entry.name,
                        "Is_Canonical": entry.is_canonical,
                        "Source_ID": safe_id(entry.source_name) if entry.source_name else None,
                    }
                )
        return rows

    def _identifier_rows(self, context):
        rows = []
        for canonical_id, identity in sorted(context.resolver._identities.items()):
            for id_type, value in sorted(identity.identifiers.items(), key=lambda item: item[0].value):
                rows.append(self._identifier_row(canonical_id, id_type.value, value, False, None))
        for script in sorted(context.store.all_of_type(Script), key=lambda item: item.id):
            if script.iso_15924:
                rows.append(self._identifier_row(script.id, "iso_15924", script.iso_15924, False, None))
        for region in sorted(context.store.all_of_type(GeographicRegion), key=lambda item: item.id):
            for system, value in (("iso_3166_1", region.country_code), ("iso_3166_2", region.subdivision_code)):
                if value:
                    rows.append(self._identifier_row(region.id, system, value, False, None))
        for (id_type, value), reason in sorted(
            context.resolver._deprecated_codes.items(), key=lambda item: (item[0][0].value, item[0][1])
        ):
            target = context.resolver._id_to_canonical.get((id_type, value))
            if target:
                rows.append(self._identifier_row(target, id_type.value, value, True, reason))
        rows.sort(key=lambda row: (row["Entity_QQ_ID"], row["System"], row["Value"], row["Is_Deprecated"]))
        for index, row in enumerate(rows, 1):
            row["ID"] = f"identifier_{index:08d}"
        return rows

    def _identifier_row(self, entity_id, system, value, deprecated, reason):
        result = {
            "ID": "",
            **typed_entity_columns("Entity", entity_id),
            "Entity_QQ_ID": entity_id,
            "System": system,
            "Value": value,
            "Is_Deprecated": deprecated,
            "Deprecation_Reason": reason,
        }
        return result

    def _resource_rows(self, languages):
        rows = []
        for language in languages:
            for resource in language.external_resources:
                rows.append(
                    {
                        "ID": "",
                        "Languoid_ID": safe_id(language.id),
                        "Label": resource.label,
                        "Group": resource.group.value,
                        "URL": resource.url,
                        "Code": resource.code,
                        "Count": resource.count,
                        "Source_ID": safe_id(resource.source_name) if resource.source_name else None,
                        "Source_File": resource.source_file,
                        "Match_Column": resource.match_column,
                        "Match_ID_Type": scalar(resource.match_id_type),
                        "Match_Value": resource.match_value,
                    }
                )
        rows.sort(key=lambda row: (row["Languoid_ID"], row["Group"], row["Label"], row["URL"]))
        for index, row in enumerate(rows, 1):
            row["ID"] = f"resource_{index:08d}"
        return rows

    def _relation_rows(self, context):
        rows = []
        for entity_id, entity in sorted(context.store._entities.items()):
            for relation_type, relations in sorted(entity._relations.items(), key=lambda item: item[0].value):
                for relation in sorted(relations, key=lambda item: (item.target_id, json_value(item.metadata))):
                    rows.append(
                        {
                            "ID": "",
                            **typed_entity_columns("Source", entity_id),
                            **typed_entity_columns("Target", relation.target_id),
                            "Source_QQ_ID": entity_id,
                            "Target_QQ_ID": relation.target_id,
                            "Relation_Type": relation_type.value,
                            "Metadata_JSON": json_value(relation.metadata),
                        }
                    )
        for index, row in enumerate(rows, 1):
            row["ID"] = f"relation_{index:08d}"
        return rows

    def _source_rows(self, context):
        names = set(context.source_metadata)
        names.update(record.source_name for record in context.provenance)
        names.update(entry.source_name for entries in context.names.values() for entry in entries if entry.source_name)
        names.update(
            resource.source_name
            for language in context.store.all_of_type(Languoid)
            for resource in language.external_resources
            if resource.source_name
        )
        rows = []
        for name in sorted(names):
            metadata = context.source_metadata.get(name, {})
            rows.append(
                {
                    "ID": safe_id(name),
                    "Name": metadata.get("display_name") or metadata.get("name") or name,
                    "Source_URL": metadata.get("source_url"),
                    "Website_URL": metadata.get("website_url"),
                    "Version": metadata.get("version"),
                    "Checksum": metadata.get("checksum"),
                    "License": metadata.get("license"),
                    "Paper_URL": metadata.get("paper_url"),
                    "Last_Updated": metadata.get("last_updated"),
                    "Last_Checked": metadata.get("last_checked"),
                    "Notes": metadata.get("notes"),
                }
            )
        return rows

    def _provenance_rows(self, context):
        rows = []
        records = sorted(
            context.provenance,
            key=lambda item: (
                item.entity_id,
                item.kind,
                item.field_name or "",
                item.relation_type or "",
                item.target_id or "",
                item.source_name,
                item.role,
            ),
        )
        for index, record in enumerate(records, 1):
            rows.append(
                {
                    "ID": f"provenance_{index:08d}",
                    **typed_entity_columns("Entity", record.entity_id),
                    **typed_entity_columns("Target", record.target_id),
                    "Entity_QQ_ID": record.entity_id,
                    "Target_QQ_ID": record.target_id,
                    "Kind": record.kind,
                    "Field": record.field_name,
                    "Relation_Type": record.relation_type,
                    "Source_ID": safe_id(record.source_name),
                    "Role": record.role,
                    "Priority": record.priority,
                    "Merge_Strategy": record.strategy,
                    "Candidate_Value_JSON": json_value(record.value) if record.value is not None else None,
                    "Metadata_JSON": json_value(record.metadata) if record.metadata is not None else None,
                }
            )
        return rows

    def _write_csv(self, path, rows, fieldnames):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(
                {
                    key: ("true" if value else "false") if isinstance(value, bool) else value
                    for key, value in row.items()
                }
                for row in rows
            )

    def _source_document(self, context):
        lines = ["# Source attribution", ""]
        for row in self._source_rows(context):
            lines.append(f"## {row['Name']}")
            lines.append("")
            lines.append(f"- License: {row['License'] or 'Not specified'}")
            if row["Source_URL"]:
                lines.append(f"- Source: {row['Source_URL']}")
            if row["Paper_URL"]:
                lines.append(f"- Paper: {row['Paper_URL']}")
            if row["Notes"]:
                lines.append(f"- Notes: {row['Notes']}")
            lines.append("")
        return "\n".join(lines)

    def _write_manifest(self, root):
        lines = []
        for path in sorted(root.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.name != "SHA256SUMS":
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                lines.append(f"{digest}  {path.name}")
        (root / "SHA256SUMS").write_text("\n".join(lines) + "\n")

    def _replace_directory(self, source, destination):
        backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(source, destination)
        except Exception:
            if backup.exists():
                os.replace(backup, destination)
            raise
        shutil.rmtree(backup, ignore_errors=True)


def entity_table(entity_id: str | None) -> str | None:
    if not entity_id:
        return None
    if entity_id.startswith("lang:"):
        return "Language"
    if entity_id.startswith("script:"):
        return "Script"
    if entity_id.startswith("region:"):
        return "Region"
    return None


def typed_entity_columns(prefix: str, entity_id: str | None) -> dict[str, str | None]:
    kind = entity_table(entity_id)
    safe = safe_id(entity_id) if entity_id is not None else None
    return {
        f"{prefix}_Language_ID": safe if kind == "Language" else None,
        f"{prefix}_Script_ID": safe if kind == "Script" else None,
        f"{prefix}_Region_ID": safe if kind == "Region" else None,
    }


def foreign_key_set(prefix: str, resources: list[str]) -> list[dict[str, Any]]:
    kinds = ("Language", "Script", "Region")
    return [foreign_key(f"{prefix}_{kind}_ID", resource) for kind, resource in zip(kinds, resources)]
