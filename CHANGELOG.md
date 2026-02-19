# Changelog

All notable changes to qwanqwa will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- NLLB-style codes support improvements
- Additional convenience methods on Languoid

## [1.0.2] - 2026-02-19

- `Database.load()` logged a bunch of INFO level messages which are now at DEBUG level
- `build_database.py` called `logging.basicConfig()` at import time, overriding the logging configuration of any application that used qq as a library

## [1.0.1] - 2026-02-19

### Fixed
- fixed an import issue due to missing build dependencies with regular install
- fixed the location of the sources when rebuilding with installed version, should be okay now

### Removed
- removed old script

## [1.0.0] - 2026-02-19

**IMPORTANT**: This is a major rewrite with breaking changes. There is no backwards compatibility with 0.x versions.

### Added
- `Database` class as the main entry point, replacing the old `LanguageData` class
- `Languoid` objects with a full set of attributes: `bcp_47`, `iso_639_1`, `iso_639_3`, `iso_639_2b`, `iso_639_5`, `glottocode`, `wikidata_id`, `name`, `endonym`, `scope`, `level`, `speaker_count`, `endangerment_status`, `deprecated_codes`
- Traversable language/script/region graph: `parent`, `children`, `siblings`, `family_tree`, `descendants()`, `scripts`, `canonical_scripts`, `regions`
- `languoids_with_same_script` and `languoids_in_same_region` properties on `Languoid`
- `IdType` enum covering BCP-47, ISO 639-1, ISO 639-2B, ISO 639-2T, ISO 639-3, ISO 639-5, Glottocode, Wikidata ID, Wikipedia ID, NLLB
- `Database.guess()` for automatic identifier type detection
- `Database.convert()` for converting between identifier types
- `Database.search()` for name-based lookup
- Multilingual names: `Languoid.name_in()` and `Languoid.endonym`
- `NameEntry` dataclass for structured name data
- `DeprecatedCode` dataclass and `DeprecatedCodeWarning` for retired identifier codes
- `Script` and `GeographicRegion` objects with traversal support
- `EndangermentStatus`, `LanguageScope`, `LanguageStatus`, `LanguoidLevel` enums
- CLI commands: `qq get`, `qq search`, `qq validate`, `qq status`, `qq rebuild`
- 11 example scripts in `examples/` covering common use cases
- 4 case studies: HuggingFace Hub language tag audit, dataset linking, publication table generation, identifier coverage visualization
- Type hints

### Changed
- **BREAKING**: Renamed `LanguageData` -> `Database`
- **BREAKING**: Removed `_code` suffixes from identifier attributes (`iso_639_3_code` -> `iso_639_3`)
- **BREAKING**: Renamed `IdType` enum values (`BCP_47_CODE` -> `BCP_47`)
- **BREAKING**: NLLB codes now accessed via `nllb_codes()` method
- Improved data storage: separate `names.zip` for multilingual name data (lazy-loaded)
- Entity resolution now tracks conflicts and source priority instead of silently overwriting

### Fixed

### Removed
- **BREAKING**: `LanguageData` class
- **BREAKING**: Old tag conversion methods (use `Database.convert()` instead)

## [0.3.1] - 2025-01-XX

Initial versions, trying stuff out.
