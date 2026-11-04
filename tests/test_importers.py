"""Tests for all data importers using mock fixture data."""

from pathlib import Path

import pytest

from qq.data_model import (
    DeprecationReason,
    EndangermentStatus,
    IdType,
    LanguageScope,
    LanguageStatus,
    LanguoidLevel,
    RelationType,
)
from qq.data_model import DataSource
from qq.importers.base_importer import BaseImporter, EntitySet
from qq.importers.glotscript_importer import GlotscriptImporter
from qq.importers.glottolog_importer import GlottologImporter
from qq.importers.linguameta_importer import LinguaMetaImporter
from qq.importers.iana_importer import IANAImporter
from qq.importers.joshi_importer import JoshiImporter
from qq.importers.loc_importer import LOCImporter
from qq.importers.sil_importer import SILImporter
from qq.importers.wikipedia_importer import WikipediaImporter
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.entity_resolution import EntityResolver

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def resolver():
    return EntityResolver()


class DummyImporter(BaseImporter):
    source = DataSource.GLOTTOLOG

    def import_data(self, data_path: Path) -> None:
        raise NotImplementedError


class TestJoshiImporter:
    def test_prefers_unique_language_but_does_not_choose_between_language_matches(self):
        levels = {"family": "family", "language-a": "language", "language-b": "language"}

        assert JoshiImporter._select_glottocode({"family"}, {"language-a"}, levels) == "language-a"
        assert JoshiImporter._select_glottocode({"family"}, {"language-a", "language-b"}, levels) == "family"

    def test_uses_wals_and_wikipedia_identifiers_before_generic_name_matching(self, resolver, tmp_path):
        glottolog = tmp_path / "glottolog"
        glottolog.mkdir()
        (glottolog / "languages.csv").write_text(
            "ID,Name,Glottocode,ISO639P3code,Level\n"
            "gree1276,Greek,gree1276,,family\n"
            "mode1248,Modern Greek,mode1248,ell,language\n"
            "wara1300,Waray (Philippines),wara1300,war,language\n",
            encoding="utf-8",
        )

        wals = tmp_path / "wals_2020"
        wals.mkdir()
        (wals / "languages.csv").write_text(
            "ID,Name,Glottocode,ISO639P3code\nwwy,Waray-Waray,wara1300,war\n",
            encoding="utf-8",
        )

        wikipedia = tmp_path / "wikipedia"
        wikipedia.mkdir()
        (wikipedia / "wikipedia.csv").write_text(
            "prefix,lang\nwar,Waray\nel,Greek\n",
            encoding="utf-8",
        )

        source = tmp_path / "joshi"
        source.mkdir()
        (source / "lang2tax.txt").write_text("waray-waray,0\nwaray,1\ngreek,3\n", encoding="utf-8")

        waray_id = resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "wara1300", IdType.ISO_639_3: "war"})
        greek_id = resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "mode1248", IdType.ISO_639_3: "ell"})
        resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "gree1276"})
        resolver.register_alias(IdType.WIKIPEDIA, "war", waray_id)
        resolver.register_alias(IdType.WIKIPEDIA, "el", greek_id)

        importer = JoshiImporter(
            resolver,
            glottolog_data_path=glottolog,
            wals_data_path=wals,
            wikipedia_data_path=wikipedia,
        )
        importer.import_data(source)

        waray = importer.resolve_languoid(IdType.ISO_639_3, "war")
        modern_greek = importer.resolve_languoid(IdType.ISO_639_3, "ell")
        greek_family = importer.resolve_languoid(IdType.GLOTTOCODE, "gree1276")
        assert waray is not None and waray.joshi_rating == 1
        assert modern_greek is not None and modern_greek.joshi_rating == 3
        assert greek_family is not None and greek_family.joshi_rating is None

    def test_joshi_rating_must_be_an_integer_from_zero_to_five(self):
        entity_set = EntitySet()

        with pytest.raises(TypeError):
            Languoid("lang:float", entity_set, joshi_rating=1.5)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            Languoid("lang:high", entity_set, joshi_rating=6)

    def test_imports_ratings_by_primary_and_alternative_glottolog_names(self, resolver, tmp_path):
        glottolog = tmp_path / "glottolog"
        glottolog.mkdir()
        (glottolog / "languages.csv").write_text(
            "ID,Name,Glottocode,ISO639P3code,Level\n"
            "dutc1256,Dutch,dutc1256,nld,language\n"
            "mand1415,Mandarin Chinese,mand1415,cmn,language\n"
            "bela1254,Belarusian,bela1254,bel,language\n"
            "broad123,Broad,broad123,,family\n"
            "speci123,Specific,speci123,xyz,language\n",
            encoding="utf-8",
        )
        (glottolog / "names.csv").write_text(
            "ID,Language_ID,Name,Provider,lang\n"
            "1,mand1415,Mandarin,,\n"
            "2,dutc1256,Nederlands,,\n"
            "3,bela1254,Belorussian,,\n"
            "4,speci123,Broad,,\n",
            encoding="utf-8",
        )
        source = tmp_path / "joshi"
        source.mkdir()
        (source / "lang2tax.txt").write_text(
            "dutch,4\nnederlands,4\nmandarin,5\n"
            "belarusian,3\nbelorussian,0\nbroad,2\n"
            "conflicted,0\nconflicted,1\ninvalid,7\n",
            encoding="utf-8",
        )

        resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "dutc1256", IdType.ISO_639_3: "nld"})
        resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "mand1415", IdType.ISO_639_3: "cmn"})
        resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "bela1254", IdType.ISO_639_3: "bel"})
        resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "broad123"})
        resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "speci123", IdType.ISO_639_3: "xyz"})

        importer = JoshiImporter(resolver, glottolog_data_path=glottolog)
        importer.import_data(source)

        dutch = importer.resolve_languoid(IdType.ISO_639_3, "nld")
        mandarin = importer.resolve_languoid(IdType.ISO_639_3, "cmn")
        belarusian = importer.resolve_languoid(IdType.ISO_639_3, "bel")
        broad_family = importer.resolve_languoid(IdType.GLOTTOCODE, "broad123")
        specific_language = importer.resolve_languoid(IdType.ISO_639_3, "xyz")
        assert dutch is not None and dutch.joshi_rating == 4
        assert mandarin is not None and mandarin.joshi_rating == 5
        assert belarusian is not None and belarusian.joshi_rating == 3
        assert broad_family is not None and broad_family.joshi_rating is None
        assert specific_language is not None and specific_language.joshi_rating == 2
        assert sum(lang.joshi_rating is not None for lang in importer.entity_set.entities_of_type(Languoid)) == 4


