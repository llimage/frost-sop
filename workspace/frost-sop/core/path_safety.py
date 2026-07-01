"""
Path traversal protection for file operations.

Per OWASP ASVS 4.0 L1 §5.3.4 — Path Traversal Prevention.

Audit: S-003 fix (2026-07-01)

Usage:
    from core.path_safety import safe_open, validate_path

    # Read file within project directory
    with safe_open(yaml_path, project_root, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Or just validate
    safe_path = validate_path(user_path, project_root)
"""

from pathlib import Path

# Project root for path containment checks
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def validate_path(
    path: str | Path,
    base_dir: str | Path | None = None,
    must_exist: bool = True,
) -> str:
    """
    Validate a file path is safe (no path traversal).

    Returns resolved absolute path string.

    Raises ValueError if path is unsafe.
    """
    if base_dir is None:
        base_dir = _PROJECT_ROOT

    base_dir = Path(base_dir).resolve()
    target = (base_dir / Path(path)).resolve()

    # Check traversal: resolved path must be within base_dir
    try:
        target.relative_to(base_dir)
    except ValueError:
        raise ValueError(f"Path traversal detected: '{path}' resolves outside '{base_dir}'")

    # Check symlink loops (optional but good practice)
    if target.is_symlink():
        resolved_symlink = target.resolve()
        try:
            resolved_symlink.relative_to(base_dir)
        except ValueError:
            raise ValueError(f"Symlink traversal detected: '{path}' targets outside '{base_dir}'")

    if must_exist and not target.exists():
        raise FileNotFoundError(f"File not found: {target}")

    return str(target)


def safe_open(
    path: str | Path,
    base_dir: str | Path | None = None,
    mode: str = "r",
    encoding: str = "utf-8",
    must_exist: bool = False,
):
    """
    Open a file safely, preventing path traversal.

    Returns a file object (use with `with` statement).

    Args:
        path: Relative or absolute path
        base_dir: Allowed base directory (default: project root)
        mode: File mode (default: "r")
        encoding: File encoding (default: "utf-8")
        must_exist: If True, requires file to exist (default: False)

    Raises ValueError on path traversal attempt.
    """
    if not isinstance(path, (str, Path)):
        raise TypeError(f"Expected str or Path, got {type(path).__name__}")

    safe_path = validate_path(path, base_dir, must_exist=must_exist)
    return open(safe_path, mode=mode, encoding=encoding)


def get_project_root() -> Path:
    """Return the project root directory."""
    return _PROJECT_ROOT
