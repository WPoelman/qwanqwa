from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qq.data_model import ExternalResourceGroup, IdType
from qq.importers import (
    BaseImporter,
    ExternalResourceImporter,
    GlotscriptImporter,
    GlottologImporter,
    IANAImporter,
    LinguaMetaImporter,
    PycountryImporter,
    SILImporter,
    UnicodeImporter,
    WikidataIso6395Importer,
    WikipediaImporter,
)
from qq.sources.external_resource import ExternalResourceDefinition, ExternalResourceFileFormat
from qq.sources.providers import (
    FileDownloadSourceProvider,
    GitSourceProvider,
    HuggingFaceDatasetTagsSourceProvider,
    SourceProvider,
    UnicodeUCDSourceProvider,
    WikidataSparqlSourceProvider,
)


@dataclass(frozen=True)
class ImporterConfig:
    source_name: str
    importer_cls: type[BaseImporter]
    data_path_name: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)

    def resolve_data_path(self, sources_dir: Path) -> Path:
        return sources_dir / (self.data_path_name or self.source_name)


class SourceConfig:
    """
    Sources are the 'raw' data that gets parsed into the qq graph database
    by an Importer.

    This config is used to import the sources in a consistent way.
    """

    def __init__(self, sources_dir: Path):
        self.sources_dir = sources_dir

    @staticmethod
    def get_providers_as_dict(sources_dir: Path) -> dict[str, SourceProvider]:
        """Get dict with name: Provider mapping."""
        return {s.name: s for s in SourceConfig.get_providers(sources_dir)}

    @staticmethod
    def get_providers(sources_dir: Path) -> list[SourceProvider]:
        """
        Get all configured source providers.

        To add a new source:
        1. Add it to this list
        2. Specify the provider type
        3. The importer will be automatically used during rebuild
           Do make sure to add an "Importer" to actually extract info from
           the source during a rebuild. See below.
           For external resources, matching can also be done purely on a column
           in a csv of which identifier to select and which external link can be
           made. For example:
                Liking to Glottolog can be done through glottocodes and
                by adding it to the end of the URL, like this:

                https://glottolog.org/resource/languoid/id/drav1251
        """
        return [
            GitSourceProvider(
                name="linguameta",
                sources_dir=sources_dir,
                source_url="https://github.com/google-research/url-nlp.git",
                branch="main",
                subpath="linguameta",
                license="CC BY-SA 4.0",
                paper_url="https://aclanthology.org/2024.lrec-main.921/",
                website_url="https://github.com/google-research/url-nlp/tree/main/linguameta",
                notes=(
                    "Individual sources documented in "
                    "[LinguaMeta README](https://github.com/google-research/url-nlp/blob/main/linguameta/README.md)"
                ),
            ),
            GitSourceProvider(
                name="glottolog",
                sources_dir=sources_dir,
                source_url="https://github.com/glottolog/glottolog-cldf.git",
                branch="master",
                subpath="cldf",
                license="CC BY 4.0",
                website_url="https://glottolog.org/",
            ),
            WikidataSparqlSourceProvider(
                name="wikidata_iso6395",
                display_name="Wikidata ISO 639-5",
                sources_dir=sources_dir,
                source_url="https://query.wikidata.org/sparql",
                filename="iso6395.json",
                query=(
                    "SELECT ?item ?itemLabel ?iso6395 ?glottocode WHERE { "
                    "?item wdt:P1798 ?iso6395 . "
                    "OPTIONAL { ?item wdt:P1394 ?glottocode . } "
                    'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } '
                    "} ORDER BY ?iso6395"
                ),
                cache_duration_hours=24 * 30,
                license="CC0",
                website_url="https://www.wikidata.org/",
                notes="SPARQL query for ISO 639-5 codes and Glottolog identifiers, used to merge family codes.",
            ),
            WikidataSparqlSourceProvider(
                name="wikidata_enwiki_sitelinks",
                display_name="Wikidata English Wikipedia sitelinks",
                sources_dir=sources_dir,
                source_url="https://query.wikidata.org/sparql",
                filename="sitelinks.json",
                query=(
                    "SELECT DISTINCT ?item ?article ?articleTitle WHERE { "
                    "VALUES ?identifierProperty { wdt:P218 wdt:P219 wdt:P220 wdt:P305 wdt:P1394 wdt:P1798 } "
                    "?item ?identifierProperty ?identifier . "
                    "?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?articleTitle . "
                    "} ORDER BY ?item"
                ),
                cache_duration_hours=24 * 30,
                license="CC0",
                website_url="https://www.wikidata.org/",
                notes="SPARQL query for English Wikipedia sitelinks on Wikidata language items.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="English Wikipedia",
                        group=ExternalResourceGroup.REFERENCE,
                        url_template="{code}",
                        source_name="wikidata_enwiki_sitelinks",
                        filename="sitelinks.json",
                        file_format=ExternalResourceFileFormat.WIKIDATA_SPARQL_BINDINGS_JSON,
                        match_column="item",
                        match_id_type=IdType.WIKIDATA_ID,
                        code_column="articleTitle",
                        url_column="article",
                        unique_per_languoid=True,
                    )
                ],
            ),
            GitSourceProvider(
                name="glotscript",
                sources_dir=sources_dir,
                source_url="https://github.com/cisnlp/glotscript",
                branch="main",
                subpath="metadata",
                license="CC BY-SA 4.0",
                paper_url="https://aclanthology.org/2024.lrec-main.687/",
                website_url="https://github.com/cisnlp/glotscript",
                notes=(
                    "Individual sources documented in "
                    "[GlotScript README](https://github.com/cisnlp/GlotScript/blob/main/metadata/README.md)"
                ),
            ),
            # TODO: maybe get rid of pycountry and just use Debian source directly?
            GitSourceProvider(
                name="pycountry",
                sources_dir=sources_dir,
                source_url="https://github.com/pycountry/pycountry",
                branch="main",
                subpath="src/pycountry/databases",
                license="LGPL-2.1 or later",
                notes="Builds on Debian iso-codes [project](https://salsa.debian.org/iso-codes-team/iso-codes)",
            ),
            UnicodeUCDSourceProvider(
                name="unicode_ucd",
                display_name="Unicode Character Database",
                sources_dir=sources_dir,
                source_url="https://www.unicode.org/Public/UCD/latest/ucd/",
                cache_duration_hours=24 * 30,
                license="UNICODE LICENSE V3",
                website_url="https://www.unicode.org/ucd/",
                notes="Unicode Scripts.txt and PropertyValueAliases.txt used to add script code point ranges.",
            ),
            FileDownloadSourceProvider(
                name="wikipedia",
                sources_dir=sources_dir,
                source_url="https://wikistats.wmcloud.org/api.php?action=dump&table=wikipedias&format=csv",
                filename="wikipedia.csv",
                cache_duration_hours=24 * 7,  # Cache for 1 week
                license="CC BY-SA 4.0",
                website_url="https://wikistats.wmcloud.org/",
                notes="Wikipedia edition statistics (article counts, active users) from Wikistats (Wikimedia)",
            ),
            FileDownloadSourceProvider(
                name="sil",
                sources_dir=sources_dir,
                source_url="https://iso639-3.sil.org/sites/iso639-3/files/downloads/iso-639-3_Retirements.tab",
                filename="iso_639_3_retirements.tab",
                cache_duration_hours=24 * 30,  # Cache for one month
                license="Custom (free use)",
                website_url="https://iso639-3.sil.org/code_tables/download_tables",
                notes="ISO 639-3 retired code mappings maintained by SIL International",
            ),
            FileDownloadSourceProvider(
                name="iana",
                sources_dir=sources_dir,
                source_url="https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry",
                filename="language-subtag-registry",
                cache_duration_hours=24 * 30,  # Cache for one month
                license="Public (Internet Standard)",
                website_url="https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry",
                notes="IANA Language Subtag Registry (BCP 47 / RFC 5646): deprecated language subtag mappings",
            ),
            FileDownloadSourceProvider(
                name="grambank",
                display_name="Grambank",
                sources_dir=sources_dir,
                source_url="https://raw.githubusercontent.com/grambank/grambank/master/cldf/languages.csv",
                filename="languages.csv",
                cache_duration_hours=24 * 30,
                license="CC BY 4.0",
                website_url="https://grambank.clld.org/",
                notes="Language table used to add exact Grambank resource links by Glottocode.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="Grambank",
                        group=ExternalResourceGroup.TYPOLOGY,
                        url_template="https://grambank.clld.org/languages/{code}",
                        source_name="grambank",
                        filename="languages.csv",
                        match_column="Glottocode",
                        match_id_type=IdType.GLOTTOCODE,
                        code_column="ID",
                    )
                ],
            ),
            FileDownloadSourceProvider(
                name="phoible",
                display_name="PHOIBLE",
                sources_dir=sources_dir,
                source_url="https://raw.githubusercontent.com/cldf-datasets/phoible/master/cldf/languages.csv",
                filename="languages.csv",
                cache_duration_hours=24 * 30,
                license="CC BY-SA 3.0",
                website_url="https://phoible.org/",
                notes="Language table used to add exact PHOIBLE resource links by Glottocode.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="PHOIBLE",
                        group=ExternalResourceGroup.TYPOLOGY,
                        url_template="https://phoible.org/languages/{code}",
                        source_name="phoible",
                        filename="languages.csv",
                        match_column="Glottocode",
                        match_id_type=IdType.GLOTTOCODE,
                        code_column="ID",
                    )
                ],
            ),
            FileDownloadSourceProvider(
                name="wals",
                display_name="WALS",
                sources_dir=sources_dir,
                source_url="https://raw.githubusercontent.com/cldf-datasets/wals/master/cldf/languages.csv",
                filename="languages.csv",
                cache_duration_hours=24 * 30,
                license="CC BY 4.0",
                website_url="https://wals.info/",
                notes="Language table used to add exact WALS resource links by Glottocode and WALS code.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="WALS",
                        group=ExternalResourceGroup.TYPOLOGY,
                        url_template="https://wals.info/languoid/lect/wals_code_{code}",
                        source_name="wals",
                        filename="languages.csv",
                        match_column="Glottocode",
                        match_id_type=IdType.GLOTTOCODE,
                        code_column="ID",
                        unique_per_languoid=True,
                    )
                ],
            ),
            FileDownloadSourceProvider(
                name="apics",
                display_name="APiCS",
                sources_dir=sources_dir,
                source_url="https://raw.githubusercontent.com/cldf-datasets/apics/master/cldf/languages.csv",
                filename="languages.csv",
                cache_duration_hours=24 * 30,
                license="CC BY 3.0",
                website_url="https://apics-online.info/",
                notes="Language table used to add exact APiCS resource links by Glottocode and APiCS language ID.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="APiCS",
                        group=ExternalResourceGroup.TYPOLOGY,
                        url_template="https://apics-online.info/languages/{code}",
                        source_name="apics",
                        filename="languages.csv",
                        match_column="Glottocode",
                        match_id_type=IdType.GLOTTOCODE,
                        code_column="ID",
                    )
                ],
            ),
            FileDownloadSourceProvider(
                name="ewave",
                display_name="eWAVE",
                sources_dir=sources_dir,
                source_url="https://raw.githubusercontent.com/cldf-datasets/ewave/master/cldf/languages.csv",
                filename="languages.csv",
                cache_duration_hours=24 * 30,
                license="CC BY 3.0",
                website_url="https://ewave-atlas.org/",
                notes="Language table used to add exact eWAVE resource links by Glottocode and eWAVE language ID.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="eWAVE",
                        group=ExternalResourceGroup.TYPOLOGY,
                        url_template="https://ewave-atlas.org/languages/{code}",
                        source_name="ewave",
                        filename="languages.csv",
                        match_column="Glottocode",
                        match_id_type=IdType.GLOTTOCODE,
                        code_column="ID",
                    )
                ],
            ),
            FileDownloadSourceProvider(
                name="afbo",
                display_name="AfBo",
                sources_dir=sources_dir,
                source_url="https://raw.githubusercontent.com/cldf-datasets/afbo/master/cldf/languages.csv",
                filename="languages.csv",
                cache_duration_hours=24 * 30,
                license="CC BY 4.0",
                website_url="https://afbo.info/",
                notes="Language table used to add exact AfBo resource links by Glottocode and AfBo language ID.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="AfBo",
                        group=ExternalResourceGroup.TYPOLOGY,
                        url_template="https://afbo.info/languages/{code}",
                        source_name="afbo",
                        filename="languages.csv",
                        match_column="Glottocode",
                        match_id_type=IdType.GLOTTOCODE,
                        code_column="ID",
                    )
                ],
            ),
            FileDownloadSourceProvider(
                name="sails",
                display_name="SAILS",
                sources_dir=sources_dir,
                source_url="https://raw.githubusercontent.com/cldf-datasets/sails/master/cldf/languages.csv",
                filename="languages.csv",
                cache_duration_hours=24 * 30,
                license="CC BY-NC-ND 2.0 DE",
                website_url="https://sails.clld.org/",
                notes="Language table used to add exact SAILS resource links by Glottocode and SAILS language ID.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="SAILS",
                        group=ExternalResourceGroup.TYPOLOGY,
                        url_template="https://sails.clld.org/languages/{code}",
                        source_name="sails",
                        filename="languages.csv",
                        match_column="Glottocode",
                        match_id_type=IdType.GLOTTOCODE,
                        code_column="ID",
                    )
                ],
            ),
            HuggingFaceDatasetTagsSourceProvider(
                name="huggingface_dataset_tags",
                display_name="Hugging Face Datasets",
                sources_dir=sources_dir,
                source_url="https://huggingface.co/api/datasets?limit=1000&expand=tags",
                filename="tags.json",
                cache_duration_hours=24,
                license="See Hugging Face datasets themselves.",
                website_url="https://huggingface.co/datasets",
                notes=(
                    "Dataset tag metadata used to add Hugging Face links only for language tags that occur on the Hub."
                ),
                external_resources=[
                    ExternalResourceDefinition(
                        label="Hugging Face",
                        group=ExternalResourceGroup.DATASETS,
                        url_template="https://huggingface.co/datasets?filter=language:{code}",
                        source_name="huggingface_dataset_tags",
                        filename="tags.json",
                        file_format=ExternalResourceFileFormat.HUGGINGFACE_TAGS_JSON,
                        match_column="language",
                        match_id_type=id_type,
                    )
                    for id_type in (
                        IdType.BCP_47,
                        IdType.ISO_639_1,
                        IdType.ISO_639_3,
                        IdType.ISO_639_2T,
                        IdType.ISO_639_2B,
                        IdType.ISO_639_5,
                    )
                ],
            ),
            FileDownloadSourceProvider(
                name="universal_dependencies",
                display_name="Universal Dependencies",
                sources_dir=sources_dir,
                source_url=(
                    "https://lindat.mff.cuni.cz/repository/server/api/core/items/7fbbbd99-ae2d-4b91-8318-d996dbe34cbc"
                ),
                filename="item.json",
                cache_duration_hours=24 * 7,
                license="Universal Dependencies v2.18 License Agreement",
                website_url="https://universaldependencies.org/",
                notes="LINDAT item metadata used to add Universal Dependencies links by ISO 639-3 code.",
                external_resources=[
                    ExternalResourceDefinition(
                        label="Universal Dependencies",
                        group=ExternalResourceGroup.DATASETS,
                        url_template="http://hdl.handle.net/11234/1-6149",
                        source_name="universal_dependencies",
                        filename="item.json",
                        file_format=ExternalResourceFileFormat.DSPACE_ITEM_JSON,
                        match_column="dc.language.iso",
                        match_id_type=IdType.ISO_639_3,
                    )
                ],
            ),
        ]

    # TODO: not a fan of this, maybe the external resouces should be attached differently or in a different location.
    #       it works for now, but a refactor would be good.
    @staticmethod
    def get_external_resource_definitions(sources_dir: Path | None = None) -> list[ExternalResourceDefinition]:
        definitions = [
            ExternalResourceDefinition(
                label="Glottolog",
                group=ExternalResourceGroup.REFERENCE,
                url_template="https://glottolog.org/resource/languoid/id/{code}",
                match_column="glottocode",
                match_id_type=IdType.GLOTTOCODE,
            ),
            ExternalResourceDefinition(
                label="Wikidata",
                group=ExternalResourceGroup.REFERENCE,
                url_template="https://www.wikidata.org/wiki/{code}",
                match_column="wikidata_id",
                match_id_type=IdType.WIKIDATA_ID,
            ),
        ]

        if sources_dir is not None:
            for provider in SourceConfig.get_providers(sources_dir):
                definitions.extend(provider.external_resources)
        return definitions

    def get_importers(self) -> list[ImporterConfig]:
        """
        Each name of a SourceProvider is associated with one or more Importers.
        These importers extract information from the source.
        Currently it's 1-1, but this could change in the future.

        Ordering is significant: importers run in this order during a build,
        and source priority in merge conflicts follows this sequence.
        """
        # TODO: in the future this should prob be a dict[str, [tuple[importer], ...]]
        return [
            ImporterConfig("linguameta", LinguaMetaImporter),
            ImporterConfig("glottolog", GlottologImporter),
            ImporterConfig("wikidata_iso6395", WikidataIso6395Importer, data_path_name="wikidata_iso6395/iso6395.json"),
            ImporterConfig("glotscript", GlotscriptImporter),
            ImporterConfig("pycountry", PycountryImporter),
            ImporterConfig("unicode_ucd", UnicodeImporter),
            ImporterConfig("wikipedia", WikipediaImporter),
            ImporterConfig("sil", SILImporter),
            ImporterConfig("iana", IANAImporter),
            ImporterConfig(
                "external_resources",
                ExternalResourceImporter,
                data_path_name=".",
                kwargs={"definitions": SourceConfig.get_external_resource_definitions(self.sources_dir)},
            ),
        ]
