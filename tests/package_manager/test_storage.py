"""Tests for where modules live on disk and how a wheel becomes a module.

The extraction tests are the important ones: a wheel is a zip, and a zip is allowed to name its
members anything at all.
"""

import stat
import sys
import zipfile
from pathlib import Path

import pytest
from _fakes import (  # pyright: ignore[reportImplicitRelativeImport]
    ALLOWED_TOP_LEVEL,
    MEMBERS,
    WHEEL_NAME,
    build_wheel,
    digest_of,
    make_record,
)

from package_manager import PackageError
from package_manager._storage import (
    INDEX_SCHEMA,
    InstalledPackage,
    cache_dir,
    extract_wheel,
    index_path,
    module_dir,
    modules_root,
    read_index,
    verify_sha256,
    write_index,
)

# region paths


def test_modules_root_honours_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROSPERO_MODULES_PATH", str(tmp_path / "somewhere"))

    assert modules_root() == tmp_path / "somewhere"


def test_modules_root_defaults_per_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROSPERO_MODULES_PATH", raising=False)

    if sys.platform == "win32":
        monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\tester\AppData\Local")
        root = modules_root()
        assert root.name == "modules"
        assert root.parent.name == "Prospero"
    else:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        assert modules_root() == Path.home() / ".local" / "share" / "prospero" / "modules"


def test_module_dir_is_name_and_version(tmp_path: Path) -> None:
    assert module_dir("pillow", "12.3.0", tmp_path).name == "pillow-12.3.0"


def test_cache_dir_sits_under_root(tmp_path: Path) -> None:
    assert cache_dir(tmp_path) == tmp_path / "cache"


def test_index_path_sits_under_root(tmp_path: Path) -> None:
    assert index_path(tmp_path) == tmp_path / "installed.json"


# endregion


# region checksum


def test_matching_digest_is_accepted(tmp_path: Path) -> None:
    wheel = tmp_path / WHEEL_NAME
    _ = wheel.write_bytes(b"payload")

    assert verify_sha256(wheel, digest_of(wheel)) == digest_of(wheel)


def test_wrong_digest_is_refused(tmp_path: Path) -> None:
    wheel = tmp_path / WHEEL_NAME
    _ = wheel.write_bytes(b"payload")

    with pytest.raises(PackageError) as e:
        _ = verify_sha256(wheel, "0" * 64, "pillow")

    assert "Checksum mismatch" in e.value.error_str
    assert e.value.package == "pillow"


def test_digest_comparison_ignores_case(tmp_path: Path) -> None:
    wheel = tmp_path / WHEEL_NAME
    _ = wheel.write_bytes(b"payload")

    assert verify_sha256(wheel, digest_of(wheel).upper())


# endregion


# region extraction


def test_wheel_is_unpacked(tmp_path: Path) -> None:
    wheel = build_wheel(tmp_path / WHEEL_NAME)
    dest = tmp_path / "out"

    written = extract_wheel(wheel, dest, ALLOWED_TOP_LEVEL, "pillow")

    assert set(written) == {"PIL", "pillow-12.3.0.dist-info"}
    assert (dest / "PIL" / "__init__.py").is_file()
    assert (dest / "pillow-12.3.0.dist-info" / "METADATA").is_file()


def test_unpacked_content_matches_the_archive(tmp_path: Path) -> None:
    wheel = build_wheel(tmp_path / WHEEL_NAME)
    dest = tmp_path / "out"

    _ = extract_wheel(wheel, dest, ALLOWED_TOP_LEVEL, "pillow")

    with zipfile.ZipFile(wheel) as archive:
        assert (dest / "PIL" / "ImageCms.py").read_bytes() == archive.read("PIL/ImageCms.py")


def test_empty_directories_are_skipped(tmp_path: Path) -> None:
    wheel = build_wheel(tmp_path / WHEEL_NAME, {"PIL/": b"", "PIL/__init__.py": b""})
    dest = tmp_path / "out"

    _ = extract_wheel(wheel, dest, ALLOWED_TOP_LEVEL, "pillow")

    assert (dest / "PIL" / "__init__.py").is_file()


