#!/usr/bin/env bash
set -euo pipefail
# Pinned official archive; local install, no root needed.
base="${ARM_TOOLCHAIN_DIR:-$PWD/.tools}"
mkdir -p "$base"
name=arm-gnu-toolchain-12.3.rel1-x86_64-arm-none-eabi
if [ ! -x "$base/$name/bin/arm-none-eabi-gcc" ]; then
 curl -fL "https://developer.arm.com/-/media/Files/downloads/gnu/12.3.rel1/binrel/$name.tar.xz" -o "$base/arm.tar.xz"
 (cd "$base" && echo '12a2815644318ebcceaf84beabb665d0924b6e79e21048452c5331a56332b309  arm.tar.xz' | sha256sum -c -)
 tar --no-same-owner -xf "$base/arm.tar.xz" -C "$base"
 rm "$base/arm.tar.xz"
fi
printf '%s\n' "$base/$name/bin"
