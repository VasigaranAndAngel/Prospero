#!/usr/bin/env bash
#
# Install the unpacked Linux build of Prospero for the current user.
#
# Everything goes under the XDG directories, so no root is needed:
#   * the app itself          -> ${PROSPERO_INSTALL_DIR:-~/.local/opt/Prospero}
#   * a `prospero` symlink    -> ${XDG_BIN_HOME:-~/.local/bin}
#   * a desktop entry         -> ${XDG_DATA_HOME:-~/.local/share}/applications
#   * the app icon            -> .../icons/hicolor/256x256/apps/prospero.png
#
# Run it from the directory you extracted the tarball into, next to the `Prospero/` folder.
# Uninstall by deleting those four paths.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$here/Prospero"

if [[ ! -x "$app_dir/Prospero" ]]; then
    echo "error: could not find the packaged app at '$app_dir/Prospero'." >&2
    echo "       run this script from the extracted tarball root." >&2
    exit 1
fi

bin_dir="${XDG_BIN_HOME:-$HOME/.local/bin}"
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
apps_dir="$data_dir/applications"
icons_dir="$data_dir/icons/hicolor/256x256/apps"
install_root="${PROSPERO_INSTALL_DIR:-$HOME/.local/opt/Prospero}"

mkdir -p "$bin_dir" "$apps_dir" "$icons_dir" "$(dirname "$install_root")"

# Refresh the app next to the user's data, then link it into PATH.
rm -rf "$install_root"
cp -r "$app_dir" "$install_root"
ln -sf "$install_root/Prospero" "$bin_dir/prospero"

# Desktop entry (with the real Exec path) and icon, so it appears in the application menu.
install -m 644 "$here/prospero.desktop" "$apps_dir/prospero.desktop"
sed -i "s|@EXEC@|$bin_dir/prospero|g" "$apps_dir/prospero.desktop"

# PyInstaller 6 keeps app data in `_internal/`; older versions put it next to the executable.
for icon_src in \
    "$install_root/_internal/assets/icon/icon.png" \
    "$install_root/assets/icon/icon.png"; do
    if [[ -f "$icon_src" ]]; then
        install -m 644 "$icon_src" "$icons_dir/prospero.png"
        break
    fi
done

update-desktop-database "$apps_dir" 2>/dev/null || true
gtk-update-icon-cache -f -t "$data_dir/icons/hicolor" 2>/dev/null || true

echo "Prospero installed:"
echo "  binary:  $bin_dir/prospero"
echo "  desktop: $apps_dir/prospero.desktop"
if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
    echo
    echo "note: $bin_dir is not on your PATH. Add it to launch 'prospero' by name,"
    echo "      or start it from your application menu." fi
