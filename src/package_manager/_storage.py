"""Where optional modules live on disk, and how a wheel becomes a usable module.

Two things make this the security sensitive part of the package manager:

- :func:`extract_wheel` refuses any archive member that could write outside the destination
  directory, and refuses any top level entry the allowlist did not expect. A wheel is a zip, and a
  zip can name a member ``../evil.py`` or ``C:/evil.py``.
- :func:`verify_sha256` checks the download against the pinned digest before any of it is unpacked.
"""

import csv
import hashlib
import io
import json
import logging
import ntpath
import os
import stat
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Final

from constants import APPLICATION_NAME

from ._allowlist import PackageError

logger = logging.getLogger(__name__)

INDEX_FILENAME: Final[str] = "installed.json"
INDEX_SCHEMA: Final[int] = 1
CHUNK_SIZE: Final[int] = 1024 * 1024
RECORD_NAME: Final[str] = "RECORD"
RECORD_SIGNATURE_SUFFIXES: Final[frozenset[str]] = frozenset({".jws", ".p7s"})


def modules_root() -> Path:
    """Directory holding installed modules, wheels and the install index.

    Honours ``PROSPERO_MODULES_PATH`` so tests and portable installs can move it.
    """
    if override := os.environ.get(f"{APPLICATION_NAME.upper()}_MODULES_PATH"):
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APPLICATION_NAME.title() / "modules"
    return Path.home() / ".local" / "share" / APPLICATION_NAME / "modules"


def module_dir(name: str, version: str, root: Path | None = None) -> Path:
    """Directory an installed module is unpacked into."""
    return (root or modules_root()) / f"{name}-{version}"


def cache_dir(root: Path | None = None) -> Path:
    """Directory holding verified wheels, so a reinstall works while offline."""
    return (root or modules_root()) / "cache"


def index_path(root: Path | None = None) -> Path:
    return (root or modules_root()) / INDEX_FILENAME


def _safe(name: str) -> bool:
    """Whether an archive member name is safe to write below the destination."""
    if not name or name.startswith(("/", "\\")):
        return False
    if ntpath.isabs(name) or name.startswith("\\\\"):
        return False
    if len(name) > 1 and name[1] == ":":
        return False
    parts = PurePosixPath(name).parts
    if any(part in ("..", "") for part in parts):
        return False
    return "\\" not in name


def verify_sha256(wheel: Path, expected: str, package: str = "") -> str:
    """Hashes a downloaded wheel and compares it to the pinned digest.

    Args:
        wheel (Path): The file to hash.
        expected (str): The digest to require, lowercase hex.
        package (str): Package name, used in the error.

    Returns:
        str: The digest that was calculated.

    Raises:
        PackageError: When the digest does not match.
    """
    digest = hashlib.sha256()
    with wheel.open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            digest.update(chunk)

    actual = digest.hexdigest()
    if actual.lower() != expected.lower():
        raise PackageError(
            f"Checksum mismatch for {wheel.name}. "
            + f"Expected {expected[:12]}..., got {actual[:12]}...",
            package,
        )
    return actual


def _check_record(archive: zipfile.ZipFile, package: str) -> None:
    """Requires RECORD to list exactly the files the archive actually holds.

    A wheel whose RECORD disagrees with its contents has been repacked, so it is refused even when
    every member is otherwise inside the allowlist.

    Args:
        archive (zipfile.ZipFile): The opened wheel.
        package (str): Package name, used in the error.

    Raises:
        PackageError: When RECORD is missing, duplicated, or inconsistent.
    """

    def normalize(name: str) -> str:
        """Both sides of the comparison agree on posix form, trailing slash dropped."""
        return PurePosixPath(name).as_posix()

    raw = {info.filename for info in archive.infolist()}
    all_names = {normalize(name) for name in raw}
    names = {normalize(name) for name in raw if not name.endswith("/")}
    records = [name for name in names if PurePosixPath(name).name == RECORD_NAME]
    if len(records) != 1:
        raise PackageError(
            f"Expected exactly one {RECORD_NAME} in wheel, found {len(records)}", package
        )
    record_path = records[0]
    dist_info = record_path.rsplit("/", 1)[0]

    listed: set[str] = set()
    with archive.open(record_path) as handle:
        text = handle.read().decode("utf-8", "replace")
    for row in csv.reader(io.StringIO(text)):
        if row:
            listed.add(normalize(row[0]))

    def is_self_describing(name: str) -> bool:
        """True for RECORD and its detached signatures, which never list themselves."""
        leaf = PurePosixPath(name).name
        return (
            name.startswith(f"{dist_info}/")
            and leaf.startswith(RECORD_NAME)
            and (leaf == RECORD_NAME or leaf[len(RECORD_NAME) :] in RECORD_SIGNATURE_SUFFIXES)
        )

    present = names - {n for n in names if is_self_describing(n)}

    unrecorded = present - listed
    if unrecorded:
        raise PackageError(
            f"Wheel holds files absent from {RECORD_NAME}: {sorted(unrecorded)[:3]}", package
        )
    # A listed directory entry is fine even though nothing is written for it.
    absent = {name for name in listed - all_names if name != record_path}
    if absent:
        raise PackageError(
            f"{RECORD_NAME} lists files the wheel does not hold: {sorted(absent)[:3]}", package
        )


