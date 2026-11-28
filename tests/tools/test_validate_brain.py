"""Unit tests for tools/validate_brain.py, one group per rule in brain/AGENTS.md."""

from pathlib import Path, PurePosixPath

import pytest

from tests.tools.vault_builder import Vault
from tools import validate_brain as vb


@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    return Vault(tmp_path)


def assert_single_problem(vault: Vault, *fragments: str) -> None:
    problems = vault.problems()
    assert len(problems) == 1, problems
    for fragment in fragments:
        assert fragment in problems[0], problems


# --- Baseline -------------------------------------------------------------------------------


def test_valid_vault_has_no_problems(vault):
    assert vault.problems() == []


def test_missing_vault_directory_is_reported(tmp_path):
    problems = [str(p) for p in vb.validate(tmp_path / "missing")]
    assert len(problems) == 1 and "does not exist" in problems[0]


def test_templates_and_obsidian_folders_are_ignored(vault):
    vault.write("templates/research.md", '---\ntitle: "{{title}}"\n---\n[[ ]]\n')
    vault.write(".obsidian/notes.md", "[[nowhere]]\n")
    assert vault.problems() == []


def test_non_markdown_files_are_ignored(vault):
    vault.write("inbox/.gitkeep", "")
    assert vault.problems() == []


# --- Frontmatter ----------------------------------------------------------------------------


def test_note_without_frontmatter_is_reported(vault):
    vault.write("resources/tfidf-cosine-similarity.md", "No frontmatter. [[index]]\n")
    assert_single_problem(vault, "tfidf-cosine-similarity.md", "frontmatter")


def test_unterminated_frontmatter_is_reported(vault):
    vault.write("resources/tfidf-cosine-similarity.md", "---\ntitle: x\n[[index]]\n")
    assert_single_problem(vault, "not closed")


def test_invalid_yaml_is_reported(vault):
    vault.write("resources/tfidf-cosine-similarity.md", "---\ntitle: [unclosed\n---\n[[index]]\n")
    assert_single_problem(vault, "invalid YAML")


def test_frontmatter_that_is_not_a_mapping_is_reported(vault):
    vault.write("resources/tfidf-cosine-similarity.md", "---\n- a\n- b\n---\n[[index]]\n")
    assert_single_problem(vault, "mapping")


@pytest.mark.parametrize("field", ["title", "type", "status", "created", "authors"])
def test_each_required_field_is_enforced(vault, field):
    vault.note("resources/tfidf-cosine-similarity.md", **{field: None})
    assert_single_problem(vault, f"'{field}'", "missing")


def test_empty_title_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", title='""')
    assert_single_problem(vault, "'title'")


def test_unknown_type_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", type="essay")
    assert_single_problem(vault, "'type'", "essay")


@pytest.mark.parametrize("note_type", sorted(vb.NOTE_TYPES - {"research"}))
def test_every_documented_type_is_accepted(vault, note_type):
    name = {
        "ai-session": "ai-session-2026-11-19-ci",
        "meeting": "meeting-2026-11-19",
        "review": "review-stage-1",
        "decision": "decision-ci-tooling",
    }.get(note_type, "pagination")
    vault.note(f"areas/{name}.md", type=note_type, sources=None)
    vault.link_from_index(name)
    assert vault.problems() == []


def test_unknown_status_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", status="done")
    problems = vault.problems()
    assert any("'status'" in p and "done" in p for p in problems), problems


@pytest.mark.parametrize(
    ("folder", "status"),
    [
        ("inbox", "inbox"),
        ("projects", "distilled"),
        ("areas", "distilled"),
        ("resources", "distilled"),
        ("archive", "archived"),
    ],
)
def test_status_matching_folder_is_accepted(vault, folder, status):
    vault.note(f"{folder}/pagination.md", status=status)
    vault.link_from_index("pagination")
    assert vault.problems() == []


@pytest.mark.parametrize(
    ("folder", "status"),
    [
        ("inbox", "distilled"),
        ("resources", "inbox"),
        ("archive", "distilled"),
        ("areas", "archived"),
    ],
)
def test_status_disagreeing_with_folder_is_reported(vault, folder, status):
    vault.note(f"{folder}/pagination.md", status=status)
    vault.link_from_index("pagination")
    assert_single_problem(vault, "pagination.md", "status")


@pytest.mark.parametrize("value", ["19-11-2026", "2026-13-01", "yesterday"])
def test_invalid_created_date_is_reported(vault, value):
    vault.note("resources/tfidf-cosine-similarity.md", created=value)
    assert_single_problem(vault, "'created'")


