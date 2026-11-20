"""Validate the knowledge-base vault against the schema in brain/AGENTS.md.

Usage: python -m tools.validate_brain [VAULT_DIR]   (default: brain)

Every problem is reported with its path relative to the vault; the exit code is 1 if any exist.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath

import yaml

# --- Schema (mirrors brain/AGENTS.md; change both together) --------------------------------

DEFAULT_VAULT = Path("brain")
SPECIAL_FILES = frozenset({"index.md", "log.md", "AGENTS.md"})
INDEX_FILE = "index.md"
EXCLUDED_DIRS = frozenset({"templates", ".obsidian"})

NOTE_TYPES = frozenset({"research", "concept", "decision", "ai-session", "review", "meeting"})
FOLDER_STATUS = {
    "inbox": "inbox",
    "projects": "distilled",
    "areas": "distilled",
    "resources": "distilled",
    "archive": "archived",
}
STATUSES = frozenset(FOLDER_STATUS.values())
INDEXED_FOLDERS = frozenset({"projects", "areas", "resources"})
REQUIRED_FIELDS = ("title", "type", "status", "created", "authors")
TYPES_REQUIRING_SOURCES = frozenset({"research"})

KEBAB = r"[a-z0-9]+(?:-[a-z0-9]+)*"
ISO_DATE = r"\d{4}-\d{2}-\d{2}"
KEBAB_RE = re.compile(KEBAB)
ISO_DATE_RE = re.compile(ISO_DATE)
GITHUB_USER_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")
REQUIREMENT_RE = re.compile(r"[A-Z]{2,4}-\d+(?:\.\d+)*")
TYPE_NAME_PATTERNS = {
    "ai-session": re.compile(rf"ai-session-{ISO_DATE}-{KEBAB}"),
    "meeting": re.compile(rf"meeting-{ISO_DATE}"),
    "review": re.compile(rf"review-{KEBAB}"),
    "decision": re.compile(rf"decision-{KEBAB}"),
}
TYPE_NAME_HINTS = {
    "ai-session": "ai-session-YYYY-MM-DD-<slug>",
    "meeting": "meeting-YYYY-MM-DD",
    "review": "review-<slug>",
    "decision": "decision-<slug>",
}

WIKILINK_RE = re.compile(r"!?\[\[([^\[\]\n]*)\]\]")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
FENCE_MARKERS = ("```", "~~~")
FRONTMATTER_DELIMITER = "---"


# --- Data -----------------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Problem:
    path: PurePosixPath
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class Note:
    path: PurePosixPath  # relative to the vault
    body: str
    frontmatter: dict | None = None
    frontmatter_error: str | None = None

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def folder(self) -> str | None:
        """Top-level PARA folder, or None for files at the vault root."""
        return self.path.parts[0] if len(self.path.parts) > 1 else None

    @property
    def is_special(self) -> bool:
        return self.folder is None and self.path.name in SPECIAL_FILES


@dataclass
class Vault:
    notes: list[Note]
    attachment_names: set[str] = field(default_factory=set)

    def known_targets(self) -> set[str]:
        return {n.stem.casefold() for n in self.notes} | self.attachment_names

    def index(self) -> Note | None:
        return next((n for n in self.notes if n.is_special and n.path.name == INDEX_FILE), None)


# --- Parsing --------------------------------------------------------------------------------


class _StringDateLoader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings, so the schema can report bad dates itself."""


_StringDateLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def parse_note(path: PurePosixPath, text: str) -> Note:
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        return Note(path, "\n".join(lines))
    try:
        end = next(
            i for i, line in enumerate(lines[1:], 1) if line.strip() == FRONTMATTER_DELIMITER
        )
    except StopIteration:
        return Note(
            path, "\n".join(lines), frontmatter_error="frontmatter is not closed with '---'"
        )
    body = "\n".join(lines[end + 1 :])
    try:
        data = yaml.load("\n".join(lines[1:end]), Loader=_StringDateLoader)
    except yaml.YAMLError as exc:
        return Note(path, body, frontmatter_error=f"invalid YAML in frontmatter: {exc}")
    if not isinstance(data, dict):
        return Note(path, body, frontmatter_error="frontmatter must be a mapping of fields")
    return Note(path, body, frontmatter=data)


def strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code, where example links must not count."""
    kept, fence = [], None
    for line in text.splitlines():
        marker = next((m for m in FENCE_MARKERS if line.lstrip().startswith(m)), None)
        if fence is None and marker:
            fence = marker
        elif fence is not None and marker == fence:
            fence = None
        elif fence is None:
            kept.append(line)
    return INLINE_CODE_RE.sub("", "\n".join(kept))


def link_targets(text: str) -> list[str]:
    """Normalised targets of every [[wikilink]] outside code: alias, heading and .md removed."""
    targets = []
    for raw in WIKILINK_RE.findall(strip_code(text)):
        target = raw.split("|", 1)[0].split("#", 1)[0].strip()
        targets.append(target.removesuffix(".md").casefold())
    return targets


def load_vault(root: Path) -> Vault:
    notes, attachments = [], set()
    for path in sorted(root.rglob("*")):
        rel = PurePosixPath(path.relative_to(root).as_posix())
        if not path.is_file() or EXCLUDED_DIRS & set(rel.parts[:-1]):
            continue
        if path.suffix == ".md":
            notes.append(parse_note(rel, path.read_text(encoding="utf-8")))
        else:
            attachments.add(path.name.casefold())
    return Vault(notes, attachments)


# --- Rules for a single note ----------------------------------------------------------------

NoteRule = Callable[[Note, Vault], Iterable[str]]


def check_frontmatter_present(note: Note, _: Vault) -> Iterable[str]:
    if note.frontmatter_error:
        yield note.frontmatter_error
    elif note.frontmatter is None:
        yield "missing YAML frontmatter (see brain/AGENTS.md)"


def check_required_fields(note: Note, _: Vault) -> Iterable[str]:
    fm = note.frontmatter or {}
    for name in REQUIRED_FIELDS:
        if name not in fm or fm[name] is None:
            yield f"field '{name}' is missing"


def check_title(note: Note, _: Vault) -> Iterable[str]:
    title = (note.frontmatter or {}).get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        yield "field 'title' must be non-empty text"


def check_type(note: Note, _: Vault) -> Iterable[str]:
    note_type = (note.frontmatter or {}).get("type")
    if note_type is not None and note_type not in NOTE_TYPES:
        yield f"field 'type' is '{note_type}'; allowed: {', '.join(sorted(NOTE_TYPES))}"


def check_status(note: Note, _: Vault) -> Iterable[str]:
    status = (note.frontmatter or {}).get("status")
    if status is None:
        return
    if status not in STATUSES:
        yield f"field 'status' is '{status}'; allowed: {', '.join(sorted(STATUSES))}"
    elif note.folder in FOLDER_STATUS and FOLDER_STATUS[note.folder] != status:
        yield (
            f"field 'status' is '{status}' but notes in {note.folder}/ "
            f"must be '{FOLDER_STATUS[note.folder]}'"
        )


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def check_dates(note: Note, _: Vault) -> Iterable[str]:
    fm = note.frontmatter or {}
    created = _parse_date(fm.get("created"))
    if "created" in fm and fm["created"] is not None and created is None:
        yield f"field 'created' must be a real date in YYYY-MM-DD form, got '{fm['created']}'"
    if fm.get("updated") is None:
        return
    updated = _parse_date(fm["updated"])
    if updated is None:
        yield f"field 'updated' must be a real date in YYYY-MM-DD form, got '{fm['updated']}'"
    elif created and updated < created:
        yield "field 'updated' is before 'created'"


def _check_string_list(
    fm: dict, name: str, pattern: re.Pattern | None, rule: str, required: bool = False
) -> Iterable[str]:
    if name not in fm or fm[name] is None:
        return
    value = fm[name]
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        yield f"field '{name}' must be a list of non-empty text values"
    elif required and not value:
        yield f"field '{name}' must not be empty"
    elif pattern and (bad := [v for v in value if not pattern.fullmatch(v)]):
        yield f"field '{name}' has invalid value(s) {', '.join(bad)}; {rule}"


def check_lists(note: Note, _: Vault) -> Iterable[str]:
    fm = note.frontmatter or {}
    yield from _check_string_list(
        fm, "authors", GITHUB_USER_RE, "use GitHub usernames", required=True
    )
    yield from _check_string_list(fm, "tags", KEBAB_RE, "use lower-case kebab-case")
    yield from _check_string_list(
        fm, "requirements", REQUIREMENT_RE, "use requirement IDs such as FR-1 or TQ-6"
    )
    yield from _check_string_list(
        fm, "sources", None, "", required=fm.get("type") in TYPES_REQUIRING_SOURCES
    )


def check_sources_present(note: Note, _: Vault) -> Iterable[str]:
    fm = note.frontmatter or {}
    if fm.get("type") in TYPES_REQUIRING_SOURCES and fm.get("sources") is None:
        yield f"field 'sources' is required for {fm['type']} notes"


def check_placement(note: Note, _: Vault) -> Iterable[str]:
    if note.folder is None:
        yield f"note must be inside a PARA folder: {', '.join(FOLDER_STATUS)}"


def check_name(note: Note, _: Vault) -> Iterable[str]:
    if not KEBAB_RE.fullmatch(note.stem):
        yield f"file name '{note.path.name}' must be lower-case kebab-case"
        return
    note_type = (note.frontmatter or {}).get("type")
    pattern = TYPE_NAME_PATTERNS.get(note_type) if isinstance(note_type, str) else None
    if pattern and not pattern.fullmatch(note.stem):
        yield f"{note_type} notes must be named {TYPE_NAME_HINTS[note_type]}.md"


def check_has_link(note: Note, _: Vault) -> Iterable[str]:
    if not any(t and t != note.stem.casefold() for t in link_targets(note.body)):
        yield "note must link at least one other note with [[...]]"


# Run on every note.
STRUCTURE_RULES: tuple[NoteRule, ...] = (
    check_frontmatter_present,
    check_placement,
    check_name,
    check_has_link,
)
# Run only once frontmatter has parsed, so one broken header does not cascade into many reports.
FIELD_RULES: tuple[NoteRule, ...] = (
    check_required_fields,
    check_title,
    check_type,
    check_status,
    check_dates,
    check_lists,
    check_sources_present,
)


def note_rules(note: Note) -> tuple[NoteRule, ...]:
    if note.is_special:
        return ()
    return STRUCTURE_RULES + (FIELD_RULES if note.frontmatter is not None else ())


# --- Rules for every Markdown file, and for the vault as a whole ----------------------------


def check_links_resolve(note: Note, vault: Vault) -> Iterable[str]:
    known = vault.known_targets()
    for target in link_targets(note.body):
        if not target:
            yield "empty link [[ ]]"
        elif target not in known:
            yield f"broken link [[{target}]]: no note or attachment with that name"


def check_unique_names(vault: Vault) -> Iterable[Problem]:
    by_name: dict[str, list[Note]] = defaultdict(list)
    for note in vault.notes:
        by_name[note.stem.casefold()].append(note)
    for name, notes in by_name.items():
        if len(notes) > 1:
            paths = ", ".join(str(n.path) for n in notes)
            for note in notes:
                yield Problem(note.path, f"duplicate note name '{name}' (used by {paths})")


def check_index_coverage(vault: Vault) -> Iterable[Problem]:
    index = vault.index()
    if index is None:
        yield Problem(PurePosixPath(INDEX_FILE), "index.md is missing from the vault root")
        return
    linked = set(link_targets(index.body))
    for note in vault.notes:
        if note.folder in INDEXED_FOLDERS and note.stem.casefold() not in linked:
            yield Problem(note.path, "note is not linked from index.md")


VAULT_RULES: tuple[Callable[[Vault], Iterable[Problem]], ...] = (
    check_unique_names,
    check_index_coverage,
)


# --- Entry points ---------------------------------------------------------------------------


def validate(root: Path) -> list[Problem]:
    if not root.is_dir():
        return [Problem(PurePosixPath("."), f"vault directory '{root}' does not exist")]
    vault = load_vault(root)
    problems: list[Problem] = []
    for note in vault.notes:
        for rule in (*note_rules(note), check_links_resolve):
            problems.extend(Problem(note.path, message) for message in rule(note, vault))
    for vault_rule in VAULT_RULES:
        problems.extend(vault_rule(vault))
    return sorted(set(problems))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else DEFAULT_VAULT
    problems = validate(root)
    for problem in problems:
        print(problem)
    if problems:
        noun = "problem" if len(problems) == 1 else "problems"
        print(f"\n{len(problems)} {noun} found in {root}. See brain/AGENTS.md.")
        return 1
    print(f"{root}: no problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
