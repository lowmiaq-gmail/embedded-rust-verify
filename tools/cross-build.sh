#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
mkdir -p reports/local
cd platforms/cortex-m
for variant in raw safe; do
 cargo build --locked --release --no-default-features --features "$variant"
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