class TestBaseImporter:
    def test_add_bidirectional_relation_shared_metadata(self, resolver):
        """Metadata kwargs are applied to both directions."""
        importer = LinguaMetaImporter(resolver)
        es = importer.entity_set

        a = Languoid("lang:a", es)
        b = Script("script:b", es)
        es.add(a)
        es.add(b)

        importer.add_bidirectional_relation(
            a,
            RelationType.USES_SCRIPT,
            b,
            RelationType.USED_BY_LANGUOID,
            is_canonical=True,
        )

        fwd = a._relations[RelationType.USES_SCRIPT]
        assert len(fwd) == 1
        assert fwd[0].metadata == {"is_canonical": True}

        bwd = b._relations[RelationType.USED_BY_LANGUOID]
        assert len(bwd) == 1
        assert bwd[0].metadata == {"is_canonical": True}

        # Round-trip: a -> script -> languoids -> back to a
        assert a.id == a.scripts[0].languoids[0].id

    def test_add_bidirectional_relation_with_multiple_kwargs(self, resolver):
        """Multiple metadata kwargs used between two different entities."""
        importer = LinguaMetaImporter(resolver)
        es = importer.entity_set

        a = Languoid("lang:a", es)
        b = GeographicRegion("region:x", es)
        es.add(a)
        es.add(b)

        importer.add_bidirectional_relation(
            a,
            RelationType.SPOKEN_IN_REGION,
            b,
            RelationType.LANGUOIDS_IN_REGION,
            is_official=True,
            speaker_count=5000,
        )

        fwd = a._relations[RelationType.SPOKEN_IN_REGION]
        assert fwd[0].metadata == {"is_official": True, "speaker_count": 5000}

        bwd = b._relations[RelationType.LANGUOIDS_IN_REGION]
        assert bwd[0].metadata == {"is_official": True, "speaker_count": 5000}

    def test_get_or_create_languoid_reconciles_merged_canonical_ids(self, resolver):
        importer = DummyImporter(resolver)

        first = importer.get_or_create_languoid({IdType.BCP_47: "x-a"})
        first.name = "First Name"
        first.add_relation(RelationType.USES_SCRIPT, "script:latn", source="first")

        second = importer.get_or_create_languoid({IdType.ISO_639_3: "xaa"})
        second.endonym = "Second Name"

        script = Script("script:latn", importer.entity_set, iso_15924="Latn")
        script.add_relation(RelationType.USED_BY_LANGUOID, second.id, source="second")
        importer.entity_set.add(script)

        merged = importer.get_or_create_languoid({IdType.BCP_47: "x-a", IdType.ISO_639_3: "xaa"})

        assert merged.id == first.id
        assert merged is importer.entity_set.get(first.id)
        assert importer.entity_set.get(second.id) is None
        assert len(importer.entity_set.entities_of_type(Languoid)) == 1
        assert merged.bcp_47 == "x-a"
        assert merged.iso_639_3 == "xaa"
        assert merged.name == "First Name"
        assert merged.endonym == "Second Name"
        assert [rel.target_id for rel in script._relations[RelationType.USED_BY_LANGUOID]] == [merged.id]


