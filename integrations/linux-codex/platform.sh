#!/usr/bin/env bash
# Pure detection helpers; sourced by the installer and its regression tests.
tokenbots_platform() {
  local distro=$1 version=$2 machine=$3 family arch
  case "$machine" in
    x86_64|amd64) arch=amd64 ;;
    aarch64|arm64) arch=arm64 ;;
    *) printf '不支持的处理器 / Unsupported architecture: %s\n' "$machine" >&2; return 1 ;;
  esac
  case "$distro:$version" in
    ubuntu:24.04|ubuntu:26.04|debian:13|debian:13.*) family=deb ;;
    fedora:43|fedora:44) family=rpm ;;
    arch:*) family=arch ;;
    *) printf '官方 Linux 预览版尚不支持此系统：%s %s。支持 Ubuntu 24.04/26.04、Debian 13、Fedora 43/44、当前 Arch。\n' "$distro" "$version" >&2; return 1 ;;
  esac
  printf '%s-%s\n' "$family" "$arch"
}

tokenbots_runtime() {
  # Layout observed in the official package. Never run a PATH lookalike with a key.
  local root
  for root in /usr/lib/chatgpt /opt/ChatGPT /opt/chatgpt; do
    if [[ -x "$root/resources/cua_node/bin/node" && -x "$root/resources/codex" ]]; then
      printf '%s\n' "$root"; return 0
    fi
  done
  printf '未找到完整的官方 Linux 客户端，请重新运行 install.sh。\n' >&2
  return 1
}
