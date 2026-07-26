"""Step 0 の Python 環境と必須依存関係を確認するスモークテスト。"""

import importlib
import sys

import pytest


@pytest.mark.parametrize(
    "module_name",
    ("PySide6", "numpy", "pyqtgraph", "pydantic", "yaml"),
)
def test_required_dependency_can_be_imported(module_name: str) -> None:
    """pyproject.toml の必須依存関係を import できる。"""
    assert importlib.import_module(module_name) is not None


def test_supported_python_version() -> None:
    """実行中の Python がサポート範囲内である。"""
    assert (3, 11) <= sys.version_info[:2] < (3, 14)
