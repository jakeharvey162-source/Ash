"""Deterministic evidence summary for generated Ash websites.

A static source checklist is *not* a visual review, usability test, security
audit, or customer feedback. We never run generated source from this module.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

MAX_FILES = 80
MAX_TOTAL_BYTES = 900_000
MAX_FILE_BYTES = 180_000
EXTENSIONS = frozenset((".html", ".jsx", ".tsx", ".js", ".ts", ".css", ".scss"))
SKIP_DIRECTORIES = frozenset(("node_modules", "dist", ".git", ".next", "coverage", ".vercel"))

def assess_build(root: pathlib.Path, details: dict[str, Any]) -> dict[str, Any]:
    """Summarize reproducible local evidence; never claim visual or user testing."""
    workspace = pathlib.Path(root).resolve()
    if not workspace.is_dir():
        raise ValueError("Build workspace does not exist")
    details = details if isinstance(details, dict) else {}
    verification = details.get("verification") or {}
    build_passed = verification.get("build_passed") is True
    generation_mode = str(details.get("generation_mode") or "unknown")[:64]
    degraded = details.get("degraded") is True
    sources: list[str] = []
    bytes_read = 0
    found_files = 0
    for path in sorted(workspace.rglob("*")):
        if len(sources) >= MAX_FILES or bytes_read >= MAX_TOTAL_BYTES:
            break
        if SKIP_DIRECTORIES.intersection(path.relative_to(workspace).parts):
            continue
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        try:
            if workspace not in path.resolve().parents:
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                continue
            bytes_read += size
            if bytes_read > MAX_TOTAL_BYTES:
                break
            sources.append(path.read_text(encoding="utf-8", errors="replace"))
            found_files += 1
        except OSError:
            continue
    body = "\n".join(sources)
    tests = {
        "responsive_layout_source": bool(re.search(r"@media\b|clamp\(|minmax\(|flex-wrap|grid-template", body, re.I)),
        "focus_styles_source": bool(re.search(r":focus-visible|:focus\b|onFocus\b", body, re.I)),
        "reduced_motion_source": bool(re.search(r"prefers-reduced-motion", body, re.I)),
        "semantic_landmarks_source": bool(re.search(r"<(?:main|nav|header|footer|section)\b", body, re.I)),
        "interaction_handlers_source": bool(re.search(r"onClick\b|addEventListener\(|onSubmit\b", body, re.I)),
        "placeholder_copy_absent": not bool(re.search(r"\blorem ipsum\b|\bacme corp\b|\bjohn doe\b", body, re.I)),
    }
    # These are source signals only, not proof they work when rendered.
    warnings = []
    if not build_passed:
        warnings.append("No verified successful build. Do not publish as ready.")
    if degraded:
        warnings.append("Generation fell back or recovered; requested functionality remains unverified.")
    if not found_files:
        warnings.append("No small readable frontend source files were inspected.")
    for key, value in tests.items():
        if not value:
            warnings.append({
                "responsive_layout_source": "Responsive layout not detected statically; inspect mobile sizes.",
                "focus_styles_source": "Keyboard focus styling not detected; test keyboard navigation.",
                "reduced_motion_source": "Reduced-motion support not detected; consider motion accessibility.",
                "semantic_landmarks_source": "Semantic page structure not detected; inspect navigation landmarks.",
                "interaction_handlers_source": "Interaction handler not detected; test buttons, forms and links.",
                "placeholder_copy_absent": "Placeholder copy detected; replace before launch.",
            }[key])
    return {
        "version": 1,
        "classification": "STATIC_SOURCE_AND_BUILD_EVIDENCE_ONLY",
        "verified_build": build_passed,
        "generation_mode": generation_mode,
        "degraded": degraded,
        "source_files_inspected": found_files,
        "checks": tests,
        "browser_tested": False,
        "mobile_visual_tested": False,
        "user_feedback_collected": False,
        "production_ready": False,
        "warnings": warnings[:10],
        "next_checks": [
            "Review screenshots at 390 and 1440 pixels.",
            "Verify buttons, forms, keyboard and screen reader usability in a browser.",
            "Review original copy, permissions and any external dependencies.",
            "Collect actual tester feedback before publishing a release claim.",
        ],
    }