def extract_wheel(
    wheel: Path, destination: Path, allowed_top_level: frozenset[str], package: str = ""
) -> tuple[str, ...]:
    """Unpacks a verified wheel into a fresh directory, rejecting anything unsafe.

    Args:
        wheel (Path): The wheel to unpack.
        destination (Path): Directory to create and fill. Must not already exist.
        allowed_top_level (frozenset[str]): The only top level entries permitted.
        package (str): Package name, used in the error.

    Returns:
        tuple[str, ...]: The importable top level names that were written.

    Raises:
        PackageError: When the wheel is malformed or tries to write outside ``destination``.
    """
    destination.mkdir(parents=True)
    root = destination.resolve()
    written: set[str] = set()

    with zipfile.ZipFile(wheel) as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]

        # Vet every path before trusting any of them, and before writing anything.
        for info in members:
            name = info.filename
            if not _safe(name):
                raise PackageError(f"Refusing unsafe path in wheel: {name!r}", package)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise PackageError(f"Refusing symlink in wheel: {name!r}", package)

        _check_record(archive, package)

        for info in members:
            name = info.filename
            head = name.split("/", 1)[0]
            if head not in allowed_top_level:
                raise PackageError(
                    f"Refusing unexpected top level entry in wheel: {head!r}", package
                )

            target = (destination / PurePosixPath(name)).resolve()
            if not target.is_relative_to(root):
                raise PackageError(f"Refusing path outside destination: {name!r}", package)

            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as dst:
                while chunk := src.read(CHUNK_SIZE):
                    _ = dst.write(chunk)
            written.add(head)

    return tuple(sorted(written))


@dataclass(frozen=True)
class InstalledPackage:
    """What the application knows about a module it unpacked earlier."""

    name: str
    version: str
    import_name: str
    sha256: str
    installed_at: str
    top_level: tuple[str, ...] = field(default_factory=tuple)
    directory: str = ""
    "Where it was unpacked, recorded so a moved install root can be found again."

    def to_json(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        data = asdict(self)
        data["top_level"] = list(self.top_level)
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "InstalledPackage":  # pyright: ignore[reportExplicitAny]
        return cls(
            name=str(data["name"]),  # pyright: ignore[reportAny]
            version=str(data["version"]),  # pyright: ignore[reportAny]
            import_name=str(data["import_name"]),  # pyright: ignore[reportAny]
            sha256=str(data["sha256"]),  # pyright: ignore[reportAny]
            installed_at=str(data["installed_at"]),  # pyright: ignore[reportAny]
            top_level=tuple(data.get("top_level") or ()),
            directory=str(data.get("directory") or ""),
        )

    def resolve(self, root: Path) -> Path:
        """Directory this package lives in, preferring the recorded location."""
        if self.directory:
            return Path(self.directory)
        return module_dir(self.name, self.version, root)


def read_index(root: Path | None = None) -> dict[str, InstalledPackage]:
    """Reads the install index. A missing or damaged index reads as empty."""
    path = index_path(root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
    except (OSError, ValueError) as e:
        logger.warning("Ignoring unreadable install index %s: %s", path, e)
        return {}
    if data.get("schema") != INDEX_SCHEMA:  # pyright: ignore[reportAny]
        logger.warning("Ignoring install index %s: unknown schema %r", path, data.get("schema"))  # pyright: ignore[reportAny]
        return {}
    return {
        name: InstalledPackage.from_json(entry)  # pyright: ignore[reportAny]
        for name, entry in data.get("packages", {}).items()  # pyright: ignore[reportAny]
    }


def write_index(index: dict[str, InstalledPackage], root: Path | None = None) -> None:
    """Writes the install index, replacing it atomically."""
    path = index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": INDEX_SCHEMA,
        "updated_at": datetime.now(UTC).isoformat(),
        "packages": {name: record.to_json() for name, record in index.items()},
    }
    tmp = path.with_name(f"{path.name}.tmp")
    _ = tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _ = tmp.replace(path)


def new_record(
    name: str,
    version: str,
    import_name: str,
    sha256: str,
    top_level: tuple[str, ...],
    directory: Path,
) -> InstalledPackage:
    """Builds the index entry for a freshly installed module."""
    return InstalledPackage(
        name=name,
        version=version,
        import_name=import_name,
        sha256=sha256,
        installed_at=datetime.now(UTC).isoformat(),
        top_level=top_level,
        directory=str(directory),
    )
