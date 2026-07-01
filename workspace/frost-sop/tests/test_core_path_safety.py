"""
core/path_safety.py 单元测试

测试路径安全验证函数。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FROST_TESTING", "1")

import pytest
from pathlib import Path
from core.path_safety import validate_path, safe_open, get_project_root


class TestGetProjectRoot:
    def test_returns_path(self):
        root = get_project_root()
        assert isinstance(root, Path)
        assert root.exists()


class TestValidatePath:
    def test_valid_relative_path(self, tmp_path):
        (tmp_path / "test.txt").write_text("hello")
        result = validate_path("test.txt", base_dir=tmp_path)
        assert result == str((tmp_path / "test.txt").resolve())

    def test_valid_absolute_path(self, tmp_path):
        (tmp_path / "data.txt").write_text("data")
        abs_path = tmp_path / "data.txt"
        result = validate_path(abs_path, base_dir=tmp_path)
        assert "data.txt" in result

    def test_path_traversal_blocked(self, tmp_path):
        (tmp_path / "file.txt").write_text("safe")
        with pytest.raises(ValueError, match="traversal"):
            validate_path("../etc/passwd", base_dir=tmp_path)

    def test_nonexistent_with_must_exist(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate_path("nonexistent.txt", base_dir=tmp_path, must_exist=True)

    def test_nonexistent_without_must_exist(self, tmp_path):
        result = validate_path("future.txt", base_dir=tmp_path, must_exist=False)
        assert "future.txt" in result

    def test_custom_base_dir(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "inner.txt").write_text("inside")
        result = validate_path("inner.txt", base_dir=subdir)
        assert "inner.txt" in result


class TestSafeOpen:
    def test_read_file(self, tmp_path):
        p = tmp_path / "hello.txt"
        p.write_text("Hello World", encoding="utf-8")
        with safe_open(str(p), base_dir=tmp_path) as f:
            assert f.read() == "Hello World"

    def test_write_file(self, tmp_path):
        p = tmp_path / "output.txt"
        with safe_open(str(p), base_dir=tmp_path, mode="w") as f:
            f.write("new content")
        assert p.read_text() == "new content"

    def test_custom_encoding(self, tmp_path):
        p = tmp_path / "utf16.txt"
        p.write_text("test", encoding="utf-16")
        with safe_open(str(p), base_dir=tmp_path, encoding="utf-16") as f:
            assert "test" in f.read()

    def test_traversal_blocked(self, tmp_path):
        with pytest.raises(ValueError, match="traversal"):
            safe_open("../etc/passwd", base_dir=tmp_path)

    def test_invalid_type(self, tmp_path):
        with pytest.raises(TypeError, match="str or Path"):
            safe_open(123, base_dir=tmp_path)

    def test_must_exist_default_false(self, tmp_path):
        with safe_open("new.txt", base_dir=tmp_path, mode="w") as f:
            f.write("ok")
