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
    ):
        self.name = name
        self.source_url = source_url
        self.sources_dir = sources_dir

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
    ):
        super().__init__(name, sources_dir, license, SourceType.GIT, source_url, website_url, paper_url, notes)
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
    ):
        super().__init__(name, sources_dir, license, SourceType.DIR, website_url, paper_url, notes)
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


class FileDownloadSourceProvider(SourceProvider):
    """Provider for single-file downloads (TSV, CSV, etc.)"""

    def __init__(
        self,
        name: str,
        sources_dir: Path,
        source_url: str,
        filename: str,
        license: str,
        cache_duration_hours: int = 24,
        paper_url: str | None = None,
        website_url: str | None = None,
        notes: str | None = None,
    ):
        super().__init__(name, sources_dir, license, SourceType.FILE, source_url, website_url, paper_url, notes)
        self.filename = filename
        self.cache_duration_hours = cache_duration_hours

        self.source_url: str  # see above

    def fetch(self, force: bool = False) -> bool:
        """Download file"""
        target_dir = self.data_dir
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
            from urllib.request import Request, urlopen

            headers = {"User-Agent": f"qwanqwa/{qq.__version__} (https://github.com/WPoelman/qwanqwa) Python/urllib"}
            request = Request(self.source_url, headers=headers)

            with urlopen(request, timeout=30) as response:
                content = response.read()
                logger.info(f"Successfully downloaded {self.name} ({len(content)} bytes)")
        except Exception as e:
            logger.error(f"Failed to download {self.name}: {e}")
            return False

        target_dir.mkdir(parents=True, exist_ok=True)
        with open(target_file, "wb") as f:
            f.write(content)

        self.metadata._version = datetime.now().strftime(DATETIME_FMT)
        self.metadata._last_updated = datetime.now()
        self.metadata._last_checked = datetime.now()
        self.metadata._checksum = self._file_checksum(target_file)
        self._save_metadata()

        return True

    def get_version(self) -> str | None:
        """Get version (fetch timestamp)."""
        return self.metadata._version

    def verify(self) -> bool:
        """Verify the downloaded file exists."""
        target_file = self.data_dir / self.filename
        return target_file.exists()
