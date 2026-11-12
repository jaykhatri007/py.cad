#!/usr/bin/env bash
# Installs distribution packages with apt and Python packages in .venv-linux.
set -euo pipefail
pycad_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
pycad_system=1
pycad_system_only=0
pycad_desktop=1
pycad_apt_options=()
pycad_options=(--setup-only)
for pycad_argument in "$@"; do
    case "$pycad_argument" in
        --no-system-packages) pycad_system=0 ;;
        --system-only) pycad_system_only=1 ;;
        --no-desktop) pycad_desktop=0 ;;
        --with-3d) pycad_options+=(--with-3d) ;;
        --yes) pycad_apt_options+=(-y) ;;
        --help|-h)
            echo 'Usage: bash setup_ubuntu.sh [--with-3d] [--no-desktop] [--no-system-packages] [--system-only] [--yes]'
            echo 'Run as your normal Ubuntu desktop user. sudo is used only for apt.'
            echo 'Default: install Ubuntu runtime libraries, prepare .venv-linux, add PY.cad to Applications.'
            echo '--system-only installs only apt dependencies; --yes accepts apt package prompts.'
            exit 0 ;;
        *) echo "Unknown option: $pycad_argument" >&2; exit 2 ;;
    esac
done
if [[ $EUID == 0 && $pycad_system_only == 0 ]]; then
    echo 'Run this script as your normal desktop user, without sudo. It requests sudo for apt when needed.' >&2
    exit 1
fi
if [[ $pycad_system == 1 ]]; then
    if ! command -v apt-get >/dev/null; then
        echo 'This setup script needs Ubuntu/Debian apt. Install equivalent Qt runtime libraries, then use --no-system-packages.' >&2
        exit 1
    fi
    pycad_packages=(python3 python3-venv python3-pip libgl1 libegl1 libopengl0
        libfontconfig1 libfreetype6 libx11-xcb1 libxkbcommon-x11-0
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
        libxcb-render-util0 libxcb-xinerama0 libxcb-randr0 libxcb-shape0
        libxcb-xfixes0 libxcb-xkb1 libsm6 libice6 libxrender1
        libwayland-client0 libwayland-cursor0 libwayland-egl1 xwayland)
    # Resolute Raccoon (Ubuntu 26.04) uses Python 3.14. Request its explicit
    # venv package when the repository exposes it; this keeps setup reliable
    # even if the generic python3 metapackage is temporarily out of sync.
    if [[ -f /etc/os-release ]] && grep -q 'VERSION_ID="26.04"' /etc/os-release \
        && apt-cache show python3.14-venv >/dev/null 2>&1; then
        pycad_packages+=(python3.14 python3.14-venv)
    fi
    pycad_privilege=()
    if [[ $EUID != 0 ]]; then pycad_privilege=(sudo); fi
    "${pycad_privilege[@]}" apt-get update
    "${pycad_privilege[@]}" apt-get install "${pycad_apt_options[@]}" "${pycad_packages[@]}"
fi
if [[ $pycad_system_only == 1 ]]; then exit 0; fi
if [[ $pycad_desktop == 1 ]]; then pycad_options+=(--install-desktop); fi
bash "$pycad_root/start.sh" "${pycad_options[@]}"
echo 'Setup complete. Open PY.cad from Applications, or run: bash start.sh'
