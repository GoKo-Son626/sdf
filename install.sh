#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
install_root=${SDF_INSTALL_ROOT:-"$data_home/sdf-translator/app"}
bin_dir=${SDF_BIN_DIR:-"$HOME/.local/bin"}
skip_deps=false
skip_hotkey=false
assume_yes=false

require_safe_path() {
  local target=$1
  case "$target" in
    ""|/|"$HOME")
      echo "Refusing unsafe install path: $target" >&2
      exit 2
      ;;
  esac
}

usage() {
  echo "Usage: ./install.sh [--yes] [--skip-deps] [--skip-hotkey]"
}

for arg in "$@"; do
  case "$arg" in
    --yes|-y) assume_yes=true ;;
    --skip-deps) skip_deps=true ;;
    --skip-hotkey) skip_hotkey=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -f /etc/arch-release ]]; then
  echo "This installer currently supports Arch Linux only." >&2
  echo "The source layout is distro-neutral; Ubuntu and other installers will be added later." >&2
  exit 1
fi

install_arch_dependencies() {
  local packages=(python wl-clipboard zenity libnotify)
  local missing=()
  mapfile -t missing < <(pacman -T "${packages[@]}" 2>/dev/null || true)
  ((${#missing[@]} == 0)) && return 0
  if "$skip_deps"; then
    echo "Missing packages (dependency installation skipped): ${missing[*]}" >&2
    return 1
  fi
  echo "Missing Arch packages: ${missing[*]}"
  if ! "$assume_yes"; then
    read -r -p "Install them with pacman? [Y/n] " answer
    [[ ${answer:-Y} =~ ^[Yy]$ ]] || exit 1
  fi
  sudo pacman -S --needed "${missing[@]}"
}

install_arch_dependencies

require_safe_path "$install_root"
install -d "$install_root/src" "$bin_dir" "$config_home/sdf-translator"
rm -rf "$install_root/src/sdf_translate"
cp -a "$project_root/src/sdf_translate" "$install_root/src/"
find "$install_root" -type d -name __pycache__ -prune -exec rm -rf {} +
install -m 755 "$project_root/packaging/bin/sdf" "$bin_dir/sdf"
install -m 755 "$project_root/packaging/bin/sdf-global" "$bin_dir/sdf-global"

if [[ ! -f "$config_home/sdf-translator/config.env" ]]; then
  install -m 600 "$project_root/config.example" \
    "$config_home/sdf-translator/config.example"
fi

if ! "$skip_hotkey" && [[ -f "$config_home/niri/config.kdl" ]]; then
  python3 "$project_root/scripts/configure_niri.py" \
    --config "$config_home/niri/config.kdl" \
    --command "$bin_dir/sdf-global"
fi

case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) echo "Add $bin_dir to PATH before using sdf." ;;
esac

echo "SDF Translator installed successfully."
echo "Run: sdf --setup"
