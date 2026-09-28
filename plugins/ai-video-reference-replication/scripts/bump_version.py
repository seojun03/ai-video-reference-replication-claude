#!/usr/bin/env python3
"""Bump the plugin version after a real content change (Claude Code port).

Replaces the Codex refresh/publish tooling. Claude Code users receive updates
through the plugin marketplace, so a release is: edit -> tests -> this script ->
commit -> push to main. Re-running without content changes keeps the version.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
AUTOMATION = ROOT / "skills" / "ai-video-reference-replication" / "assets" / "automation-version.json"
MAIN_SKILL = ROOT / "skills" / "ai-video-reference-replication" / "SKILL.md"
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}
VERSION_LINE = re.compile(r"(- 현재 자동화 버전: `)([0-9]+\.[0-9]+)(`)")


def fingerprint(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root)
        if IGNORED_PARTS & set(relative.parts) or path.suffix == ".pyc" or path.name == ".DS_Store":
            continue
        if path in (MANIFEST, AUTOMATION):
            continue
        data = path.read_bytes()
        if path == MAIN_SKILL:
            data = VERSION_LINE.sub(r"\1X\3", data.decode("utf-8")).encode("utf-8")
        digest.update(str(relative).encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


def next_minor(version: str) -> str:
    major, minor = (int(part) for part in version.split(".")[:2])
    return f"{major}.{minor + 1}"


def bump(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    automation = json.loads(AUTOMATION.read_text(encoding="utf-8"))
    current = fingerprint()
    if automation.get("sourceFingerprint") == current:
        return {"contentChanged": False, "automationVersion": automation["automationVersion"]}
    version = next_minor(automation["automationVersion"])
    kst = now.astimezone(timezone(timedelta(hours=9)))
    automation.update({
        "automationVersion": version,
        "sourceFingerprint": current,
        "packageVersion": f"{version}.0+claude",
        "updatedAt": now.isoformat(timespec="seconds"),
        "displayUpdatedAtKst": kst.strftime("%Y.%m.%d %H:%M"),
        "packageUpdatedAt": now.isoformat(timespec="seconds"),
    })
    AUTOMATION.write_text(json.dumps(automation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["version"] = f"{version}.0"
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    skill = MAIN_SKILL.read_text(encoding="utf-8")
    if not VERSION_LINE.search(skill):
        raise SystemExit("main SKILL.md version line not found")
    MAIN_SKILL.write_text(VERSION_LINE.sub(lambda m: m.group(1) + version + m.group(3), skill), encoding="utf-8")
    return {"contentChanged": True, "automationVersion": version, "pluginVersion": manifest["version"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only report whether content changed")
    args = parser.parse_args()
    if args.check:
        automation = json.loads(AUTOMATION.read_text(encoding="utf-8"))
        print(json.dumps({"contentChanged": automation.get("sourceFingerprint") != fingerprint()}, indent=2))
        return
    print(json.dumps(bump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
