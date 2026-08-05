"""Layer 1: the file is a document at all."""

from __future__ import annotations

import pytest

from m365_governance.loader import DocumentError, load_yaml

DUPLICATE = """
id: SPO-SITE-001
severity:
  default: low
severity:
  default: critical
"""

NESTED_DUPLICATE = """
severity:
  default: low
  rationale: one
  default: critical
"""

CLEAN = """
id: SPO-SITE-001
severity:
  default: medium
"""


def test_duplicate_top_level_key_is_rejected(tmp_path):
    path = tmp_path / "rule.yaml"
    path.write_text(DUPLICATE, encoding="utf-8")
    with pytest.raises(DocumentError) as excinfo:
        load_yaml(path)
    assert "duplicate key" in str(excinfo.value)


def test_duplicate_nested_key_is_rejected(tmp_path):
    """The dangerous one: a severity silently overriding another severity."""
    path = tmp_path / "rule.yaml"
    path.write_text(NESTED_DUPLICATE, encoding="utf-8")
    with pytest.raises(DocumentError):
        load_yaml(path)


def test_a_clean_document_loads(tmp_path):
    path = tmp_path / "rule.yaml"
    path.write_text(CLEAN, encoding="utf-8")
    assert load_yaml(path)["severity"]["default"] == "medium"


def test_a_list_at_the_top_level_is_rejected(tmp_path):
    path = tmp_path / "rule.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(DocumentError):
        load_yaml(path)


def test_broken_yaml_is_rejected(tmp_path):
    path = tmp_path / "rule.yaml"
    path.write_text("id: [unclosed\n", encoding="utf-8")
    with pytest.raises(DocumentError):
        load_yaml(path)
