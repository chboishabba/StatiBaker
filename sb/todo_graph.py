from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CHECKBOX_RE = re.compile(r"^(?P<indent>\s*)([-*+]|\d+\.)\s+\[(?P<mark>[ xX])\]\s+(?P<text>.+?)\s*$")
BULLET_RE = re.compile(r"^(?P<indent>\s*)([-*+]|\d+\.)\s+(?P<text>.+?)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(?P<text>.+?)\s*$")
BACKTICK_RE = re.compile(r"`([^`]+)`")
PATH_TOKEN_RE = re.compile(r"(?P<token>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+|[A-Za-z0-9_.-]+\.(?:py|md|json|yaml|yml|sh|ts|tsx|js|jsx|svelte|txt))")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_/-]{2,}")
STOPWORDS = {
    "add",
    "and",
    "for",
    "from",
    "into",
    "keep",
    "make",
    "next",
    "path",
    "real",
    "route",
    "task",
    "that",
    "the",
    "this",
    "todo",
    "use",
    "with",
}
SOURCE_FILES = ("TODO.md", "todo.md")


@dataclass(frozen=True)
class TodoItem:
    obligation_id: str
    source_path: str
    line_no: int
    section_path: list[str]
    text: str
    state: str
    indent: int
    source_kind: str


def _hash(*parts: str) -> str:
    return "sha256:" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def discover_todo_files(repo_root: str | Path) -> list[Path]:
    root = Path(repo_root).expanduser().resolve()
    results: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in {".git", ".venv", "node_modules", "__pycache__", "runs"}]
        for name in filenames:
            if name in SOURCE_FILES:
                results.append(Path(dirpath) / name)
    return sorted(results)


def _source_kind(path: Path) -> str:
    lowered = str(path).replace("\\", "/").lower()
    return "daily_todo_log" if "/logs/todo/" in lowered else "project_todo_file"


def parse_todo_file(path: str | Path, *, repo_root: str | Path) -> list[dict[str, Any]]:
    target = Path(path).expanduser().resolve()
    root = Path(repo_root).expanduser().resolve()
    rel = str(target.relative_to(root)) if target.is_relative_to(root) else str(target)
    lines = target.read_text(encoding="utf-8").splitlines()
    headings: list[str] = []
    items: list[TodoItem] = []

    for line_no, line in enumerate(lines, start=1):
        heading = HEADING_RE.match(line)
        if heading:
            level = len(line) - len(line.lstrip("#"))
            text = str(heading.group("text") or "").strip()
            if level <= len(headings):
                headings = headings[: level - 1]
            headings.append(text)
            continue

        match = CHECKBOX_RE.match(line) or BULLET_RE.match(line)
        if not match:
            continue

        indent = len(match.group("indent") or "")
        text = str(match.group("text") or "").strip()
        if not text:
            continue

        mark = match.groupdict().get("mark")
        section_text = " / ".join(headings).lower()
        if mark and str(mark).lower() == "x":
            state = "checked_complete"
        elif "completed" in section_text or "done" in section_text:
            state = "checked_complete"
        elif mark is None:
            state = "open"
        else:
            state = "open"

        obligation_id = _hash(rel, str(line_no), text)
        items.append(
            TodoItem(
                obligation_id=obligation_id,
                source_path=rel,
                line_no=line_no,
                section_path=list(headings),
                text=text,
                state=state,
                indent=indent,
                source_kind=_source_kind(target),
            )
        )

    return [
        {
            "obligation_id": item.obligation_id,
            "source_path": item.source_path,
            "line_no": item.line_no,
            "section_path": item.section_path,
            "text": item.text,
            "state": item.state,
            "indent": item.indent,
            "source_kind": item.source_kind,
        }
        for item in items
    ]


def _extract_refs(text: str) -> tuple[list[str], list[str]]:
    refs = [item.strip() for item in BACKTICK_RE.findall(text) if item.strip()]
    path_refs: list[str] = []
    symbol_refs: list[str] = []
    for ref in refs:
        if "/" in ref or "." in Path(ref).name:
            path_refs.append(ref)
        else:
            symbol_refs.append(ref)
    for token in PATH_TOKEN_RE.findall(text):
        token = token.strip()
        if token and token not in path_refs:
            path_refs.append(token)
    return path_refs, symbol_refs


