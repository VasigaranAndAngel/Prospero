#!/usr/bin/env bash
#
# Install the unpacked Linux build of Prospero for the current user.
#
# The app is installed as an immutable, versioned directory:
#
#   ~/.local/opt/prospero/versions/<version>/Prospero/
#   ~/.local/opt/prospero/current -> versions/<version>/Prospero
#   ~/.local/opt/prospero/current.txt
#
# A stable `prospero` symlink points at `current/Prospero`, so shortcuts and autostart
# entries never need to know which version is installed.
#
# Run this script from the directory you extracted the tarball into, next to `Prospero/`.
# Uninstall with `uninstall.sh` in the install root (also exposed as a desktop action).

set -euo pipefail

escape_sed_replacement() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//|/\\|}"
    value="${value//&/\\&}"
    printf '%s' "$value"
}

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$here/Prospero"

if [[ ! -x "$app_dir/Prospero" ]]; then
    echo "error: could not find the packaged app at '$app_dir/Prospero'." >&2
    echo "       run this script from the extracted tarball root." >&2
    exit 1
fi
if [[ ! -f "$here/uninstall.sh" ]]; then
    echo "error: could not find '$here/uninstall.sh'." >&2
    echo "       run this script from the extracted tarball root." >&2
    exit 1
fi

version="${PROSPERO_VERSION:-}"
if [[ -z "$version" && -f "$here/VERSION" ]]; then
    version="$(tr -d '[:space:]' < "$here/VERSION")"
fi
if [[ -z "$version" ]]; then
    version="$("$app_dir/Prospero" --version 2>/dev/null | head -n 1 || true)"
fi
version="${version#v}"
case "$version" in
    ""|*/*|*\\*|*..*|*[!A-Za-z0-9._+!-]*)
        echo "error: could not determine a safe version string (got '$version')." >&2
        exit 1
        ;;
esac

bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
apps_dir="$data_dir/applications"
icons_dir="$data_dir/icons/hicolor/256x256/apps"
desktop_file="$apps_dir/prospero.desktop"
icon_file="$icons_dir/prospero.png"
install_root="${PROSPERO_INSTALL_ROOT:-$HOME/.local/opt/prospero}"
versions_dir="$install_root/versions"
version_dir="$versions_dir/$version"
staging="$versions_dir/.staging-$version-$$"

mkdir -p "$bin_dir" "$apps_dir" "$icons_dir" "$versions_dir"
rm -rf "$versions_dir"/.staging-*

install -m 755 "$here/uninstall.sh" "$install_root/uninstall.sh"

previous=""
if [[ -f "$install_root/current.txt" ]]; then
    previous="$(tr -d '[:space:]' < "$install_root/current.txt" || true)"
fi
if [[ -z "$previous" && -L "$install_root/current" ]]; then
    previous="$(readlink "$install_root/current" || true)"
    previous="${previous#versions/}"
    previous="${previous%%/*}"
fi

# Build the version directory off to the side, then rename it into place.
rm -rf "$staging"
mkdir -p "$staging"
cp -a "$app_dir" "$staging/Prospero"
chmod +x "$staging/Prospero/Prospero"

rm -rf "$version_dir"
mv "$staging" "$version_dir"

# Switch the stable pointer only after the new version is complete.
rm -rf "$install_root/current.tmp"
ln -sfn "versions/$version/Prospero" "$install_root/current.tmp"
mv -Tf "$install_root/current.tmp" "$install_root/current"
printf '%s\n' "$version" > "$install_root/current.txt.tmp"
mv -f "$install_root/current.txt.tmp" "$install_root/current.txt"
if [[ -n "$previous" && "$previous" != "$version" ]]; then
    printf '%s\n' "$previous" > "$install_root/previous.txt.tmp"
    mv -f "$install_root/previous.txt.tmp" "$install_root/previous.txt"
fi

# Record the exact paths used so the uninstaller does not have to guess.
{
    printf 'PROSPERO_INSTALL_ROOT=%q\n' "$install_root"
    printf 'PROSPERO_BIN_DIR=%q\n' "$bin_dir"
    printf 'PROSPERO_DATA_DIR=%q\n' "$data_dir"
    printf 'PROSPERO_DESKTOP_FILE=%q\n' "$desktop_file"
    printf 'PROSPERO_ICON_FILE=%q\n' "$icon_file"
} > "$install_root/install-paths.env.tmp"
mv -f "$install_root/install-paths.env.tmp" "$install_root/install-paths.env"

# Keep the version currently selected and the one before it; remove the rest.
for candidate in "$versions_dir"/*; do
    [[ -d "$candidate" ]] || continue
    name="$(basename "$candidate")"
    if [[ "$name" == "$version" || "$name" == "$previous" ]]; then
        continue
    fi
    rm -rf "$candidate"
done

# Stable entry point on PATH. It resolves through `current` on every launch.
ln -sfn "$install_root/current/Prospero" "$bin_dir/prospero"

# Desktop entry (with real Exec paths), so it appears in the application menu.
install -m 644 "$here/prospero.desktop" "$desktop_file"
escaped_bin="$(escape_sed_replacement "$bin_dir/prospero")"
escaped_uninstall="$(escape_sed_replacement "$install_root/uninstall.sh")"
sed -i \
    -e "s|@EXEC@|\"$escaped_bin\"|g" \
    -e "s|@UNINSTALL@|\"$escaped_uninstall\"|g" \
    "$desktop_file"

# PyInstaller 6 keeps app data in `_internal/`; older versions put it next to the executable.
for icon_src in \
    "$install_root/current/_internal/assets/icon/icon.png" \
    "$install_root/current/assets/icon/icon.png"; do
    if [[ -f "$icon_src" ]]; then
        install -m 644 "$icon_src" "$icon_file"
        break
    fi
done

update-desktop-database "$apps_dir" 2>/dev/null || true
gtk-update-icon-cache -f -t "$data_dir/icons/hicolor" 2>/dev/null || true

echo "Prospero $version installed:"
echo "  root:       $install_root"
echo "  binary:     $bin_dir/prospero"
echo "  desktop:    $desktop_file"
echo "  uninstall:  $install_root/uninstall.sh"
echo
echo "To uninstall, run '$install_root/uninstall.sh' or choose"
echo "'Uninstall Prospero' from Prospero's application-menu context menu."
if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
    echo
    echo "note: $bin_dir is not on your PATH. Add it to launch 'prospero' by name,"
    echo "      or start it from your application menu."
fi
