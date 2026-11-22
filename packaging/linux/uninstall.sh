#!/usr/bin/env bash
#
# Uninstall a current-user Linux installation of Prospero.
#
# The installer records the exact paths it used in install-paths.env next to this
# script, so custom XDG directories and PROSPERO_INSTALL_ROOT are handled without
# guessing. User configuration and application data are preserved unless
# --purge-data is passed.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: uninstall.sh [options]

Options:
  --yes          Do not ask for confirmation.
  --gui          Ask for confirmation with kdialog/zenity (used by the desktop action).
  --purge-data   Also remove ~/.config/Prospero and the Prospero data directory.
  --force        Continue even if Prospero appears to be running.
  -h, --help     Show this help.

By default the uninstaller keeps settings and application data.
EOF
}

YES=0
GUI=0
PURGE_DATA=0
FORCE=0
while (($#)); do
    case "$1" in
        --yes|-y) YES=1 ;;
        --gui) GUI=1 ;;
        --purge-data) PURGE_DATA=1 ;;
        --force) FORCE=1 ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option '$1'." >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

script_path="${BASH_SOURCE[0]}"
if command -v readlink >/dev/null 2>&1; then
    resolved="$(readlink -f -- "$script_path" 2>/dev/null || true)"
    [[ -n "$resolved" ]] && script_path="$resolved"
fi
install_root="$(cd -- "$(dirname -- "$script_path")" && pwd -P)"

manifest="$install_root/install-paths.env"
if [[ ! -f "$manifest" ]]; then
    echo "error: '$manifest' is missing." >&2
    echo "       run the uninstaller from the Prospero installation directory." >&2
    exit 1
fi

# shellcheck source=/dev/null
source "$manifest"

if [[ -n "${PROSPERO_INSTALL_ROOT:-}" && "$PROSPERO_INSTALL_ROOT" != "$install_root" ]]; then
    echo "error: install root mismatch: manifest says '$PROSPERO_INSTALL_ROOT'," >&2
    echo "       but the uninstaller is in '$install_root'." >&2
    exit 1
fi

bin_dir="${PROSPERO_BIN_DIR:-${XDG_BIN_HOME:-$HOME/.local/bin}}"
data_dir="${PROSPERO_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}}"
desktop_file="${PROSPERO_DESKTOP_FILE:-$data_dir/applications/prospero.desktop}"
icon_file="${PROSPERO_ICON_FILE:-$data_dir/icons/hicolor/256x256/apps/prospero.png}"

if [[ -z "$install_root" || "$install_root" == / || "$install_root" == "$HOME" ]]; then
    echo "error: refusing to uninstall from unsafe root '$install_root'." >&2
    exit 1
fi
if [[ ! -d "$install_root/versions" && ! -f "$install_root/current.txt" && ! -L "$install_root/current" ]]; then
    echo "error: '$install_root' does not look like a Prospero installation." >&2
    exit 1
fi

confirm_terminal() {
    if (( YES )); then
        return 0
    fi
    if [[ ! -t 0 ]]; then
        echo "error: no terminal for confirmation; re-run with --yes." >&2
        return 1
    fi
    local reply
    read -r -p "Uninstall Prospero from $install_root? [y/N] " reply
    [[ "$reply" == [yY] || "$reply" == [yY][eE][sS] ]]
}

confirm_gui() {
    if (( YES )); then
        return 0
    fi
    local question="Uninstall Prospero from $install_root? User settings will be kept."
    if command -v kdialog >/dev/null 2>&1; then
        kdialog --yesno "$question"
        return $?
    fi
    if command -v zenity >/dev/null 2>&1; then
        zenity --question --title="Uninstall Prospero" --text="$question"
        return $?
    fi
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "Prospero uninstaller" \
            "No GUI confirmation tool found. Run the uninstaller from a terminal." || true
    fi
    echo "error: need kdialog or zenity for --gui; run from a terminal instead." >&2
    return 1
}

if (( GUI )); then
    confirm_gui || exit 1
else
    confirm_terminal || exit 1
fi

if (( ! FORCE )) && command -v pgrep >/dev/null 2>&1; then
    if pgrep -f -- "$install_root/versions/" >/dev/null 2>&1; then
        echo "error: Prospero appears to be running from '$install_root'." >&2
        echo "       close it and try again, or pass --force." >&2
        exit 1
    fi
fi

# Only remove the launcher if it is the symlink this installer created.
if [[ -L "$bin_dir/prospero" ]]; then
    link_target="$(readlink -- "$bin_dir/prospero")"
    case "$link_target" in
        "$install_root"/*)
            rm -f -- "$bin_dir/prospero"
            ;;
        *)
            echo "warning: '$bin_dir/prospero' points to '$link_target'; leaving it alone." >&2
            ;;
    esac
elif [[ -e "$bin_dir/prospero" ]]; then
    echo "warning: '$bin_dir/prospero' is not a symlink; leaving it alone." >&2
fi

if [[ -f "$desktop_file" ]] && grep -q '^Name=Prospero$' "$desktop_file"; then
    rm -f -- "$desktop_file"
elif [[ -e "$desktop_file" ]]; then
    echo "warning: '$desktop_file' is not a Prospero desktop entry; leaving it alone." >&2
fi

if [[ -f "$icon_file" ]]; then
    rm -f -- "$icon_file"
fi

if (( PURGE_DATA )); then
    config_dir="$HOME/.config/Prospero"
    app_data_dir="$data_dir/prospero"
    rm -rf -- "$config_dir" "$app_data_dir"
fi

rm -rf -- "$install_root"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$data_dir/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$data_dir/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Prospero uninstalled from $install_root."
if (( PURGE_DATA )); then
    echo "User configuration and data were removed."
else
    echo "User configuration and data were kept."
    echo "Re-run with --purge-data to remove them."
fi
