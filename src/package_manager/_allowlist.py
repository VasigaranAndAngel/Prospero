"""The allowlist of optional modules this application is willing to install.

This is deliberately not a general purpose package installer. Only packages listed here can be
installed, only at the pinned version, and only when the wheel matches the interpreter that is
running. The expected SHA-256 of every wheel is hard coded, so a tampered download or a hijacked
index is rejected even if PyPI itself were compromised.

To add a package, add an :class:`AllowedPackage` with a wheel entry for every platform the
application supports, and get the hashes from
``https://pypi.org/pypi/<name>/json``.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final

from packaging.specifiers import SpecifierSet
from packaging.tags import Tag, parse_tag, sys_tags
from packaging.utils import canonicalize_name
from packaging.version import Version

__all__ = [
    "ALLOWLIST",
    "AllowedPackage",
    "AllowedWheel",
    "PackageError",
    "allowed_import_names",
    "get_allowed",
    "select_wheel",
]


class PackageError(Exception):
    """A module could not be resolved, installed, verified or removed.

    Signals rather than crashes, because every failure here is recoverable: the application simply
    carries on without the optional feature.
    """

    def __init__(self, error_str: str, package: str = "") -> None:
        super().__init__(error_str)
        self.error_str: str = error_str
        self.package: str = package


@dataclass(frozen=True)
class AllowedWheel:
    """One vetted wheel build of an allowed package."""

    filename: str
    "Exact wheel filename. Its tags decide whether it fits the interpreter."
    sha256: str
    "Expected SHA-256 of the file, as advertised on the index."
    size: int
    url: str
    "Where to download it from."
    requires_python: str = ""
    "Spec set this wheel claims to support, if the index said so."

    @property
    def platform_tags(self) -> frozenset[Tag]:
        """The compatibility tags this wheel claims, read from its filename."""
        parts = self.filename.removesuffix(".whl").split("-")
        if len(parts) < 3:
            return frozenset()
        return parse_tag("-".join(parts[-3:]))


@dataclass(frozen=True)
class AllowedPackage:
    """An optional module, pinned to one version and a known set of wheels."""

    name: str
    "Distribution name as it appears on the index."
    import_name: str
    "Top level name the package makes importable, e.g. ``PIL`` for ``pillow``."
    version: str
    "The only version this application will install."
    summary: str
    "Shown to the user when explaining what the module is for."
    provides: str
    "Which feature of the application needs it."
    wheels: dict[str, AllowedWheel] = field(default_factory=dict)
    "Vetted wheels, keyed by the platform tag they target."

    @property
    def canonical_name(self) -> str:
        return canonicalize_name(self.name)

    @property
    def dist_info(self) -> str:
        "Top level directory the wheel's metadata lands in."
        return f"{self.canonical_name.replace('-', '_')}-{self.version}.dist-info"

    @property
    def allowed_top_level(self) -> frozenset[str]:
        """Every top level entry a matching wheel is allowed to create."""
        return frozenset({self.import_name, self.dist_info})


PILLOW: Final[AllowedPackage] = AllowedPackage(
    name="pillow",
    import_name="PIL",
    version="12.3.0",
    summary="Image handling. Used here only for ICC colour profile conversion.",
    provides="Colour profile conversion in the colour calculator.",
    wheels={
        "win_amd64": AllowedWheel(
            filename="pillow-12.3.0-cp312-cp312-win_amd64.whl",
            sha256="a2b55dd6b2a4c4b7d87ffa56bdb33fdc5fdb9a462173861a7bc097f17d91cb09",
            size=7227137,
            url=(
                "https://files.pythonhosted.org/packages/45/89/"
                "da2f7971a317f83d807fdd4065c0af40208e59e692cc43d315a71a0e96d1/"
                "pillow-12.3.0-cp312-cp312-win_amd64.whl"
            ),
            requires_python=">=3.10",
        ),
    },
)

ALLOWLIST: Final[dict[str, AllowedPackage]] = {p.canonical_name: p for p in (PILLOW,)}

_BY_IMPORT_NAME: Final[dict[str, AllowedPackage]] = {p.import_name: p for p in ALLOWLIST.values()}


def get_allowed(name: str) -> AllowedPackage:
    """Looks up an allowed package by distribution or import name.

    Args:
        name (str): Distribution name such as ``pillow``, or import name ``PIL``.

    Raises:
        PackageError: When the package is not on the allowlist.
    """
    key = canonicalize_name(name)
    if (package := ALLOWLIST.get(key)) is not None:
        return package
    if (package := _BY_IMPORT_NAME.get(name)) is not None:
        return package

    raise PackageError(
        f"'{name}' is not an installable module. Allowed: {', '.join(sorted(ALLOWLIST))}.",
        name,
    )


def select_wheel(package: AllowedPackage, tags: Iterable[Tag] | None = None) -> AllowedWheel | None:
    """Picks the vetted wheel that fits the running interpreter.

    Args:
        package (AllowedPackage): The package to choose a wheel for.
        tags (Iterable[Tag] | None): Tags to match against, defaulting to the
            tags of the running interpreter.

    Returns:
        AllowedWheel | None: The wheel, or None when none of the vetted wheels fit.
    """
    if tags is None:
        usable = frozenset(sys_tags())
    else:
        usable = frozenset(tags)

    version = Version(package.version)
    for wheel in package.wheels.values():
        if not (wheel.platform_tags & usable):
            continue
        if wheel.requires_python and not (version in SpecifierSet(wheel.requires_python)):
            continue
        return wheel
    return None


def allowed_import_names() -> tuple[str, ...]:
    """Top level import names the allowlist can provide."""
    return tuple(p.import_name for p in ALLOWLIST.values())
