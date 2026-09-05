#!/usr/bin/env python3
"""Classify whether a change invalidates Cortex-M hardware evidence.

This is deliberately a small path policy, not a dependency graph.  The
classification is conservative: an unknown non-documentation path requires
fresh hardware evidence.  The script never runs hardware and a
``hardware_required`` result is a successful classification (exit status 0).

The normal interface is ``hardware-impact.py BASE HEAD`` for use from CI.
Tests and local callers can use ``--path PATH`` one or more times to classify
an explicit path list without invoking Git.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable, Sequence


NO_CHANGE = "no_change"
DOCUMENTATION = "documentation_or_evidence_only"
EVIDENCE_REPARSE = "evidence_reparse"
PIPELINE_ONLY = "pipeline_only"
HOST_REFERENCE = "host_reference_recheck"
HARDWARE_REQUIRED = "hardware_required"

# Higher numbers win when more than one path is changed.  A source/build
# change therefore cannot be hidden by a simultaneous documentation change.
PRIORITY = {
    NO_CHANGE: 0,
    DOCUMENTATION: 1,
    PIPELINE_ONLY: 2,
    EVIDENCE_REPARSE: 3,
    HOST_REFERENCE: 4,
    HARDWARE_REQUIRED: 5,
}

_DOC_NAMES = {
    "readme",
    "changelog",
    "contributing",
    "security",
    "license",
    "license-mit",
    "license-apache",
    "third-party-notices",
}
_DOC_SUFFIXES = (".md", ".markdown", ".rst", ".adoc")

_EVIDENCE_EXACT = {
    "tools/collect-hardware.py",
    "tools/size-report.py",
    "tools/fingerprint.py",
}
_EVIDENCE_NAME = re.compile(
    r"(?:collect|collector|report|summary|parse|size)[-_a-z0-9]*\.(?:py|rs|sh)$"
)

_HOST_NAME = re.compile(
    r"(?:^|[-_])(reference|oracle|comparator|comparison|tolerance)(?:[-_]|$)"
)

_HARDWARE_PREFIXES = (
    "adapters/",
    "vendor/",
    "platforms/",
    "firmware/",
    ".cargo/",
)
_HARDWARE_EXACT = {
    "Cargo.toml",
    "Cargo.lock",
    "rust-toolchain.toml",
    "cargo.lock",
    "build.rs",
    "memory.x",
    "tools/cross-build.sh",
    "tools/install-arm.sh",
}
_HARDWARE_SUFFIXES = (
    "/cargo.toml",
    "/cargo.lock",
    "/build.rs",
    "/memory.x",
    ".ld",
    ".c",
    ".h",
)
_HARDWARE_COMPONENTS = {
    "corpus",
    "digest",
    "linker",
    "toolchain",
    "firmware",
    "cross-build",
}


@dataclass(frozen=True)
class ImpactResult:
    """Stable, serializable result returned by :func:`classify_paths`."""

    classification: str
    reason: str
    paths: tuple[str, ...]

    @property
    def requires_new_hardware(self) -> bool:
        return self.classification == HARDWARE_REQUIRED

    @property
    def may_require_new_hardware(self) -> bool:
        return self.classification == HOST_REFERENCE

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": 1,
            "classification": self.classification,
            "reason": self.reason,
            "paths": list(self.paths),
            "requires_new_hardware": self.requires_new_hardware,
            "may_require_new_hardware": self.may_require_new_hardware,
        }


def _normalize_path(path: str) -> str:
    """Normalize a Git/path-list entry while preserving its relative path."""

    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_documentation(path: str) -> bool:
    if path.startswith(("docs/", "reports/")):
        return True
    name = path.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0].lower() if "." in name else name.lower()
    return stem in _DOC_NAMES or name.lower().endswith(_DOC_SUFFIXES)


def _is_pipeline(path: str) -> bool:
    if path == "tools/hardware-impact.py":
        return True
    if path.startswith((".github/", "tests/")):
        return True
    return False


def _is_evidence_reparse(path: str) -> bool:
    if path in _EVIDENCE_EXACT or path.startswith("crates/verify-report/"):
        return True
    name = path.rsplit("/", 1)[-1].lower()
    return bool(_EVIDENCE_NAME.fullmatch(name))


def _is_host_reference(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    stem = name.rsplit(".", 1)[0]
    if _HOST_NAME.search(stem):
        return True
    # Keep the rule useful for conventional host verification module names
    # even when they use an extension not covered above.
    components = set(path.lower().replace("-", "_").split("/"))
    return bool(components & {"reference", "oracle", "comparator", "comparison"})


def _is_hardware_required(path: str) -> bool:
    if path.startswith(_HARDWARE_PREFIXES) or path.startswith("examples/cmsis-fir-f32/"):
        return True
    if path in _HARDWARE_EXACT or path.endswith(_HARDWARE_SUFFIXES):
        return True
    components = set(path.lower().replace("-", "_").split("/"))
    if components & {component.replace("-", "_") for component in _HARDWARE_COMPONENTS}:
        return True
    # verify-core contains the production digest/comparison behavior.  A
    # change to it is not merely a report formatting change.  A separately
    # named reference/comparator module is the narrower host-reference case;
    # it is handled by ``_is_host_reference`` below.
    if path.startswith("crates/verify-core/src/") and not _is_host_reference(path):
        return True
    return False


def classify_path(path: str) -> str:
    """Return the impact class for one normalized or relative path."""

    path = _normalize_path(path)
    if not path:
        return NO_CHANGE
    if _is_documentation(path):
        return DOCUMENTATION
    # Corpus/build/production rules intentionally run before test-only rules.
    # A test fixture that changes the board corpus must still invalidate it.
    if _is_hardware_required(path):
        return HARDWARE_REQUIRED
    if _is_host_reference(path):
        return HOST_REFERENCE
    if _is_evidence_reparse(path):
        return EVIDENCE_REPARSE
    if _is_pipeline(path):
        return PIPELINE_ONLY
    return HARDWARE_REQUIRED


def _reason_for(classification: str, paths: Sequence[str]) -> str:
    if classification == NO_CHANGE:
        return "No changed paths were reported; no hardware-evidence decision is required."
    if classification == DOCUMENTATION:
        return (
            "Only documentation, status, launch, or report files changed; "
            "existing hardware evidence remains reusable."
        )
    if classification == PIPELINE_ONLY:
        return (
            "Only CI/pipeline or test-control files changed; measured binary "
            "behavior is unchanged and no new hardware run is required."
        )
    if classification == EVIDENCE_REPARSE:
        return (
            "Evidence collection/report parsing changed; re-parse identity-matched "
            "raw logs without automatically reflashing the device."
        )
    if classification == HOST_REFERENCE:
        return (
            "The host reference/comparator changed; recheck the host reference "
            "first and escalate to hardware if the hardware corpus identity is "
            "changed or cannot be proven unchanged."
        )
    unknown = [
        path
        for path in paths
        if classify_path(path) == HARDWARE_REQUIRED and not _is_hardware_required(path)
    ]
    if unknown:
        return (
            "At least one non-documentation path has unknown impact "
            f"({', '.join(unknown)}); fresh hardware evidence is required."
        )
    return (
        "A production adapter, firmware, build/toolchain, linker, corpus, or "
        "digest input changed; fresh hardware evidence is required."
    )


def classify_paths(paths: Iterable[str]) -> ImpactResult:
    """Classify a path iterable without reading Git or the filesystem.

    Empty entries are ignored and the remaining paths are sorted/deduplicated,
    making the result deterministic for both CI and unit tests.
    """

    normalized = tuple(sorted({_normalize_path(path) for path in paths if _normalize_path(path)}))
    if not normalized:
        return ImpactResult(NO_CHANGE, _reason_for(NO_CHANGE, ()), ())
    classifications = [classify_path(path) for path in normalized]
    classification = max(classifications, key=lambda value: PRIORITY[value])
    return ImpactResult(classification, _reason_for(classification, normalized), normalized)


def changed_paths_from_git(base: str, head: str) -> list[str]:
    """Read changed paths for the historical ``BASE HEAD`` CLI interface."""

    completed = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.splitlines()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", help="Git base revision")
    parser.add_argument("head", nargs="?", help="Git head revision")
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Classify this path directly (repeatable; avoids invoking Git)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit only the stable machine-readable JSON object",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    using_paths = args.paths is not None
    using_revisions = args.base is not None or args.head is not None
    if using_paths and using_revisions:
        parser.error("use BASE HEAD or --path, not both")
    if using_paths:
        raw_paths = args.paths
    elif args.base is not None and args.head is not None:
        try:
            raw_paths = changed_paths_from_git(args.base, args.head)
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", None) or str(exc)
            print(f"git diff failed: {detail.strip()}", file=sys.stderr)
            return 2
    else:
        parser.error("provide BASE HEAD or at least one --path")

    result = classify_paths(raw_paths or ())
    encoded = json.dumps(result.as_dict(), ensure_ascii=True, separators=(",", ":"))
    if args.json:
        print(encoded)
    else:
        print(f"Hardware impact classification: {result.classification}")
        print(f"Reason: {result.reason}")
        print("Changed paths: " + (", ".join(result.paths) if result.paths else "(none)"))
        print(f"Machine-readable: {encoded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
