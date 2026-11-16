#!/usr/bin/env bash
set -euo pipefail
umask 077
here=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
source "$here/platform.sh"
runtime=$(tokenbots_runtime)
node="$runtime/resources/cua_node/bin/node"
action=${1:-start}
[[ $# == 0 ]] || shift
if [[ $action == configure ]]; then
  if [[ ! -t 0 ]]; then echo '请在终端运行登录设置。' >&2; exit 1; fi
  printf '输入你自己的 TokenBots API Key（输入不显示；不是 ChatGPT 密码）：'
  IFS= read -r -s tokenbots_key
  printf '\n'
  printf '%s\n' "$tokenbots_key" | "$node" "$here/linux.cjs" configure
  unset tokenbots_key
elif [[ $action == update ]]; then
  source /etc/os-release
  platform=$(tokenbots_platform "$ID" "${VERSION_ID:-rolling}" "$(uname -m)")
  echo '通过官方签名软件源更新客户端。请先保存工作并关闭 TokenBots Codex。'
  case "$platform" in
    deb-*) sudo apt-get update; sudo apt-get install --only-upgrade -y chatgpt ;;
    rpm-*) sudo dnf upgrade --refresh -y chatgpt ;;
    arch-*) sudo pacman -Syu ;;
  esac
  "$node" "$here/linux.cjs" record-update
  if [[ -t 0 ]]; then read -r -p '按 Enter 关闭 / Press Enter to close. ' unused; fi
elif [[ $action == usage ]]; then
  "$node" "$here/linux.cjs" usage "$@"
  if [[ -t 0 ]]; then read -r -p '按 Enter 关闭 / Press Enter to close. ' unused; fi
else
  exec "$node" "$here/linux.cjs" "$action" "$@"
fi