def test_updated_before_created_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", updated="2026-11-01")
    assert_single_problem(vault, "'updated'", "before")


def test_updated_on_or_after_created_is_accepted(vault):
    vault.note("resources/tfidf-cosine-similarity.md", updated="2026-11-19")
    assert vault.problems() == []


def test_invalid_updated_date_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", updated="soon")
    assert_single_problem(vault, "'updated'")


@pytest.mark.parametrize("authors", ["[]", "sidtricoder", "[-bad-name]", "[two words]"])
def test_invalid_authors_are_reported(vault, authors):
    path = vault.root / "resources/tfidf-cosine-similarity.md"
    vault.note("resources/tfidf-cosine-similarity.md")
    path.write_text(
        path.read_text(encoding="utf-8").replace("authors: [sidtricoder]", f"authors: {authors}"),
        encoding="utf-8",
    )
    assert_single_problem(vault, "'authors'")


def test_several_valid_authors_are_accepted(vault):
    vault.note("resources/tfidf-cosine-similarity.md", authors=["sidtricoder", "Devaang-Rastogi"])
    assert vault.problems() == []


@pytest.mark.parametrize("tags", [["Similarity"], ["two words"], ["snake_case"]])
def test_tags_must_be_kebab_case(vault, tags):
    vault.note("resources/tfidf-cosine-similarity.md", tags=tags)
    assert_single_problem(vault, "'tags'")


def test_tags_that_are_not_a_list_are_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", tags="similarity")
    assert_single_problem(vault, "'tags'")


@pytest.mark.parametrize("requirement", ["FR-1", "NFR-3", "SK-1", "TQ-6", "SB-2", "FR-5.14"])
def test_valid_requirement_ids_are_accepted(vault, requirement):
    vault.note("resources/tfidf-cosine-similarity.md", requirements=[requirement])
    assert vault.problems() == []


@pytest.mark.parametrize("requirement", ["fr-1", "FR1", "FR-", "Feature-1"])
def test_invalid_requirement_ids_are_reported(vault, requirement):
    vault.note("resources/tfidf-cosine-similarity.md", requirements=[requirement])
    assert_single_problem(vault, "'requirements'")


def test_research_note_requires_sources(vault):
    vault.note("resources/tfidf-cosine-similarity.md", sources=None)
    assert_single_problem(vault, "'sources'")


def test_research_note_with_empty_sources_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", sources=[])
    assert_single_problem(vault, "'sources'")


def test_sources_are_optional_for_other_types(vault):
    vault.note("resources/tfidf-cosine-similarity.md", type="concept", sources=None)
    assert vault.problems() == []


def test_sources_that_are_not_a_list_are_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", type="concept", sources="https://x.org")
    assert_single_problem(vault, "'sources'")


def test_crlf_line_endings_and_bom_are_accepted(vault):
    path = vault.root / "resources/tfidf-cosine-similarity.md"
    text = path.read_text(encoding="utf-8").replace("\n", "\r\n")
    path.write_bytes(("﻿" + text).encode("utf-8"))
    assert vault.problems() == []


# --- File names and placement ---------------------------------------------------------------


@pytest.mark.parametrize("name", ["TF-IDF.md", "tfidf_similarity.md", "tfidf similarity.md"])
def test_note_names_must_be_kebab_case(vault, name):
    stem = name.removesuffix(".md")
    vault.note(f"resources/{name}")
    vault.link_from_index(stem)
    problems = vault.problems()
    assert any(name in p and "kebab-case" in p for p in problems), problems


@pytest.mark.parametrize(
    ("note_type", "name"),
    [
        ("ai-session", "claude-ci-session"),
        ("meeting", "standup"),
        ("review", "stage-1"),
        ("decision", "ci-tooling"),
    ],
)
def test_type_specific_name_patterns_are_enforced(vault, note_type, name):
    vault.note(f"areas/{name}.md", type=note_type, sources=None)
    vault.link_from_index(name)
    assert_single_problem(vault, f"{name}.md", note_type)


def test_note_outside_para_folders_is_reported(vault):
    vault.note("pagination.md")
    vault.link_from_index("pagination")
    assert_single_problem(vault, "pagination.md", "PARA folder")


def test_duplicate_note_names_are_reported(vault):
    vault.note("inbox/tfidf-cosine-similarity.md", status="inbox")
    problems = vault.problems()
    assert any("duplicate" in p and "tfidf-cosine-similarity" in p for p in problems), problems


def test_duplicate_detection_ignores_case(vault):
    vault.note("inbox/Index.md", status="inbox")
    problems = vault.problems()
    assert any("duplicate" in p for p in problems), problems


