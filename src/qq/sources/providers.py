import hashlib
import json
import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import qq
from qq.constants import DATETIME_FMT

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    GIT = "git"
    DIR = "dir"
    FILE = "file"


@dataclass
class SourceStatus:
    """Status of a source, this is for displaying and checking, the SourceMetadata is for internal tracking."""

    version: str | None
    last_updated: str | None
    last_checked: str | None
    checksum: str | None
    is_valid: bool
    data_path: str


@dataclass
class SourceMetadata:
    """Metadata about a data source. This is more for internal use, for displaying use SourceStatus."""

    name: str
    license: str
    source_type: SourceType
    source_url: str | None = None  # The url for getting the actual data
    website_url: str | None = None  # Project website or similar
    paper_url: str | None = None  # Paper for the project
    notes: str | None = None  # Additional sources or comments, see sources.md
    # The fields below are unknown the first time a source is fetched
    # or if we run into an error during the fetching.
    # Do not manually update these as they will be overwritten.
    _version: str | None = None
    _last_updated: datetime | None = None
    _last_checked: datetime | None = None
    _checksum: str | None = None


class SourceProvider(ABC):
    """Base class for data source providers"""

    def __init__(
        self,
        name: str,
        sources_dir: Path,
        license: str,
        source_type: SourceType,
        source_url: str | None = None,
        website_url: str | None = None,
        paper_url: str | None = None,
        notes: str | None = None,
        external_resources: list[object] | None = None,
        display_name: str | None = None,
    ):
        self.name = name
        self.source_url = source_url
        self.sources_dir = sources_dir
        self.external_resources = external_resources or []
        self.display_name = display_name

        self.metadata_dir = self.sources_dir / "_metadata"
        self.metadata_dir.mkdir(exist_ok=True, parents=True)
        self.metadata_file = self.metadata_dir / f"{name}_metadata.json"

        self.data_dir = self.sources_dir / self.name
        self.data_dir.mkdir(exist_ok=True, parents=True)

        self.metadata = self._load_metadata(name, license, source_type, source_url, website_url, paper_url, notes)

    @abstractmethod
    def fetch(self, force: bool = False) -> bool:
        """
        Fetch/update the source data.
        Returns True if data was updated, False if already up-to-date.
        """
        pass

    @abstractmethod
    def get_version(self) -> str | None:
        """Get current version of the source"""
        pass

    @abstractmethod
    def verify(self) -> bool:
        """Verify the source data is valid"""
        pass

    def get_status(self) -> SourceStatus:
        """Get the status of the source"""
        md = self.metadata
        return SourceStatus(
            version=self.get_version(),
            last_updated=md._last_updated.isoformat() if md._last_updated else None,
            last_checked=md._last_checked.isoformat() if md._last_checked else None,
            checksum=md._checksum,
            is_valid=self.verify(),
            data_path=str(self.data_dir),
        )

    def _load_metadata(
        self,
        name: str,
        license: str,
        source_type: SourceType,
        source_url: str | None = None,
        website_url: str | None = None,
        paper_url: str | None = None,
        notes: str | None = None,
    ) -> SourceMetadata:
        """Load metadata from file"""
        if self.metadata_file.exists():
            data = json.loads(self.metadata_file.read_bytes())
            # Convert datetime strings back to datetime objects
            if data.get("_last_updated"):
                data["_last_updated"] = datetime.fromisoformat(data["_last_updated"])
            if data.get("_last_checked"):
                data["_last_checked"] = datetime.fromisoformat(data["_last_checked"])
            if st := data.get("source_type"):
                data["source_type"] = SourceType[st.upper()]
            return SourceMetadata(**data)
        else:
            return SourceMetadata(
                name=name,
                license=license,
                source_type=source_type,
                source_url=source_url,
                website_url=website_url,
                paper_url=paper_url,
                notes=notes,
            )

    def _save_metadata(self):
        """Save metadata to file"""
        data = asdict(self.metadata)
        data["_last_updated"] = self.metadata._last_updated.isoformat() if self.metadata._last_updated else None
        data["_last_checked"] = self.metadata._last_checked.isoformat() if self.metadata._last_checked else None
        self.metadata_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _calculate_checksum(self, path: Path) -> str:
        """Calculate checksum of a file or directory"""
        if path.is_file():
            return self._file_checksum(path)
        elif path.is_dir():
            return self._dir_checksum(path)
        else:
            raise ValueError("Can only calculate checksum for file or dir.")

    def _file_checksum(self, filepath: Path) -> str:
        """Calculate SHA256 checksum of a file"""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _dir_checksum(self, dirpath: Path) -> str:
        """Calculate checksum of all files in directory"""
        sha256 = hashlib.sha256()

        files = sorted(dirpath.rglob("*"))
        for filepath in files:
            if filepath.is_file():
                sha256.update(str(filepath.relative_to(dirpath)).encode())
                sha256.update(self._file_checksum(filepath).encode())

        return sha256.hexdigest()


