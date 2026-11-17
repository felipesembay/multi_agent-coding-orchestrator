"""Validate repository documentation without network access or dependencies."""
import argparse
from datetime import date
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


TASK_ID = re.compile(r"\bV2-[A-Z]+-\d{3}\b")
LINK_START = re.compile(r"!?\[[^\]\n]*\]\(")


def destination(text):
    """Read an angle-wrapped or balanced Markdown link destination."""
    text = text.lstrip()
    if text.startswith("<"):
        end = text.find(">")
        return text[1:end] if end >= 0 else text[1:]
    depth = 0
    for index, char in enumerate(text):
        if char.isspace() or (char == ")" and depth == 0):
            return text[:index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
    return text


def link_targets(text):
    for match in LINK_START.finditer(text):
        yield destination(text[match.end():])
    # Reference definitions cover full, collapsed and shortcut references.
    for match in re.finditer(r"^ {0,3}\[[^]\n]+\]:[ \t]*(.+)$", text, re.M):
        yield destination(match.group(1))


def prose(text):
    """Ignore fenced examples and inline code when finding Markdown links."""
    text = re.sub(r"^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text, flags=re.M | re.S)
    return re.sub(r"`[^`\n]+`", "", text)


def anchors(text):
    result = set()
    counts = {}
    for heading in re.findall(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", text, re.M):
        heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if not count else "{}-{}".format(slug, count))
    result.update(re.findall(r'\b(?:id|name)=[\"\']([^\"\']+)[\"\']', text))
    return result


def check_docs(root):
    root = Path(root).resolve()
    errors = []
    backlog = root / "docs/planning/BACKLOG.md"
    if not backlog.is_file():
        return ["docs/planning/BACKLOG.md: arquivo obrigatório ausente"]
    known_ids = set(re.findall(r"^\|\s*(V2-[A-Z]+-\d{3})\s*\|", backlog.read_text(), re.M))
    files = set((root / "docs").rglob("*.md"))
    files.update(p for p in (root / "README.md", root / "AGENTS.md", root / "CLAUDE.md", root / "frontend/README.md") if p.is_file())
    for path in sorted(files):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root)
        for task in sorted(set(TASK_ID.findall(text)) - known_ids):
            errors.append("{}: ID desconhecido {}".format(relative, task))
        for target in link_targets(prose(text)):
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            destination = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not destination.exists():
                errors.append("{}: link quebrado {}".format(relative, target))
            elif url.fragment and destination.suffix == ".md" and unquote(url.fragment) not in anchors(destination.read_text(encoding="utf-8")):
                errors.append("{}: âncora inexistente {}".format(relative, target))
    current = root / "docs/handoff/CURRENT_STATE.md"
    if not current.is_file():
        errors.append("docs/handoff/CURRENT_STATE.md: arquivo obrigatório ausente")
        return errors
    updated = re.search(r"^Atualizado:\s*(\d{4}-\d{2}-\d{2})", current.read_text(), re.M)
    try:
        updated_date = date.fromisoformat(updated.group(1)) if updated else None
    except ValueError:
        updated_date = None
    if updated_date is None:
        errors.append("docs/handoff/CURRENT_STATE.md: data Atualizado ausente ou inválida")
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", "orchestrator", "frontend", "scripts", "tests", ".github", "requirements.txt", "pytest.ini"],
            cwd=root, capture_output=True, text=True, check=True,
        )
        latest = result.stdout.strip()
        if latest and updated_date and updated_date < date.fromisoformat(latest):
            errors.append("docs/handoff/CURRENT_STATE.md: data anterior ao último commit de código ({})".format(latest))
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        errors.append("Não foi possível verificar histórico Git: {}".format(exc))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = check_docs(args.root)
    for error in errors:
        print(error)
    if not errors:
        print("Documentação válida: links, IDs e data do handoff.")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