class TestEntitySet:
    def test_add_get(self, resolver):
        es = EntitySet()
        lang = Languoid("lang:001", es, name="Test")
        es.add(lang)

        assert es.get("lang:001") is lang
        assert es.get("nonexistent") is None

    def test_iter_and_len(self, resolver):
        es = EntitySet()
        es.add(Languoid("lang:001", es))
        es.add(Script("script:001", es))
        assert len(es) == 2
        assert sum(1 for _ in es) == 2

    def test_entities_of_type(self, resolver):
        es = EntitySet()
        es.add(Languoid("lang:001", es))
        es.add(Script("script:001", es))
        es.add(Languoid("lang:002", es))

        languoids = es.entities_of_type(Languoid)
        assert len(languoids) == 2
        scripts = es.entities_of_type(Script)
        assert len(scripts) == 1


class TestLinguaMetaImporter:
    @pytest.fixture
    def importer(self, resolver):
        imp = LinguaMetaImporter(resolver)
        imp.import_data(FIXTURES / "linguameta")
        return imp

    def test_imports_languoid_with_identifiers(self, importer):
        """Languoid should have all identifiers from the JSON."""
        es = importer.entity_set
        # Find Dutch by resolving iso_639_3
        canonical = importer.resolver.resolve(IdType.ISO_639_3, "nld")
        assert canonical is not None
        lang = es.get(canonical)
        assert isinstance(lang, Languoid)
        assert lang.iso_639_3 == "nld"
        assert lang.bcp_47 == "nl"
        assert lang.iso_639_2b == "dut"
        assert lang.glottocode == "dutc1256"
        assert lang.wikidata_id == "Q7411"

    def test_extracts_english_canonical_name(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        assert lang.name == "Dutch"

    def test_extracts_endonym(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        assert lang.endonym == "Nederlands"

    def test_parses_speaker_count(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        assert lang.speaker_count == 24000000

    def test_extracts_description(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        assert lang.description == "Dutch is a West Germanic language."

    def test_sets_scope(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        assert lang.scope == LanguageScope.INDIVIDUAL

    def test_sets_endangerment_status(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        assert lang.endangerment_status == EndangermentStatus.NOT_ENDANGERED

        canonical_frr = importer.resolver.resolve(IdType.BCP_47, "frr")
        lang_frr = importer.entity_set.get(canonical_frr)
        assert lang_frr.endangerment_status == EndangermentStatus.SEVERELY_ENDANGERED

    def test_creates_region_relations(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        region_rels = lang._relations.get(RelationType.SPOKEN_IN_REGION, [])
        assert len(region_rels) == 2
        target_ids = {r.target_id for r in region_rels}
        assert "region:nl" in target_ids
        assert "region:be" in target_ids

    def test_region_metadata_is_official(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        region_rels = lang._relations[RelationType.SPOKEN_IN_REGION]
        # Both NL and BE should have is_official=True for Dutch
        for rel in region_rels:
            assert rel.metadata["is_official"] is True

    def test_creates_script_relations(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        script_rels = lang._relations.get(RelationType.USES_SCRIPT, [])
        # Dutch has Latn in both NL and BE locale entries, but should be deduplicated
        # to a single script relation (with is_canonical from the canonical entry)
        assert len(script_rels) >= 1
        target_ids = {r.target_id for r in script_rels}
        assert "script:latn" in target_ids

    def test_script_canonical_metadata(self, importer):
        canonical = importer.resolver.resolve(IdType.BCP_47, "nl")
        lang = importer.entity_set.get(canonical)
        script_rels = lang._relations[RelationType.USES_SCRIPT]
        # At least one script relation should have is_canonical=True
        canonical_rels = [r for r in script_rels if r.metadata.get("is_canonical")]
        assert len(canonical_rels) >= 1

    def test_deprecated_bcp47_code(self, importer):
        """Deprecated BCP-47 codes should be registered."""
        canonical = importer.resolver.resolve(IdType.BCP_47, "frr")
        lang = importer.entity_set.get(canonical)
        assert lang.deprecated_codes is not None
        assert any(dc.code == "frr-old" for dc in lang.deprecated_codes)

        # Old code should resolve to same entity
        old_canonical = importer.resolver.resolve(IdType.BCP_47, "frr-old")
        assert old_canonical == canonical

    def test_imports_locales(self, importer):
        """Locales should create region entities."""
        nl = importer.entity_set.get("region:nl")
        assert nl is not None
        assert isinstance(nl, GeographicRegion)
        assert nl.country_code == "NL"
        assert nl.name == "Netherlands"

    def test_imports_scripts(self, importer):
        """Script entities should be created from scripts.json."""
        latn = importer.entity_set.get("script:latn")
        assert latn is not None
        assert isinstance(latn, Script)
        assert latn.iso_15924 == "Latn"
        assert latn.name == "Latin"

    def test_stats_are_populated(self, importer):
        assert importer.stats.entities_created > 0


class TestGlottologImporter:
    @pytest.fixture
    def importer(self, resolver):
        """Run LinguaMeta first so resolver knows about nld/frr."""
        lm = LinguaMetaImporter(resolver)
        lm.import_data(FIXTURES / "linguameta")

        imp = GlottologImporter(resolver)
        imp.import_data(FIXTURES / "glottolog")
        return imp

    def test_creates_parent_child_relations(self, importer):
        """Dutch should have Germanic as parent."""
        dutch_id = importer.resolver.resolve(IdType.GLOTTOCODE, "dutc1256")
        dutch = importer.entity_set.get(dutch_id)
        assert dutch is not None

        parent_rels = dutch._relations.get(RelationType.PARENT_LANGUOID, [])
        assert len(parent_rels) == 1

        germanic_id = importer.resolver.resolve(IdType.GLOTTOCODE, "germ1287")
        assert parent_rels[0].target_id == germanic_id

    def test_sets_level(self, importer):
        dutch_id = importer.resolver.resolve(IdType.GLOTTOCODE, "dutc1256")
        dutch = importer.entity_set.get(dutch_id)
        assert dutch.level == LanguoidLevel.LANGUAGE

        ie_id = importer.resolver.resolve(IdType.GLOTTOCODE, "indo1319")
        ie = importer.entity_set.get(ie_id)
        assert ie.level == LanguoidLevel.FAMILY

    def test_sets_coordinates(self, importer):
        dutch_id = importer.resolver.resolve(IdType.GLOTTOCODE, "dutc1256")
        dutch = importer.entity_set.get(dutch_id)
        assert dutch.latitude == pytest.approx(52.15)
        assert dutch.longitude == pytest.approx(5.28)

    def test_family_has_children(self, importer):
        germanic_id = importer.resolver.resolve(IdType.GLOTTOCODE, "germ1287")
        germanic = importer.entity_set.get(germanic_id)
        child_rels = germanic._relations.get(RelationType.CHILD_LANGUOID, [])
        assert len(child_rels) == 2  # Dutch and Frisian

    def test_collects_name_data(self, importer):
        """Glottolog importer should collect name data for languoids with names."""
        assert importer.name_data
        dutch_id = importer.resolver.resolve(IdType.GLOTTOCODE, "dutc1256")
        assert dutch_id in importer.name_data
        entries = importer.name_data[dutch_id]
        assert len(entries) == 1
        assert entries[0].name == "Dutch"
        assert entries[0].bcp_47_code == "en"
        assert entries[0].is_canonical is True


class TestGlotscriptImporter:
    @pytest.fixture
    def importer(self, resolver):
        """Run LinguaMeta first so resolver knows about nld/frr."""
        lm = LinguaMetaImporter(resolver)
        lm.import_data(FIXTURES / "linguameta")

        imp = GlotscriptImporter(resolver)
        imp.import_data(FIXTURES / "glotscript")
        return imp

    def test_creates_script_languoid_relations(self, importer):
        dutch_id = importer.resolver.resolve(IdType.ISO_639_3, "nld")
        dutch = importer.entity_set.get(dutch_id)
        assert dutch is not None
        script_rels = dutch._relations.get(RelationType.USES_SCRIPT, [])
        assert len(script_rels) == 1
        assert script_rels[0].target_id == "script:latn"

    def test_script_has_back_relation(self, importer):
        script = importer.entity_set.get("script:latn")
        assert script is not None
        lang_rels = script._relations.get(RelationType.USED_BY_LANGUOID, [])
        assert len(lang_rels) == 2  # nld and frr


class TestWikipediaImporter:
    def test_special_wikipedia_code_takes_precedence_over_colliding_iso_code(self, resolver):
        norman_id = resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "norm1245"})
        resolver.find_or_create_canonical_id({IdType.ISO_639_3: "nrm"})
        importer = WikipediaImporter(resolver)

        result = importer._find_languoid_for_wikipedia_code("nrm")

        assert result is not None and result.id == norman_id

    @pytest.fixture
    def importer(self, resolver):
        """Run LinguaMeta first so resolver knows about nl/frr."""
        lm = LinguaMetaImporter(resolver)
        lm.import_data(FIXTURES / "linguameta")

        imp = WikipediaImporter(resolver)
        imp.import_data(FIXTURES / "wikipedia")
        return imp

    def test_imports_wikipedia_edition(self, importer):
        dutch_id = importer.resolver.resolve(IdType.BCP_47, "nl")
        dutch = importer.entity_set.get(dutch_id)
        assert dutch is not None
        assert dutch.wikipedia_url == "https://nl.wikipedia.org"
        assert dutch.wikipedia_code == "nl"
        assert dutch.wikipedia_article_count == 2150000
        assert dutch.wikipedia_active_users == 4500

    def test_imports_article_counts(self, importer):
        """Article count and active users should be populated from Wikistats data."""
        frr_id = importer.resolver.resolve(IdType.BCP_47, "frr")
        frr = importer.entity_set.get(frr_id)
        assert frr is not None
        assert frr.wikipedia_code == "frr"
        assert frr.wikipedia_article_count == 15600
        assert frr.wikipedia_active_users == 20

    def test_collects_name_data(self, importer):
        """Wikipedia importer should collect name data with English and local names."""
        assert importer.name_data
        dutch_id = importer.resolver.resolve(IdType.BCP_47, "nl")
        assert dutch_id in importer.name_data
        entries = importer.name_data[dutch_id]
        # Should have English name + local name (Nederlands)
        assert len(entries) == 2
        en_entry = [e for e in entries if e.bcp_47_code == "en"][0]
        assert en_entry.name == "Dutch"
        local_entry = [e for e in entries if e.bcp_47_code == "nl"][0]
        assert local_entry.name == "Nederlands"


class TestSILImporter:
    @pytest.fixture
    def importer(self, resolver):
        """Pre-register some languoids so SIL can find replacements."""
        # Register Romanian (ron) as a known languoid
        resolver.find_or_create_canonical_id({IdType.ISO_639_3: "ron"})
        # Register knw and huc for split test
        resolver.find_or_create_canonical_id({IdType.ISO_639_3: "knw"})
        resolver.find_or_create_canonical_id({IdType.ISO_639_3: "huc"})

        imp = SILImporter(resolver)
        imp.import_data(FIXTURES / "sil_iso6393")
        return imp

    def test_merge_replacement(self, importer):
        """Merged code (mol -> ron) should create DeprecatedCode on replacement."""
        ron_id = importer.resolver.resolve(IdType.ISO_639_3, "ron")
        ron = importer.entity_set.get(ron_id)
        assert ron is not None
        assert ron.deprecated_codes is not None
        mol_dc = [dc for dc in ron.deprecated_codes if dc.code == "mol"]
        assert len(mol_dc) == 1
        assert mol_dc[0].reason == DeprecationReason.MERGE
        assert mol_dc[0].name == "Moldavian"

    def test_merge_registers_alias(self, importer):
        """Old code should resolve to the replacement entity."""
        ron_id = importer.resolver.resolve(IdType.ISO_639_3, "ron")
        mol_id = importer.resolver.resolve(IdType.ISO_639_3, "mol")
        assert mol_id == ron_id

    def test_split_creates_deprecated_codes(self, importer):
        """Split code should attach DeprecatedCode to each replacement."""
        knw_id = importer.resolver.resolve(IdType.ISO_639_3, "knw")
        knw = importer.entity_set.get(knw_id)
        assert knw is not None
        assert knw.deprecated_codes is not None
        xuu_dc = [dc for dc in knw.deprecated_codes if dc.code == "xuu"]
        assert len(xuu_dc) == 1
        assert xuu_dc[0].reason == DeprecationReason.SPLIT
        assert xuu_dc[0].split_into == ["knw", "huc"]

    def test_split_on_second_target(self, importer):
        """Both split targets should have the deprecated code."""
        huc_id = importer.resolver.resolve(IdType.ISO_639_3, "huc")
        huc = importer.entity_set.get(huc_id)
        assert huc is not None
        assert huc.deprecated_codes is not None
        xuu_dc = [dc for dc in huc.deprecated_codes if dc.code == "xuu"]
        assert len(xuu_dc) == 1

    def test_deprecated_tracking(self, importer):
        """All retired codes should be marked deprecated in resolver."""
        assert importer.resolver.is_deprecated(IdType.ISO_639_3, "mol")
        assert importer.resolver.is_deprecated(IdType.ISO_639_3, "xuu")
        assert importer.resolver.is_deprecated(IdType.ISO_639_3, "bgh")

    def test_nonexistent_code_unresolved(self, importer):
        """Non-existent codes should not resolve to any entity."""
        bgh_id = importer.resolver.resolve(IdType.ISO_639_3, "bgh")
        # bgh was never registered as an entity, so resolve returns None
        assert bgh_id is None


class TestSILAndLOCImporters:
    @pytest.fixture
    def importer(self, resolver):
        """Run LinguaMeta first, then SIL and LOC for ISO enrichment."""
        lm = LinguaMetaImporter(resolver)
        lm.import_data(FIXTURES / "linguameta")

        sil = SILImporter(resolver)
        sil.import_data(FIXTURES / "sil_iso6393")

        loc = LOCImporter(resolver)
        loc.import_data(FIXTURES / "loc")
        return sil

    def test_enriches_languoid_scope_status(self, importer):
        nld_id = importer.resolver.resolve(IdType.ISO_639_3, "nld")
        nld = importer.entity_set.get(nld_id)
        assert nld is not None
        assert nld.scope == LanguageScope.INDIVIDUAL
        assert nld.status == LanguageStatus.LIVING

    def test_registers_iso639_1_alias(self, importer):
        """ISO 639-1 codes should be registered as aliases."""
        nl_id = importer.resolver.resolve(IdType.ISO_639_1, "nl")
        nld_id = importer.resolver.resolve(IdType.ISO_639_3, "nld")
        assert nl_id == nld_id

    def test_creates_missing_languoids(self, importer):
        """Chinese (zho) is not in linguameta fixture, should be created by SIL."""
        zho_id = importer.resolver.resolve(IdType.ISO_639_3, "zho")
        assert zho_id is not None
        zho = importer.entity_set.get(zho_id)
        assert zho is not None
        assert zho.name == "Chinese"
        assert zho.scope == LanguageScope.MACROLANGUAGE

    def test_registers_iso639_2b_alias(self, importer):
        """LOC should register ISO 639-2B aliases."""
        dut_id = importer.resolver.resolve(IdType.ISO_639_2B, "dut")
        nld_id = importer.resolver.resolve(IdType.ISO_639_3, "nld")
        assert dut_id == nld_id

    def test_collects_name_data_for_enriched_languoids(self, importer):
        """SIL should collect name data for languoids it enriches."""
        assert importer.name_data
        nld_id = importer.resolver.resolve(IdType.ISO_639_3, "nld")
        assert nld_id in importer.name_data
        entries = importer.name_data[nld_id]
        assert len(entries) == 1
        assert entries[0].name == "Dutch"

    def test_collects_name_data_for_missing_languoids(self, importer):
        """SIL should collect name data for languoids it creates."""
        zho_id = importer.resolver.resolve(IdType.ISO_639_3, "zho")
        assert zho_id in importer.name_data
        entries = importer.name_data[zho_id]
        assert entries[0].name == "Chinese"

    def test_loc_does_not_create_collectives_as_iso639_3(self, resolver):
        """LOC collective ISO 639-2 rows should not become ISO 639-3 identifiers."""
        importer = LOCImporter(resolver)
        importer.import_data(FIXTURES / "loc")

        gem_2b = importer.resolver.resolve(IdType.ISO_639_2B, "gem")
        gem_3 = importer.resolver.resolve(IdType.ISO_639_3, "gem")
        assert gem_2b is not None
        assert gem_3 is None


class TestIANAImporter:
    @pytest.fixture
    def importer(self, resolver):
        """Run LinguaMeta + SIL + LOC first so IANA can resolve preferred codes."""
        lm = LinguaMetaImporter(resolver)
        lm.import_data(FIXTURES / "linguameta")

        sil = SILImporter(resolver)
        sil.import_data(FIXTURES / "sil_iso6393")

        loc = LOCImporter(resolver)
        loc.import_data(FIXTURES / "loc")

        imp = IANAImporter(resolver)
        imp.import_data(FIXTURES / "iana")
        return imp

    def test_deprecated_iso639_1_registered(self, importer):
        """Deprecated ISO 639-1 codes should be marked deprecated in resolver."""
        assert importer.resolver.is_deprecated(IdType.ISO_639_1, "iw")
        assert importer.resolver.is_deprecated(IdType.ISO_639_1, "in")
        assert importer.resolver.is_deprecated(IdType.ISO_639_1, "ji")
        assert importer.resolver.is_deprecated(IdType.ISO_639_1, "mo")

    def test_deprecated_code_resolves_to_replacement(self, importer):
        """iw should resolve to the same canonical entity as he (Hebrew)."""
        iw_id = importer.resolver.resolve(IdType.ISO_639_1, "iw")
        he_id = importer.resolver.resolve(IdType.ISO_639_1, "he")
        assert iw_id is not None
        assert he_id is not None
        assert iw_id == he_id

    def test_deprecated_without_preferred_registered(self, importer):
        """sh (Serbo-Croatian) is deprecated with no Preferred-Value."""
        assert importer.resolver.is_deprecated(IdType.ISO_639_1, "sh")
        # No alias should be registered (sh doesn't resolve to anything)
        sh_id = importer.resolver.resolve(IdType.ISO_639_1, "sh")
        assert sh_id is None

    def test_deprecated_code_on_languoid(self, importer):
        """Hebrew languoid should have iw as a DeprecatedCode."""
        he_id = importer.resolver.resolve(IdType.ISO_639_1, "he")
        he = importer.entity_set.get(he_id)
        assert he is not None
        assert he.deprecated_codes is not None
        iw_dc = [dc for dc in he.deprecated_codes if dc.code == "iw"]
        assert len(iw_dc) == 1
        assert iw_dc[0].code_type == IdType.ISO_639_1

    def test_non_deprecated_not_registered(self, importer):
        """Non-deprecated language subtags should not appear in deprecated index."""
        assert not importer.resolver.is_deprecated(IdType.ISO_639_1, "nl")
        assert not importer.resolver.is_deprecated(IdType.ISO_639_1, "he")

    def test_region_and_script_subtags_ignored(self, importer):
        """Type: region and Type: script records should not create deprecated entries."""
        assert not importer.resolver.is_deprecated(IdType.ISO_639_1, "NL")
        assert not importer.resolver.is_deprecated(IdType.ISO_639_1, "Latn")

    def test_parse_registry_yields_records(self):
        """_parse_registry should yield one dict per record."""
        records = list(IANAImporter._parse_registry(FIXTURES / "iana" / "language-subtag-registry"))
        # File-Date header + all language/region/script records
        assert len(records) >= 10
        types = [r.get("Type") for r in records if "Type" in r]
        assert "language" in types
        assert "region" in types
        assert "script" in types
