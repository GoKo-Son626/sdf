#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
install_root=${SDF_INSTALL_ROOT:-"$data_home/sdf-translator/app"}
bin_dir=${SDF_BIN_DIR:-"$HOME/.local/bin"}
skip_deps=false
skip_hotkey=false
skip_editor=false
assume_yes=false

require_safe_path() {
  local target=$1
  case "$target" in
    ""|/|"$HOME")
      echo "拒绝使用不安全的安装路径：$target" >&2
      exit 2
      ;;
  esac
}

usage() {
  echo "用法：./install.sh [--yes] [--skip-deps] [--skip-hotkey] [--skip-editor]"
}

for arg in "$@"; do
  case "$arg" in
    --yes|-y) assume_yes=true ;;
    --skip-deps) skip_deps=true ;;
    --skip-hotkey) skip_hotkey=true ;;
    --skip-editor) skip_editor=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "未知选项：$arg" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -f /etc/arch-release ]]; then
  echo "当前安装器仅支持 Arch Linux。" >&2
  echo "源码布局与发行版无关；Ubuntu 等发行版安装器将在后续添加。" >&2
  exit 1
fi

install_arch_dependencies() {
  local packages=(python wl-clipboard zenity libnotify)
  local missing=()
  mapfile -t missing < <(pacman -T "${packages[@]}" 2>/dev/null || true)
  ((${#missing[@]} == 0)) && return 0
  if "$skip_deps"; then
    echo "缺少软件包（已跳过依赖安装）：${missing[*]}" >&2
    return 1
  fi
  echo "缺少 Arch 软件包：${missing[*]}"
  if ! "$assume_yes"; then
    read -r -p "是否使用 pacman 安装？[是/否，默认是] " answer
    [[ ${answer:-Y} =~ ^([Yy]|是)$ ]] || exit 1
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

if [[ ! -f "$config_home/sdf-translator/config.env" && -f "$project_root/config.env" ]]; then
  # 从源码运行方式迁移时，保留现有配置。
  install -m 600 "$project_root/config.env" \
    "$config_home/sdf-translator/config.env"
elif [[ ! -f "$config_home/sdf-translator/config.env" ]]; then
  install -m 600 "$project_root/config.example" \
    "$config_home/sdf-translator/config.example"
fi

if ! "$skip_editor"; then
  if command -v nvim >/dev/null 2>&1; then
    install -Dm644 "$project_root/editor/nvim/sdf-selection.lua" \
      "$config_home/nvim/plugin/sdf-selection.lua"
  fi
  if command -v vim >/dev/null 2>&1; then
    install -Dm644 "$project_root/editor/vim/sdf-selection.vim" \
      "$HOME/.vim/plugin/sdf-selection.vim"
  fi
fi

if ! "$skip_hotkey" && [[ -f "$config_home/niri/config.kdl" ]]; then
  python3 "$project_root/scripts/configure_niri.py" \
    --config "$config_home/niri/config.kdl" \
    --command "$bin_dir/sdf-global"
fi

case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) echo "使用 sdf 前，请将 $bin_dir 加入 PATH。" ;;
esac

echo "SDF 翻译工具安装成功。"
echo "首次配置请运行：sdf --setup"
