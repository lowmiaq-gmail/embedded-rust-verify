#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
 echo "tools/cross-build.sh is reviewed only on Linux x86_64; download a matching CI artifact for board-only hosts." >&2
 exit 2
fi
if [[ ! -f reports/local/host.json ]]; then
 echo "reports/local/host.json is required; run the host verification first." >&2
 exit 2
fi
if ! command -v arm-none-eabi-gcc >/dev/null || ! command -v arm-none-eabi-size >/dev/null; then
 echo "Arm GNU tools are missing from PATH; run tools/install-arm.sh and export its bin directory." >&2
 exit 2
fi
mkdir -p reports/local
corpus_id="$(python3 tools/fingerprint.py --corpus-id --host-report reports/local/host.json)"
raw_build_id="$(python3 tools/fingerprint.py --build-id raw --host-report reports/local/host.json)"
safe_build_id="$(python3 tools/fingerprint.py --build-id safe --host-report reports/local/host.json)"
cd platforms/cortex-m
for variant in raw safe; do
 if [[ "$variant" == raw ]]; then build_id="$raw_build_id"; else build_id="$safe_build_id"; fi
 EVR_MODE="$variant" EVR_BUILD_ID="$build_id" EVR_CORPUS_ID="$corpus_id" \
  cargo rustc --locked --release --no-default-features --features "$variant" -- \
  -C "link-arg=-Map=$root/reports/local/$variant.map"
 cp target/thumbv7em-none-eabihf/release/fir-bench "$root/reports/local/$variant.elf"
done
cd "$root"
python3 tools/size-report.py
rustc -Vv > reports/local/rustc.txt
arm-none-eabi-gcc --version > reports/local/arm-gcc.txt
python3 tools/fingerprint.py > reports/local/source-fingerprint.txt
python3 - <<'META'
from pathlib import Path
import json,subprocess
files=list(Path('platforms/cortex-m/target').glob('**/build/verify-cmsis-dsp-*/out/c-build.txt'))
Path('reports/local/c-builds.json').write_text(json.dumps({str(p):p.read_text() for p in files},indent=2))
Path('reports/local/build-commit.txt').write_text(subprocess.check_output(['git','rev-parse','HEAD']).decode())
META
python3 tools/fingerprint.py \
 --write-build-manifest reports/local/build-manifest.json \
 --host-report reports/local/host.json \
 --raw-elf reports/local/raw.elf --safe-elf reports/local/safe.elf \
 --raw-build-id "$raw_build_id" --safe-build-id "$safe_build_id"