@pytest.mark.parametrize(
    "member",
    [
        "../evil.py",
        "PIL/../../evil.py",
        "..\\evil.py",
        "/etc/evil.py",
        "C:/evil.py",
        "\\\\server\\share\\evil.py",
    ],
)
def test_paths_escaping_the_destination_are_refused(tmp_path: Path, member: str) -> None:
    wheel = build_wheel(tmp_path / WHEEL_NAME, {member: b"pwned"})

    with pytest.raises(PackageError) as e:
        _ = extract_wheel(wheel, tmp_path / "out", ALLOWED_TOP_LEVEL, "pillow")

    assert "Refusing" in e.value.error_str
    assert not (tmp_path / "evil.py").exists()


def test_unexpected_top_level_entry_is_refused(tmp_path: Path) -> None:
    wheel = build_wheel(tmp_path / WHEEL_NAME, {"PIL/__init__.py": b"", "evil/thing.py": b"x"})

    with pytest.raises(PackageError) as e:
        _ = extract_wheel(wheel, tmp_path / "out", ALLOWED_TOP_LEVEL, "pillow")

    assert "unexpected top level entry" in e.value.error_str
    assert not (tmp_path / "out" / "evil").exists()


def test_symlink_member_is_refused(tmp_path: Path) -> None:
    """A zip can carry a symlink, which would let a wheel write outside the root."""
    path = tmp_path / WHEEL_NAME
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("PIL/link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../../../elsewhere")

    with pytest.raises(PackageError) as e:
        _ = extract_wheel(path, tmp_path / "out", ALLOWED_TOP_LEVEL, "pillow")

    assert "symlink" in e.value.error_str


def test_damaged_archive_is_refused(tmp_path: Path) -> None:
    wheel = tmp_path / WHEEL_NAME
    _ = wheel.write_bytes(b"not a zip at all")

    with pytest.raises(zipfile.BadZipFile):
        _ = extract_wheel(wheel, tmp_path / "out", ALLOWED_TOP_LEVEL, "pillow")


def test_nothing_is_written_when_extraction_fails(tmp_path: Path) -> None:
    """A wheel that goes bad halfway must not leave half a module behind."""
    members = {"PIL/__init__.py": b"ok", "PIL/sub.py": b"ok", "evil/thing.py": b"x"}
    wheel = build_wheel(tmp_path / WHEEL_NAME, members)
    dest = tmp_path / "out"

    with pytest.raises(PackageError):
        _ = extract_wheel(wheel, dest, ALLOWED_TOP_LEVEL, "pillow")

    # The caller discards the staging directory, but nothing escaped it.
    assert not (tmp_path / "evil").exists()


# endregion


# region index


def test_index_round_trip(tmp_path: Path) -> None:
    record = InstalledPackage(
        name="pillow",
        version="12.3.0",
        import_name="PIL",
        sha256="a" * 64,
        installed_at="2026-01-01T00:00:00+00:00",
        top_level=("PIL",),
        directory=str(tmp_path / "pillow-12.3.0"),
    )

    write_index({"pillow": record}, tmp_path)
    read_back = read_index(tmp_path)

    assert read_back == {"pillow": record}


def test_missing_index_reads_as_empty(tmp_path: Path) -> None:
    assert read_index(tmp_path) == {}


def test_corrupt_index_reads_as_empty(tmp_path: Path) -> None:
    _ = index_path(tmp_path).write_text("{not json", encoding="utf-8")

    assert read_index(tmp_path) == {}


def test_unknown_schema_reads_as_empty(tmp_path: Path) -> None:
    _ = index_path(tmp_path).write_text('{"schema": 999, "packages": {}}', encoding="utf-8")

    assert read_index(tmp_path) == {}


def test_index_records_the_schema_it_wrote(tmp_path: Path) -> None:
    write_index({}, tmp_path)

    assert f'"schema": {INDEX_SCHEMA}' in index_path(tmp_path).read_text(encoding="utf-8")