class GitSourceProvider(SourceProvider):
    """Provider for Git repositories"""

    def __init__(
        self,
        name: str,
        sources_dir: Path,
        license: str,
        branch: str = "main",
        subpath: str = "",  # where to look for the data directory for example
        source_url: str | None = None,
        website_url: str | None = None,
        paper_url: str | None = None,
        notes: str | None = None,
        external_resources: list[object] | None = None,
        display_name: str | None = None,
    ):
        super().__init__(
            name,
            sources_dir,
            license,
            SourceType.GIT,
            source_url=source_url,
            website_url=website_url,
            paper_url=paper_url,
            notes=notes,
            external_resources=external_resources,
            display_name=display_name,
        )
        self.branch = branch
        self.subpath = subpath
        self.repo_path = self.sources_dir / f"{name}_repo"
        # TODO: a source url should be required for all sources that download something
        # Maybe there should be a subclass that requires this URLSourceProvider? For now this is necessary to
        # keep ty happy
        self.source_url: str

        self._verify_git_available()

    def fetch(self, force: bool = False) -> bool:
        """Clone or update git repository"""
        logger.info(f"Fetching {self.name} from {self.source_url}...")

        updated = False

        # Clone new
        if not self.repo_path.exists():
            logger.info(f"Cloning {self.name}...")
            subprocess.run(
                ["git", "clone", "--branch", self.branch, "--depth", "1", self.source_url, str(self.repo_path)],
                check=True,
                capture_output=True,
            )
            updated = True
        # Update existing
        else:
            logger.info(f"Updating {self.name}...")
            # Get current commit hash
            old_hash = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            # Pull updates
            subprocess.run(
                ["git", "pull", "origin", self.branch],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            # Get new commit hash
            new_hash = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            if old_hash != new_hash:
                logger.info(f"Updated {self.name}: {old_hash[:8]} -> {new_hash[:8]}")
                updated = True
            else:
                logger.info(f"{self.name} is up-to-date")

        # Copy data to usable location
        source_path = self.repo_path / self.subpath if self.subpath else self.repo_path
        target_path = self.data_dir

        if target_path.exists():
            shutil.rmtree(target_path)

        if source_path.is_dir():
            shutil.copytree(source_path, target_path)
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

        self.metadata._version = self.get_version()
        self.metadata._last_updated = datetime.now()
        self.metadata._last_checked = datetime.now()
        self.metadata._checksum = self._calculate_checksum(target_path)
        self._save_metadata()

        return updated

    def get_version(self) -> str | None:
        """Get current git commit hash"""
        if not self.repo_path.exists():
            return None

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()[:8]

    def verify(self) -> bool:
        """Verify git repository is valid"""
        if not self.repo_path.exists():
            return False

        try:
            subprocess.run(["git", "status"], cwd=self.repo_path, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def _verify_git_available():
        try:
            subprocess.run(["git", "-v"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise ModuleNotFoundError(f"Make sure git is installed for the GitSourceProvider. {e}")


class DirectorySourceProvider(SourceProvider):
    """Provider for local directory data sources"""

    def __init__(
        self,
        name: str,
        sources_dir: Path,
        local_path: Path,
        license: str,
        website_url: str | None = None,
        paper_url: str | None = None,
        notes: str | None = None,
        external_resources: list[object] | None = None,
        display_name: str | None = None,
    ):
        super().__init__(
            name,
            sources_dir,
            license,
            SourceType.DIR,
            website_url=website_url,
            paper_url=paper_url,
            notes=notes,
            external_resources=external_resources,
            display_name=display_name,
        )
        self.local_path = local_path

    def fetch(self, force: bool = False) -> bool:
        """Copy from local directory"""
        if not self.local_path.exists():
            raise FileNotFoundError("Source folder not found!")

        target_path = self.data_dir

        # Check if changed
        new_checksum = self._calculate_checksum(self.local_path)
        if not force and new_checksum == self.metadata._checksum:
            logger.info(f"{self.name} is up-to-date")
            self.metadata._last_checked = datetime.now()
            self._save_metadata()
            return False

        # Copy data
        if target_path.exists():
            shutil.rmtree(target_path)

        if self.local_path.is_dir():
            shutil.copytree(self.local_path, target_path)
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.local_path, target_path)

        logger.info(f"Copied {self.name} from {self.local_path}")

        self.metadata._version = datetime.now().strftime(DATETIME_FMT)
        self.metadata._last_updated = datetime.now()
        self.metadata._last_checked = datetime.now()
        self.metadata._checksum = new_checksum
        self._save_metadata()

        return True

    def get_version(self) -> str | None:
        """Get version (use checksum)"""
        return self.metadata._checksum[:8] if self.metadata._checksum else None

    def verify(self) -> bool:
        """Verify local path exists"""
        return self.local_path.exists()


@dataclass(frozen=True)
class DownloadFile:
    """A single file to download into a source directory."""

    url: str
    filename: str


class FileDownloadSourceProvider(SourceProvider):
    """Provider for sources made up of one or more downloadable files."""

    def __init__(
        self,
        name: str,
        sources_dir: Path,
        license: str,
        source_url: str | None = None,
        filename: str | None = None,
        files: list[DownloadFile] | None = None,
        cache_duration_hours: int = 24,
        paper_url: str | None = None,
        website_url: str | None = None,
        notes: str | None = None,
        external_resources: list[object] | None = None,
        display_name: str | None = None,
    ):
        if files is None and (source_url is None or filename is None):
            raise ValueError("FileDownloadSourceProvider requires either files or source_url + filename")
        if files is not None and filename is not None:
            raise ValueError("Use either files or filename, not both")

        super().__init__(
            name,
            sources_dir,
            license,
            SourceType.FILE,
            source_url=source_url,
            website_url=website_url,
            paper_url=paper_url,
            notes=notes,
            external_resources=external_resources,
            display_name=display_name,
        )
        self.filename = filename
        self.files = files
        self.cache_duration_hours = cache_duration_hours

    @property
    def _download_files(self) -> list[DownloadFile]:
        if self.files is not None:
            return self.files
        if self.source_url is None or self.filename is None:
            raise ValueError("FileDownloadSourceProvider has no download files configured")
        return [DownloadFile(url=self.source_url, filename=self.filename)]

    def fetch(self, force: bool = False) -> bool:
        """Download all configured files."""
        target_dir = self.data_dir
        files = self._download_files
        target_files = [target_dir / file.filename for file in files]

        if not force and all(path.exists() for path in target_files) and self.metadata._last_updated:
            age_hours = (datetime.now() - self.metadata._last_updated).total_seconds() / 3600
            if age_hours < self.cache_duration_hours:
                logger.info(f"{self.name} cache is still valid (age: {age_hours:.1f} hours)")
                self.metadata._last_checked = datetime.now()
                self._save_metadata()
                return False

        try:
            from urllib.request import Request, urlopen

            headers = {"User-Agent": f"qwanqwa/{qq.__version__} (https://github.com/WPoelman/qwanqwa) Python/urllib"}
            downloads: list[tuple[Path, bytes]] = []
            for file in files:
                logger.info(f"Fetching {self.name}/{file.filename} from {file.url}...")
                request = Request(file.url, headers=headers)
                with urlopen(request, timeout=30) as response:
                    content = response.read()
                    logger.info(f"Successfully downloaded {self.name}/{file.filename} ({len(content)} bytes)")
                    downloads.append((target_dir / file.filename, content))
        except Exception as e:
            logger.error(f"Failed to download {self.name}: {e}")
            return False

        target_dir.mkdir(parents=True, exist_ok=True)
        for target_file, content in downloads:
            with open(target_file, "wb") as f:
                f.write(content)

        self.metadata._version = datetime.now().strftime(DATETIME_FMT)
        self.metadata._last_updated = datetime.now()
        self.metadata._last_checked = datetime.now()
        self.metadata._checksum = self._calculate_checksum(target_dir)
        self._save_metadata()

        return True

    def get_version(self) -> str | None:
        """Get version (fetch timestamp)."""
        return self.metadata._version

    def verify(self) -> bool:
        """Verify all downloaded files exist."""
        return all((self.data_dir / file.filename).exists() for file in self._download_files)


class WikidataSparqlSourceProvider(FileDownloadSourceProvider):
    """Provider for cached Wikidata SPARQL JSON results."""

    endpoint_url = "https://query.wikidata.org/sparql"

    def __init__(self, *args, query: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query

    def fetch(self, force: bool = False) -> bool:
        from urllib.parse import urlencode

        self.source_url = f"{self.endpoint_url}?{urlencode({'format': 'json', 'query': self.query})}"
        return super().fetch(force=force)


class HuggingFaceDatasetTagsSourceProvider(FileDownloadSourceProvider):
    """Provider that caches Hugging Face language tags with dataset counts."""

    dataset_search_url = "https://huggingface.co/api/datasets"
    page_size = 100
    max_count = 1000

    def fetch(self, force: bool = False) -> bool:
        target_dir = self.data_dir
        if not self.filename:
            raise ValueError("Filename should not be empty.")
        target_file = target_dir / self.filename

        logger.info(f"Fetching {self.name} from {self.source_url}...")

        if not force and target_file.exists() and self.metadata._last_updated:
            age_hours = (datetime.now() - self.metadata._last_updated).total_seconds() / 3600
            if age_hours < self.cache_duration_hours:
                logger.info(f"{self.name} cache is still valid (age: {age_hours:.1f} hours)")
                self.metadata._last_checked = datetime.now()
                self._save_metadata()
                return False

        try:
            data = self._fetch_language_tag_counts()
        except Exception as e:
            logger.error(f"Failed to fetch {self.name}: {e}")
            return False

        target_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        self.metadata._version = datetime.now().strftime(DATETIME_FMT)
        self.metadata._last_updated = datetime.now()
        self.metadata._last_checked = datetime.now()
        self.metadata._checksum = self._file_checksum(target_file)
        self._save_metadata()

        return True

    def _fetch_language_tag_counts(self) -> dict[str, list[dict[str, int | str]]]:
        from collections import Counter

        headers = {"User-Agent": f"qwanqwa/{qq.__version__} (https://github.com/WPoelman/qwanqwa) Python/urllib"}
        url = self.source_url
        counts: Counter[str] = Counter()
        page_count = 0
        dataset_count = 0

        while url:
            datasets, link, base_url = self._fetch_dataset_page(url, headers)
            page_count += 1
            dataset_count += len(datasets)

            for dataset in datasets:
                tags = dataset.get("tags") or []
                for tag in tags:
                    if isinstance(tag, str) and tag.startswith("language:"):
                        counts[tag] += 1

            if page_count == 1 or page_count % 25 == 0:
                logger.info(
                    "Scanned %d Hugging Face dataset pages (%d datasets, %d language tags)",
                    page_count,
                    dataset_count,
                    len(counts),
                )

            url = self._next_link(link, base_url)

        return {
            "language": [
                {"id": tag, "dataset_count": count} for tag, count in sorted(counts.items(), key=lambda item: item[0])
            ]
        }

    def _fetch_dataset_page(
        self, url: str, headers: dict[str, str], retries: int = 3
    ) -> tuple[list[dict], str | None, str]:
        import time
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        for attempt in range(retries + 1):
            request = Request(url, headers=headers)
            try:
                with urlopen(request, timeout=60) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    self._respect_rate_limit(response.headers)
                    return data, response.headers.get("Link"), response.geturl()
            except HTTPError as e:
                if e.code != 429 or attempt >= retries:
                    raise
                wait_seconds = self._retry_after_seconds(e.headers)
                logger.warning("Hugging Face rate limit reached; retrying in %d seconds", wait_seconds)
                time.sleep(wait_seconds)

        raise RuntimeError("unreachable")

    @staticmethod
    def _respect_rate_limit(headers) -> None:
        import time

        ratelimit = headers.get("ratelimit")
        if not ratelimit:
            return
        remaining = HuggingFaceDatasetTagsSourceProvider._ratelimit_value(ratelimit, "r")
        reset_seconds = HuggingFaceDatasetTagsSourceProvider._ratelimit_value(ratelimit, "t")
        if remaining is not None and reset_seconds is not None and remaining <= 2:
            logger.info("Pausing for Hugging Face API rate limit reset (%d seconds)", reset_seconds)
            time.sleep(reset_seconds + 1)

    @staticmethod
    def _retry_after_seconds(headers) -> int:
        retry_after = headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return max(1, int(retry_after))
        ratelimit = headers.get("ratelimit")
        reset_seconds = HuggingFaceDatasetTagsSourceProvider._ratelimit_value(ratelimit or "", "t")
        return max(30, (reset_seconds or 60) + 1)

    @staticmethod
    def _ratelimit_value(header: str, key: str) -> int | None:
        prefix = f"{key}="
        for part in header.split(";"):
            value = part.strip()
            if value.startswith(prefix):
                raw = value.removeprefix(prefix)
                if raw.isdigit():
                    return int(raw)
        return None

    @staticmethod
    def _next_link(link_header: str | None, base_url: str) -> str | None:
        from urllib.parse import urljoin

        if not link_header:
            return None
        for part in link_header.split(","):
            section = part.strip()
            if 'rel="next"' not in section:
                continue
            start = section.find("<")
            end = section.find(">")
            if start != -1 and end != -1 and end > start:
                return urljoin(base_url, section[start + 1 : end])
        return None
