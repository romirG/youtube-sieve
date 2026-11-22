"""Builders for throwaway knowledge-base vaults, shared by the tools tests."""

from pathlib import Path

from tools import validate_brain as vb

VALID_FRONTMATTER = {
    "title": "TF-IDF and cosine similarity",
    "type": "research",
    "status": "distilled",
    "created": "2026-11-19",
    "authors": ["sidtricoder"],
    "tags": ["similarity"],
    "requirements": ["FR-1"],
    "sources": ["https://example.org/article"],
}


def render(frontmatter: dict | None, body: str) -> str:
    if frontmatter is None:
        return body
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(value)}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


class Vault:
    """Builds a minimal valid vault in a temporary directory, then lets a test break one thing."""

    def __init__(self, root: Path):
        self.root = root
        self.write("index.md", "# Index\n\n- [[tfidf-cosine-similarity]]\n- [[log]]\n")
        self.write("log.md", "# Log\n")
        self.write("AGENTS.md", "# Schema\n\nExample: `[[file-name]]`\n")
        self.note("resources/tfidf-cosine-similarity.md")

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def note(self, rel: str, body: str = "See [[index]].\n", **overrides) -> Path:
        frontmatter = {**VALID_FRONTMATTER, **overrides}
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}
        return self.write(rel, render(frontmatter, body))

    def link_from_index(self, *names: str) -> None:
        index = self.root / "index.md"
        extra = "".join(f"- [[{name}]]\n" for name in names)
        index.write_text(index.read_text(encoding="utf-8") + extra, encoding="utf-8")

    def problems(self) -> list[str]:
        return [str(p) for p in vb.validate(self.root)]
