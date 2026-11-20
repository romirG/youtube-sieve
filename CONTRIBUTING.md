# Contributing to youtube-sieve

Thanks for contributing. This document describes how work moves from an idea to `main`.

## Workflow at a glance

1. **Open an issue** using a template. Describe the context, scope and acceptance criteria.
2. **Create a branch** from an up-to-date `main`.
3. **Commit** in small, logical steps using Conventional Commits.
4. **Open a pull request** that closes the issue, and request a reviewer.
5. **Address review**, get at least one approval and green checks.
6. **Squash-merge**, then delete the branch.

`main` is protected: nobody pushes to it directly, including administrators.

## Issues

- Every change starts with an issue, including documentation and knowledge-base notes.
- Add labels for **type** (`type: feature`, `type: bug`, `type: docs`, `type: chore`, `type: test`, `type: ci`) and **area** (`area: brain`, `area: mcp`, `area: repo`).
- Assign the issue to yourself before starting, so work is not duplicated.
- Reference SRS requirement IDs (for example `FR-1`) where relevant.

## Branches

Name branches `<type>/<issue-number>-<short-slug>`:

```
feat/12-similar-videos
fix/31-duration-parsing
docs/8-tfidf-research-note
chore/3-governance-files
```

Keep branches short-lived. Rebase on `main` if it moves ahead while you work.

## Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <imperative summary, at most 72 characters>

<optional body explaining why>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `perf`.
Write in the imperative mood ("add", not "added"). Do not mix unrelated changes in one commit.

## Pull requests

- One issue per pull request. Aim for fewer than about 400 changed lines.
- Fill in every section of the template, and write `Closes #<n>`.
- Open a **draft** pull request early if you want feedback on direction.
- The pull request title becomes the squash commit on `main`, so it must follow Conventional Commits.

## Review

- Every pull request needs **at least one approval from someone other than the author**.
- Reviewers check correctness, tests, readability and security; linters handle style.
- Keep comments about the code. Prefix minor points with `nit:` and explain the reason for a requested change.
- Authors reply to or resolve every comment. Authors never merge without an approval.

## Definition of Done

A change is done when:

- [ ] the issue's acceptance criteria are all met;
- [ ] tests are added or updated and pass;
- [ ] documentation and `CHANGELOG.md` are updated;
- [ ] CI is green;
- [ ] it has been reviewed and approved.

## AI-assisted work

AI coding assistants are welcome, but the author is responsible for every merged line.

- Disclose AI assistance in the pull request.
- A human reviews every AI-generated change.
- Never paste secrets, tokens or credentials into an AI tool.
- Record significant AI sessions in the knowledge base (`brain/`).

## Running checks locally

CI runs these on every pull request; run them before you push. You need Python 3.12 and pip 25.1 or newer.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --group dev

ruff check .                      # lint
ruff format .                     # format (CI runs: ruff format --check .)
pytest --cov                      # tests, fails below 90% coverage
python -m tools.validate_brain    # knowledge-base schema
```

## Security

Never commit secrets, OAuth client files, tokens or real user data. `.env` and `client_secret*.json` are ignored by git; use `.env.example` for documented placeholders.
