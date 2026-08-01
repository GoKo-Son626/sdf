#!/usr/bin/env bash
set -euo pipefail

data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
state_home=${XDG_STATE_HOME:-"$HOME/.local/state"}
install_root=${SDF_INSTALL_ROOT:-"$data_home/sdf-translator/app"}
bin_dir=${SDF_BIN_DIR:-"$HOME/.local/bin"}
purge=false

[[ ${1:-} == "--purge" ]] && purge=true

require_safe_path() {
  local target=$1
  case "$target" in
    ""|/|"$HOME")
      echo "Refusing unsafe removal path: $target" >&2
      exit 2
      ;;
  esac
}

require_safe_path "$install_root"
require_safe_path "$config_home/sdf-translator"
require_safe_path "$data_home/sdf-translator"
require_safe_path "$state_home/sdf-translator"

rm -f "$bin_dir/sdf" "$bin_dir/sdf-global"
rm -f "$config_home/nvim/plugin/sdf-selection.lua" \
  "$HOME/.vim/plugin/sdf-selection.vim"
rm -rf "$install_root"

if "$purge"; then
  rm -rf "$config_home/sdf-translator" \
    "$data_home/sdf-translator" \
    "$state_home/sdf-translator"
  echo "SDF Translator and user data removed."
else
  echo "SDF Translator removed; user configuration and vocabulary were preserved."
fi
