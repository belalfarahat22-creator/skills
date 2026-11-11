#!/usr/bin/env python3
"""Check every skill in this repository against the Agent Skills spec.

Usage:
    python3 scripts/validate_skills.py            # all skills + marketplace
    python3 scripts/validate_skills.py skills/pdf # one or more skill folders

ERROR lines break the spec or the plugin marketplace and make the exit code 1.
WARN lines are best-practice findings (triggering, size, broken references).

Checks:
  * SKILL.md exists and starts with YAML frontmatter
  * only allowed frontmatter keys (name, description, license, allowed-tools,
    metadata, compatibility)
  * name: kebab-case, at most 64 characters, equal to the folder name
  * description: non-empty, at most 1024 characters, no angle brackets,
    says when to use the skill (WARN)
  * SKILL.md body under 500 lines (WARN)
  * relative files named in SKILL.md exist (WARN)
  * every Python file compiles
  * evals/trigger_evals.json, when present, is a list of
    {"query": str, "should_trigger": bool} with both kinds of case
  * .claude-plugin/marketplace.json: every listed skill path exists and every
    skill folder is listed by some plugin (WARN)
"""

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
WHEN_RE = re.compile(r"\b(use (this|it|when|whenever|for)|when (the )?user|trigger|whenever)\b", re.I)
# relative paths written in backticks or markdown links, e.g. `scripts/foo.py`, (reference.md)
REF_RE = re.compile(r"[`(]((?:\./)?(?:[\w.-]+/)*[\w.-]+\.(?:py|js|ts|md|json|html|sh|txt|xsd|css|pdf))[`)]")
MAX_BODY_LINES = 500
# Findings that come from the upstream anthropics/skills repo. They are reported as WARN so CI
# stays green, and are left unchanged here so upstream updates merge cleanly.
KNOWN_UPSTREAM = {("claude-api", "description-length")}


class Report:
    def __init__(self):
        self.errors = 0
        self.warnings = 0

    def error(self, where, msg):
        self.errors += 1
        print(f"ERROR {where}: {msg}")

    def warn(self, where, msg):
        self.warnings += 1
        print(f"WARN  {where}: {msg}")


def read_frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def check_skill(folder: Path, rep: Report):
    where = folder.relative_to(ROOT).as_posix()
    skill_md = folder / "SKILL.md"
    if not skill_md.is_file():
        rep.error(where, "SKILL.md not found")
        return
    text = skill_md.read_text(encoding="utf-8")
    fm_text, body = read_frontmatter(text)
    if fm_text is None:
        rep.error(where, "SKILL.md must start with '---' YAML frontmatter")
        return
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        rep.error(where, f"frontmatter is not valid YAML: {e}")
        return
    if not isinstance(fm, dict):
        rep.error(where, "frontmatter must be a YAML mapping")
        return

    extra = set(fm) - ALLOWED_KEYS
    if extra:
        rep.error(where, f"unexpected frontmatter key(s): {', '.join(sorted(extra))}")

    name = fm.get("name")
    if not isinstance(name, str) or not name.strip():
        rep.error(where, "missing 'name'")
    else:
        if not NAME_RE.match(name):
            rep.error(where, f"name '{name}' must be kebab-case (a-z, 0-9, single hyphens)")
        if len(name) > 64:
            rep.error(where, f"name is {len(name)} characters (max 64)")
        if name != folder.name:
            rep.error(where, f"name '{name}' differs from folder name '{folder.name}'")

    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        rep.error(where, "missing 'description'")
    else:
        if len(desc) > 1024:
            report = rep.warn if (folder.name, "description-length") in KNOWN_UPSTREAM else rep.error
            report(where, f"description is {len(desc)} characters (max 1024)")
        if "<" in desc or ">" in desc:
            rep.error(where, "description contains angle brackets")
        if not WHEN_RE.search(desc):
            rep.warn(where, "description does not say when to use the skill (e.g. 'Use when ...') - it may under-trigger")
        if len(desc) < 80:
            rep.warn(where, f"description is only {len(desc)} characters - likely too thin to trigger reliably")

    comp = fm.get("compatibility")
    if comp is not None and (not isinstance(comp, str) or len(comp) > 500):
        rep.error(where, "compatibility must be a string of at most 500 characters")

    n_lines = body.count("\n") + 1
    if n_lines > MAX_BODY_LINES:
        rep.warn(where, f"SKILL.md body is {n_lines} lines (recommended under {MAX_BODY_LINES}; move detail to references/)")

    # files referenced from SKILL.md
    missing = set()
    for ref in REF_RE.findall(body):
        ref = ref[2:] if ref.startswith("./") else ref
        # Bare names (`output.pdf`) are usually examples, so only paths into one of this
        # skill's own sub-folders (scripts/, references/, ...) are checked.
        if "/" in ref and (folder / ref.split("/")[0]).is_dir() and not (folder / ref).exists():
            missing.add(ref)
    for ref in sorted(missing):
        rep.warn(where, f"SKILL.md mentions '{ref}' but it does not exist")

    for py in sorted(folder.rglob("*.py")):
        try:
            compile(py.read_bytes(), str(py), "exec")
        except (SyntaxError, ValueError) as e:
            rep.error(py.relative_to(ROOT).as_posix(), f"does not compile: {e}")

    ev = folder / "evals" / "trigger_evals.json"
    if ev.exists():
        try:
            cases = json.loads(ev.read_text(encoding="utf-8"))
            ok = isinstance(cases, list) and all(
                isinstance(c, dict) and isinstance(c.get("query"), str) and isinstance(c.get("should_trigger"), bool)
                for c in cases)
            if not ok:
                rep.error(ev.relative_to(ROOT).as_posix(), 'must be a list of {"query": str, "should_trigger": bool}')
            elif {c["should_trigger"] for c in cases} != {True, False}:
                rep.warn(ev.relative_to(ROOT).as_posix(), "needs both should_trigger true and false cases")
        except json.JSONDecodeError as e:
            rep.error(ev.relative_to(ROOT).as_posix(), f"invalid JSON: {e}")


def check_marketplace(rep: Report):
    where = MARKETPLACE.relative_to(ROOT).as_posix()
    if not MARKETPLACE.exists():
        rep.warn(where, "not found")
        return
    try:
        data = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        rep.error(where, f"invalid JSON: {e}")
        return
    listed, names = set(), set()
    for p in data.get("plugins", []):
        pname = p.get("name", "?")
        if pname in names:
            rep.error(where, f"plugin name '{pname}' is used twice")
        names.add(pname)
        base = ROOT / p.get("source", "./")
        for s in p.get("skills", []):
            path = (base / s).resolve()
            if not (path / "SKILL.md").is_file():
                rep.error(where, f"plugin '{pname}' lists '{s}', which has no SKILL.md")
            listed.add(path)
    for folder in sorted(SKILLS.iterdir()):
        if folder.is_dir() and folder.resolve() not in listed:
            rep.warn(where, f"skills/{folder.name} is not in any plugin, so it can't be installed with /plugin install")


def main(argv):
    rep = Report()
    targets = [Path(a).resolve() for a in argv] or sorted(p for p in SKILLS.iterdir() if p.is_dir())
    for folder in targets:
        check_skill(folder, rep)
    if not argv:
        check_marketplace(rep)
    print(f"\n{len(targets)} skill(s) checked: {rep.errors} error(s), {rep.warnings} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
