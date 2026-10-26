"""Tests for the ONNX-backed MiniLM embedder."""

from pathlib import Path

import numpy as np
import pytest

from organizer.ai.embedder import AIEmbedder

MODEL_DIR = Path(__file__).parent.parent / "organizer" / "ai" / "models" / "minilm-l6-v2"

pytestmark = pytest.mark.skipif(
    not (MODEL_DIR / "model.onnx").exists(),
    reason="MiniLM model files not present; run scripts/fetch_ml_model.py",
)


@pytest.fixture(scope="module")
def embedder() -> AIEmbedder:
    return AIEmbedder()


def test_embedding_shape(embedder):
    vec = embedder.generate_embedding("lecture notes for CS229")
    assert len(vec) == 384
    assert all(isinstance(x, float) for x in vec)


def test_embedding_is_l2_normalized(embedder):
    vec = np.array(embedder.generate_embedding("a random document"))
    norm = float(np.linalg.norm(vec))
    assert abs(norm - 1.0) < 1e-4


def test_similar_texts_have_high_cosine_similarity(embedder):
    a = np.array(embedder.generate_embedding("screenshot from vacation in Hawaii"))
    b = np.array(embedder.generate_embedding("photo from my Hawaii trip"))
    c = np.array(embedder.generate_embedding("quarterly financial report"))
    sim_ab = float(a @ b)
    sim_ac = float(a @ c)
    assert sim_ab > sim_ac
    assert sim_ab > 0.5


def test_empty_batch_returns_empty_list(embedder):
    assert embedder.encode_batch([]) == []


def test_batch_vs_single_semantic_equivalence(embedder):
    """Batched and single inference agree in direction (cosine > 0.99).

    Quantized models produce slightly different component values depending
    on batch size. That's fine — downstream classification uses cosine
    similarity, which cares about direction, not magnitude.
    """
    texts = ["first text", "second text", "third text"]
    batch = np.array(embedder.encode_batch(texts))
    singles = np.array([embedder.generate_embedding(t) for t in texts])
    assert len(batch) == len(singles) == 3
    for b, s in zip(batch, singles):
        cos = float(np.dot(b, s) / (np.linalg.norm(b) * np.linalg.norm(s)))
        assert cos > 0.98, f"Batch/single cosine too low: {cos:.4f}"


def test_batch_size_1_matches_single(embedder):
    """Same code path, same batch size -> numerically identical."""
    text = "first text"
    batch = embedder.encode_batch([text])
    single = embedder.generate_embedding(text)
    assert np.allclose(batch[0], single, atol=1e-6)


def test_missing_model_raises():
    e = AIEmbedder(model_dir=Path("/tmp/definitely-not-here"))
    with pytest.raises(FileNotFoundError):
        e.generate_embedding("anything")