def test_record_resolves_recorded_directory(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    record = InstalledPackage("pillow", "12.3.0", "PIL", "a" * 64, "now", (), str(elsewhere))

    assert record.resolve(tmp_path) == elsewhere


def test_record_falls_back_to_conventional_directory(tmp_path: Path) -> None:
    record = InstalledPackage("pillow", "12.3.0", "PIL", "a" * 64, "now")

    assert record.resolve(tmp_path) == tmp_path / "pillow-12.3.0"


def test_default_root_is_under_a_directory_named_after_the_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROSPERO_MODULES_PATH", raising=False)

    if sys.platform == "win32":
        monkeypatch.setenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        assert "Prospero" in str(modules_root())
    else:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        assert "prospero" in str(modules_root())


# endregion

# region record consistency


def test_a_wheel_whose_record_matches_extracts(tmp_path: Path) -> None:
    wheel = build_wheel(tmp_path / WHEEL_NAME)
    dest = tmp_path / "out"

    top_level = extract_wheel(wheel, dest, ALLOWED_TOP_LEVEL, "pillow")

    assert top_level == ("PIL", "pillow-12.3.0.dist-info")
    assert (dest / "PIL" / "ImageCms.py").is_file()


def test_a_file_missing_from_record_is_refused(tmp_path: Path) -> None:
    """A smuggled file inside an allowed directory is still a smuggled file."""
    wheel = build_wheel(
        tmp_path / WHEEL_NAME,
        {**MEMBERS, "PIL/smuggled.py": b"print('hello')\n"},
        record=make_record(MEMBERS),
    )

    with pytest.raises(PackageError) as e:
        _ = extract_wheel(wheel, tmp_path / "out", ALLOWED_TOP_LEVEL, "pillow")

    assert "absent from RECORD" in e.value.error_str
    assert not (tmp_path / "out" / "PIL" / "smuggled.py").exists()


def test_a_record_listing_a_missing_file_is_refused(tmp_path: Path) -> None:
    members = {**MEMBERS, "PIL/ghost.py": b""}
    wheel = build_wheel(
        tmp_path / WHEEL_NAME, members, record=make_record({**members, "PIL/phantom.py": b""})
    )

    with pytest.raises(PackageError) as e:
        _ = extract_wheel(wheel, tmp_path / "out", ALLOWED_TOP_LEVEL, "pillow")

    assert "does not hold" in e.value.error_str


def test_a_wheel_without_record_is_refused(tmp_path: Path) -> None:
    path = tmp_path / WHEEL_NAME
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in MEMBERS.items():
            archive.writestr(name, content)

    with pytest.raises(PackageError) as e:
        _ = extract_wheel(path, tmp_path / "out", ALLOWED_TOP_LEVEL, "pillow")

    assert "exactly one RECORD" in e.value.error_str


def test_a_wheel_with_two_records_is_refused(tmp_path: Path) -> None:
    """An ambiguous RECORD means there is no single source of truth to trust."""
    wheel = build_wheel(tmp_path / WHEEL_NAME, {**MEMBERS, "PIL/RECORD": b"PIL/__init__.py\n"})

    with pytest.raises(PackageError) as e:
        _ = extract_wheel(wheel, tmp_path / "out", ALLOWED_TOP_LEVEL, "pillow")

    assert "exactly one RECORD" in e.value.error_str


def test_a_detached_record_signature_does_not_have_to_list_itself(tmp_path: Path) -> None:
    """RECORD.jws and RECORD.p7s are unlisted by design, so they must not trip the check."""
    members = {**MEMBERS, "pillow-12.3.0.dist-info/RECORD.jws": b"signature"}
    wheel = build_wheel(tmp_path / WHEEL_NAME, members)
    dest = tmp_path / "out"

    top_level = extract_wheel(wheel, dest, ALLOWED_TOP_LEVEL, "pillow")

    assert "PIL" in top_level
    assert (dest / "pillow-12.3.0.dist-info" / "RECORD.jws").is_file()


# endregion
