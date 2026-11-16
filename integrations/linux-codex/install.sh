#!/usr/bin/env bash
set -euo pipefail
umask 077
here=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$here/platform.sh"
if [[ $(uname -s) != Linux ]]; then echo '请在 Linux 电脑运行此安装包。' >&2; exit 1; fi
source /etc/os-release
platform=$(tokenbots_platform "$ID" "${VERSION_ID:-rolling}" "$(uname -m)")
printf 'TokenBots Linux 安装器：%s %s / %s\n' "$ID" "${VERSION_ID:-rolling}" "$platform"
mode=${1:-install}
case "$mode" in install|--check|--install-only) ;; *) echo '用法：bash install.sh [--check|--install-only]' >&2; exit 1 ;; esac
[[ $mode != --check ]] || exit 0
if [[ $EUID == 0 ]]; then echo '请以桌面用户运行，不要 sudo bash install.sh；需要安装系统包时会单独请求 sudo。' >&2; exit 1; fi
for command in curl sha256sum sudo; do
  command -v "$command" >/dev/null || { printf '缺少 %s，请先通过系统软件管理器安装。\n' "$command" >&2; exit 1; }
done
cache=$(mktemp -d)
trap 'rm -rf -- "$cache"' EXIT
record=$(awk -F '\t' -v platform="$platform" '$1==platform {print $2 " " $3}' "$here/packages.tsv")
[[ -n $record ]] || { echo '安装包清单缺少此系统。' >&2; exit 1; }
read -r url sha <<< "$record"
family=${platform%-*}
installed=false
if [[ $family == deb ]] && dpkg-query -W -f='${Status}' chatgpt 2>/dev/null | grep -q 'install ok installed'; then installed=true; fi
if [[ $family == rpm ]] && rpm -q chatgpt >/dev/null 2>&1; then installed=true; fi
if [[ $family == arch ]] && pacman -Q chatgpt-bin >/dev/null 2>&1; then installed=true; fi
if [[ $installed == false ]]; then
  printf '下载官方客户端（约 550–650 MB），随后安装系统依赖。\n'
  package="$cache/chatgpt.$family"
  [[ $family != arch ]] || package="$cache/install-arch.sh"
  curl --proto '=https' --proto-redir '=https' --tlsv1.2 -fL --retry 2 --connect-timeout 20 --max-time 1800 -o "$package" "$url"
  printf '%s  %s\n' "$sha" "$package" | sha256sum --check --status || {
    echo '官方安装文件校验不符，未安装。请下载新版 TokenBots Linux 安装器。' >&2; exit 1;
  }
  case "$family" in
    deb) sudo apt-get update; sudo apt-get install -y "$package" ;;
    rpm) sudo dnf install -y "$package" ;;
    arch)
      echo 'Arch 官方安装器会提示确认整机软件升级，请阅读它的确认内容。'
      sudo bash "$package" ;;
  esac
fi
runtime=$(tokenbots_runtime)
node="$runtime/resources/cua_node/bin/node"
"$node" --version
# The official package supplies Node; no separate npm/Node installation required.
"$node" "$here/linux.cjs" install
launcher="${XDG_DATA_HOME:-$HOME/.local/share}/tokenbots-codex-linux/current/tokenbots.sh"
if [[ $mode == --install-only ]]; then
  echo '程序已安装；请从应用菜单打开“TokenBots 登录设置”完成登录。'
else
  "$launcher" configure
  echo '安装完成。请从应用菜单打开“TokenBots Codex”。'
fi
