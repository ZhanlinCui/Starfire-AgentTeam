"""File operation tools for the coding agent."""

import os
from pathlib import Path
from langchain_core.tools import tool

WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", "/workspace")


@tool
def read_file(path: str) -> dict:
    """Read a file from the workspace.

    Args:
        path: Relative path from workspace root, or absolute path.
    """
    full_path = _resolve(path)
    if not os.path.exists(full_path):
        return {"error": f"File not found: {path}"}

    try:
        content = Path(full_path).read_text()
        lines = content.count("\n") + 1
        return {"path": path, "content": content, "lines": lines}
    except Exception as e:
        return {"error": f"Failed to read {path}: {e}"}


@tool
def write_file(path: str, content: str) -> dict:
    """Write content to a file in the workspace. Creates parent directories if needed.

    Args:
        path: Relative path from workspace root, or absolute path.
        content: The full file content to write.
    """
    full_path = _resolve(path)

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        Path(full_path).write_text(content)
        lines = content.count("\n") + 1
        return {"path": path, "lines": lines, "status": "written"}
    except Exception as e:
        return {"error": f"Failed to write {path}: {e}"}


@tool
def list_files(path: str = ".", pattern: str = "*") -> dict:
    """List files in a directory, optionally filtered by glob pattern.

    Args:
        path: Directory path relative to workspace root.
        pattern: Glob pattern to filter files (e.g. "*.py", "**/*.tsx").
    """
    full_path = _resolve(path)
    if not os.path.isdir(full_path):
        return {"error": f"Not a directory: {path}"}

    try:
        matches = sorted(str(p.relative_to(full_path)) for p in Path(full_path).glob(pattern) if p.is_file())
        return {"path": path, "pattern": pattern, "files": matches[:200], "count": len(matches)}
    except Exception as e:
        return {"error": f"Failed to list {path}: {e}"}


@tool
def search_code(pattern: str, path: str = ".", file_pattern: str = "") -> dict:
    """Search for a text pattern in files. Like grep.

    Args:
        pattern: Text or regex pattern to search for.
        path: Directory to search in.
        file_pattern: Optional file glob filter (e.g. "*.py").
    """
    import re

    full_path = _resolve(path)
    results = []

    try:
        glob_pattern = file_pattern if file_pattern else "**/*"
        for file_path in Path(full_path).glob(glob_pattern):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text()
                for i, line in enumerate(content.splitlines(), 1):
                    if re.search(pattern, line):
                        results.append({
                            "file": str(file_path.relative_to(full_path)),
                            "line": i,
                            "text": line.strip()[:200],
                        })
                        if len(results) >= 50:
                            return {"pattern": pattern, "matches": results, "truncated": True}
            except (UnicodeDecodeError, PermissionError):
                continue

        return {"pattern": pattern, "matches": results, "truncated": False}
    except Exception as e:
        return {"error": f"Search failed: {e}"}


def _resolve(path: str) -> str:
    """Resolve a path relative to workspace root."""
    if os.path.isabs(path):
        return path
    return os.path.join(WORKSPACE_DIR, path)