def test_nested_folders_inside_para_folders_are_allowed(vault):
    vault.note("areas/youtube-api/pagination.md")
    vault.link_from_index("pagination")
    assert vault.problems() == []


# --- Links ----------------------------------------------------------------------------------


def test_note_without_links_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", body="No links here.\n")
    assert_single_problem(vault, "at least one other note")


def test_link_to_itself_does_not_count(vault):
    vault.note("resources/tfidf-cosine-similarity.md", body="[[tfidf-cosine-similarity]]\n")
    assert_single_problem(vault, "at least one other note")


def test_broken_link_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", body="[[index]] and [[missing-note]]\n")
    assert_single_problem(vault, "broken link", "missing-note")


def test_broken_link_in_index_is_reported(vault):
    vault.link_from_index("ghost")
    assert_single_problem(vault, "index.md", "ghost")


@pytest.mark.parametrize(
    "link",
    [
        "[[index|home]]",
        "[[index#Projects]]",
        "[[index.md]]",
        "[[Index]]",
        "![[index]]",
        "[[index#Projects|home]]",
    ],
)
def test_link_forms_resolve(vault, link):
    vault.note("resources/tfidf-cosine-similarity.md", body=f"{link}\n")
    assert vault.problems() == []


def test_link_to_attachment_resolves(vault):
    vault.write("resources/attachments/diagram.png", "png")
    vault.note("resources/tfidf-cosine-similarity.md", body="[[index]] ![[diagram.png]]\n")
    assert vault.problems() == []


def test_links_inside_code_are_ignored(vault):
    body = "\n\n".join(
        [
            "[[index]]",
            "`[[inline-example]]`",
            "```\n[[fenced-example]]\n```",
            "~~~\n[[tilde]]\n~~~",
        ]
    )
    vault.note("resources/tfidf-cosine-similarity.md", body=body)
    assert vault.problems() == []


def test_empty_link_is_reported(vault):
    vault.note("resources/tfidf-cosine-similarity.md", body="[[index]] [[ ]]\n")
    assert_single_problem(vault, "empty link")


def test_special_files_do_not_need_frontmatter_or_links(vault):
    vault.write("log.md", "# Log\n\nNo links.\n")
    assert vault.problems() == []


# --- Index coverage -------------------------------------------------------------------------


def test_missing_index_is_reported(vault):
    (vault.root / "index.md").unlink()
    vault.write("log.md", "# Log\n")
    problems = vault.problems()
    assert any("index.md" in p and "missing" in p for p in problems), problems


def test_distilled_note_not_linked_from_index_is_reported(vault):
    vault.note("areas/pagination.md")
    assert_single_problem(vault, "pagination.md", "index.md")


@pytest.mark.parametrize(("folder", "status"), [("inbox", "inbox"), ("archive", "archived")])
def test_inbox_and_archive_notes_need_not_be_indexed(vault, folder, status):
    vault.note(f"{folder}/pagination.md", status=status)
    assert vault.problems() == []


# --- Reporting and CLI ----------------------------------------------------------------------


def test_problems_include_path_relative_to_vault(vault):
    vault.note("resources/tfidf-cosine-similarity.md", type="essay")
    problem = vb.validate(vault.root)[0]
    assert problem.path == PurePosixPath("resources/tfidf-cosine-similarity.md")


def test_all_problems_are_reported_not_just_the_first(vault):
    vault.note("resources/tfidf-cosine-similarity.md", type="essay", status="done", body="none\n")
    assert len(vault.problems()) >= 3


def test_problems_are_sorted_by_path(vault):
    vault.note("resources/zeta.md", type="essay")
    vault.note("areas/alpha.md", type="essay")
    vault.link_from_index("zeta", "alpha")
    paths = [p.path for p in vb.validate(vault.root)]
    assert paths == sorted(paths)


def test_main_returns_zero_for_valid_vault(vault, capsys):
    assert vb.main([str(vault.root)]) == 0
    assert "no problems" in capsys.readouterr().out


def test_main_returns_one_and_lists_problems(vault, capsys):
    vault.note("resources/tfidf-cosine-similarity.md", type="essay")
    assert vb.main([str(vault.root)]) == 1
    out = capsys.readouterr().out
    assert "tfidf-cosine-similarity.md" in out and "1 problem" in out


def test_main_defaults_to_brain_directory(tmp_path, monkeypatch, capsys):
    Vault(tmp_path / "brain")
    monkeypatch.chdir(tmp_path)
    assert vb.main([]) == 0


def test_repository_vault_is_valid():
    repo_brain = Path(__file__).resolve().parents[2] / "brain"
    assert [str(p) for p in vb.validate(repo_brain)] == []