def _template_family(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("remove", "delete", "drop", "retire")):
        return "removal"
    if any(word in lowered for word in ("document", "docs", "record", "explain")):
        return "docs"
    if any(word in lowered for word in ("test", "tests", "coverage")):
        return "testing"
    if any(word in lowered for word in ("support", "query", "route", "adapter", "integrat", "wire", "cli")):
        return "integration"
    if any(word in lowered for word in ("fix", "resolve", "diagnose")):
        return "fix"
    if any(word in lowered for word in ("add", "implement", "create", "build", "emit", "expose", "surface", "generate")):
        return "build"
    return "unknown"


def _looks_like_symbol(ref: str) -> bool:
    return "/" not in ref and bool(re.search(r"[A-Za-z_]", ref))


def _repo_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in {".git", ".venv", "node_modules", "__pycache__", "runs"}]
        for name in filenames:
            files.append(Path(dirpath) / name)
    return files


def _resolve_paths(root: Path, ref: str) -> list[Path]:
    target = (root / ref).resolve()
    if target.exists():
        return [target]
    if "/" not in ref:
        matches = [path for path in _repo_files(root) if path.name == ref]
        if matches:
            return matches[:10]
    return []


def _rg_search(root: Path, pattern: str) -> list[str]:
    if not pattern:
        return []
    try:
        proc = subprocess.run(
            ["rg", "-n", "-F", pattern, str(root)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return []
    if proc.returncode not in {0, 1}:
        return []
    out: list[str] = []
    for line in proc.stdout.splitlines():
        path = line.split(":", 1)[0].strip()
        if path:
            out.append(path)
    return out


def _git_last_touch(root: Path, ref: str) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "log", "-n", "1", "--format=%H%x1f%cI", "--", ref],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.strip()
    if not text:
        return None
    commit_hash, _, commit_ts = text.partition("\x1f")
    if not commit_hash:
        return None
    return {
        "kind": "git_commit",
        "hash": commit_hash,
        "ts": commit_ts or None,
        "target": ref,
    }


def _test_token_set(text: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(text) if token.lower() not in STOPWORDS}


def _matching_tests(root: Path, text: str) -> list[str]:
    tokens = _test_token_set(text)
    if not tokens:
        return []
    out: list[str] = []
    for path in _repo_files(root):
        lowered = path.name.lower()
        if "test" not in lowered and "/tests/" not in str(path).replace("\\", "/").lower():
            continue
        score = sum(1 for token in tokens if token in lowered)
        if score > 0:
            out.append(str(path.relative_to(root)))
    return sorted(out)[:10]


def derive_predicates(obligation: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(obligation.get("text") or "")
    family = _template_family(text)
    path_refs, symbol_refs = _extract_refs(text)
    predicates: list[dict[str, Any]] = []

    if family in {"build", "integration", "docs", "fix"}:
        for ref in path_refs:
            predicates.append({"predicate_kind": "path_exists", "target": ref, "required": True})
        for ref in symbol_refs:
            if _looks_like_symbol(ref):
                predicates.append({"predicate_kind": "symbol_present", "target": ref, "required": True})
    elif family == "removal":
        for ref in path_refs:
            predicates.append({"predicate_kind": "path_absent", "target": ref, "required": True})
        for ref in symbol_refs:
            if _looks_like_symbol(ref):
                predicates.append({"predicate_kind": "symbol_absent", "target": ref, "required": True})

    if family in {"build", "integration", "fix", "testing"} and "test" in text.lower():
        predicates.append({"predicate_kind": "tests_present", "target": None, "required": True})

    if family != "unknown" and (path_refs or symbol_refs):
        predicates.append({"predicate_kind": "git_evidence", "target": path_refs[0] if path_refs else symbol_refs[0], "required": False})

    if not predicates:
        predicates.append({"predicate_kind": "needs_human_review", "target": None, "required": True})
    return predicates


def evaluate_obligation(obligation: dict[str, Any], *, repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve()
    predicates = derive_predicates(obligation)
    evidence_links: list[dict[str, Any]] = []
    evaluated: list[dict[str, Any]] = []
    satisfied_required = 0
    total_required = 0
    contradiction = False
    review_required = False

    for index, predicate in enumerate(predicates):
        kind = str(predicate.get("predicate_kind") or "")
        target = predicate.get("target")
        required = bool(predicate.get("required"))
        if required:
            total_required += 1
        satisfied = False
        details: dict[str, Any] = {}

        if kind == "path_exists" and isinstance(target, str):
            matches = [str(path.relative_to(root)) for path in _resolve_paths(root, target)]
            satisfied = bool(matches)
            details["matches"] = matches
            if satisfied:
                evidence_links.append({"kind": "path_exists", "target": target, "matches": matches})
                touch = _git_last_touch(root, target)
                if touch:
                    evidence_links.append(touch)
        elif kind == "path_absent" and isinstance(target, str):
            matches = [str(path.relative_to(root)) for path in _resolve_paths(root, target)]
            satisfied = not matches
            details["matches"] = matches
            if not satisfied:
                contradiction = True
                evidence_links.append({"kind": "path_present", "target": target, "matches": matches})
        elif kind == "symbol_present" and isinstance(target, str):
            matches = _rg_search(root, target)[:10]
            satisfied = bool(matches)
            details["matches"] = matches
            if satisfied:
                evidence_links.append({"kind": "symbol_present", "target": target, "matches": matches})
        elif kind == "symbol_absent" and isinstance(target, str):
            matches = _rg_search(root, target)[:10]
            satisfied = not matches
            details["matches"] = matches
            if not satisfied:
                contradiction = True
                evidence_links.append({"kind": "symbol_present", "target": target, "matches": matches})
        elif kind == "tests_present":
            matches = _matching_tests(root, str(obligation.get("text") or ""))
            satisfied = bool(matches)
            details["matches"] = matches
            if satisfied:
                evidence_links.append({"kind": "tests_present", "matches": matches})
        elif kind == "git_evidence" and isinstance(target, str):
            touch = _git_last_touch(root, target)
            satisfied = touch is not None
            details["touch"] = touch
            if touch:
                evidence_links.append(touch)
        elif kind == "needs_human_review":
            review_required = True
            satisfied = False
        else:
            review_required = True

        if required and satisfied:
            satisfied_required += 1

        evaluated.append(
            {
                "predicate_id": _hash(str(obligation.get("obligation_id") or ""), str(index), kind, str(target)),
                "predicate_kind": kind,
                "target": target,
                "required": required,
                "satisfied": satisfied,
                "details": details,
            }
        )

    state = str(obligation.get("state") or "open")
    text = str(obligation.get("text") or "").lower()
    if "@blocker" in text or " blocker" in text:
        classification = "blocked"
    elif review_required:
        classification = "needs_human_review"
    elif contradiction:
        classification = "contradicted"
    elif total_required > 0 and satisfied_required == total_required:
        classification = "likely_complete"
    elif total_required > 0 and satisfied_required > 0:
        classification = "partially_satisfied"
    elif state == "checked_complete":
        classification = "contradicted"
    else:
        classification = "stale"

    candidate = None
    if classification in {"likely_complete", "partially_satisfied"}:
        candidate = {
            "candidate_id": _hash(str(obligation.get("obligation_id") or ""), classification),
            "version": "todo_completion_candidate_v1",
            "obligation_id": obligation.get("obligation_id"),
            "source_path": obligation.get("source_path"),
            "line_no": obligation.get("line_no"),
            "status": classification,
            "confidence": "high" if classification == "likely_complete" else "medium",
            "evidence_refs": evidence_links[:10],
        }

    reason_codes: list[str] = []
    if review_required:
        reason_codes.append("needs_human_review")
    if contradiction:
        reason_codes.append("contradiction")
    if classification == "stale":
        reason_codes.append("no_satisfying_evidence")

    return {
        "obligation": dict(obligation),
        "predicates": evaluated,
        "evidence_links": evidence_links[:20],
        "classification": classification,
        "reason_codes": reason_codes,
        "candidate": candidate,
    }


def _score_bucket(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def _alignment_for_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    obligations = [item.get("obligation", {}) for item in evaluations]
    open_items = [item for item in obligations if str(item.get("state") or "") != "checked_complete"]
    complete_like = [item for item in evaluations if item.get("classification") == "likely_complete"]
    source_completed = [item for item in obligations if str(item.get("state") or "") == "checked_complete"]

    coverage_num = sum(1 for item in evaluations if item.get("classification") in {"likely_complete", "partially_satisfied"})
    coverage_den = max(1, len(open_items))
    coverage_score = _score_bucket(coverage_num / coverage_den)

    closure_num = sum(
        1
        for item in evaluations
        if str(item.get("classification") or "") == "likely_complete"
        or str((item.get("obligation") or {}).get("state") or "") == "checked_complete"
    )
    closure_den = max(1, len(source_completed) + len(complete_like))
    closure_score = _score_bucket(closure_num / closure_den)

    required_total = 0
    required_sat = 0
    evidence_total = 0
    evidence_linked = 0
    penalty_counts = Counter()
    support_counts = Counter()
    for item in evaluations:
        predicates = item.get("predicates") if isinstance(item.get("predicates"), list) else []
        evidence = item.get("evidence_links") if isinstance(item.get("evidence_links"), list) else []
        evidence_total += max(1, len(predicates))
        evidence_linked += len(evidence)
        classification = str(item.get("classification") or "")
        if classification == "likely_complete":
            support_counts["supported_completions"] += 1
        elif classification == "partially_satisfied":
            support_counts["partially_satisfied"] += 1
        elif classification == "contradicted":
            penalty_counts["contradicted_obligations"] += 1
        elif classification == "stale":
            penalty_counts["stale_open_items"] += 1
        elif classification == "blocked":
            penalty_counts["blocked_by_missing_evidence"] += 1
        elif classification == "needs_human_review":
            penalty_counts["needs_human_review"] += 1
        for predicate in predicates:
            if not isinstance(predicate, dict) or not predicate.get("required"):
                continue
            required_total += 1
            if predicate.get("satisfied"):
                required_sat += 1
                support_counts["fully_satisfied_predicates"] += 1
            else:
                penalty_counts["unmet_required_predicates"] += 1

    predicate_score = _score_bucket(required_sat / max(1, required_total))
    focus_score = _score_bucket(evidence_linked / max(1, evidence_total))
    efficiency_score = _score_bucket(
        (support_counts["supported_completions"] + support_counts["partially_satisfied"])
        / max(1, len(evaluations) + penalty_counts["contradicted_obligations"] + penalty_counts["stale_open_items"])
    )
    evidence_score = _score_bucket(
        (support_counts["fully_satisfied_predicates"] + support_counts["supported_completions"])
        / max(1, required_total + penalty_counts["needs_human_review"])
    )

    task_alignment_score = _score_bucket(
        0.25 * coverage_score
        + 0.20 * closure_score
        + 0.20 * predicate_score
        + 0.15 * focus_score
        + 0.10 * efficiency_score
        + 0.10 * evidence_score
    )

    return {
        "version": "todo_alignment_v1",
        "task_alignment_score": task_alignment_score,
        "coverage_score": coverage_score,
        "closure_score": closure_score,
        "predicate_score": predicate_score,
        "focus_score": focus_score,
        "efficiency_score": efficiency_score,
        "evidence_score": evidence_score,
        "penalty_counts": dict(sorted(penalty_counts.items())),
        "support_counts": dict(sorted(support_counts.items())),
        "obligation_counts": {
            "total": len(obligations),
            "open": len(open_items),
            "source_completed": len(source_completed),
            "likely_complete": len(complete_like),
        },
    }


def analyze_repo_todos(repo_root: str | Path, *, todo_paths: Iterable[str | Path] | None = None) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve()
    selected = [Path(path).expanduser().resolve() for path in (todo_paths or discover_todo_files(root))]
    obligations: list[dict[str, Any]] = []
    for path in selected:
        if path.exists():
            obligations.extend(parse_todo_file(path, repo_root=root))

    evaluations = [evaluate_obligation(item, repo_root=root) for item in obligations]
    candidates = [item["candidate"] for item in evaluations if isinstance(item.get("candidate"), dict)]

    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evaluations:
        obligation = item.get("obligation") if isinstance(item.get("obligation"), dict) else {}
        by_file[str(obligation.get("source_path") or "unknown")].append(item)

    per_file_alignment = {
        path: _alignment_for_evaluations(items)
        for path, items in sorted(by_file.items(), key=lambda pair: pair[0])
    }

    return {
        "version": "todo_graph_v1",
        "repo_root": str(root),
        "todo_files": [str(path.relative_to(root)) if path.is_relative_to(root) else str(path) for path in selected],
        "obligations": obligations,
        "evaluations": evaluations,
        "completion_candidates": candidates,
        "alignment": {
            "project": _alignment_for_evaluations(evaluations),
            "by_file": per_file_alignment,
        },
    }
