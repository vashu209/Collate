"""Tests for the capability probe."""

from pathlib import Path

import pytest

from organizer.ai import capabilities


def test_rules_always_available():
    caps = capabilities.detect_capabilities()
    assert caps.rules is True


def test_ml_unavailable_when_module_missing(monkeypatch):
    real_find_spec = capabilities.importlib.util.find_spec

    def fake_find_spec(name, *args, **kwargs):
        if name == "onnxruntime":
            return None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(capabilities.importlib.util, "find_spec", fake_find_spec)

    ok, reason = capabilities._ml_available()
    assert ok is False
    assert "onnxruntime" in reason


def test_ml_unavailable_when_model_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(capabilities, "_module_available", lambda name: True)
    monkeypatch.setenv("ORGANIZER_ML_MODEL_DIR", str(tmp_path))

    ok, reason = capabilities._ml_available()
    assert ok is False
    assert "model.onnx" in reason or "tokenizer.json" in reason


def test_ml_available_when_everything_present(monkeypatch, tmp_path: Path):
    (tmp_path / "model.onnx").write_bytes(b"fake")
    (tmp_path / "tokenizer.json").write_text("{}")

    monkeypatch.setattr(capabilities, "_module_available", lambda name: True)
    monkeypatch.setenv("ORGANIZER_ML_MODEL_DIR", str(tmp_path))

    ok, reason = capabilities._ml_available()
    assert ok is True
    assert reason == ""


def test_llm_and_api_are_disabled_stubs():
    caps = capabilities.detect_capabilities()
    assert caps.llm is False
    assert caps.api is False
    assert "llm" in caps.reasons
    assert "api" in caps.reasons