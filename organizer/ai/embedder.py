"""ONNX-backed sentence embedder using quantized MiniLM-L6-v2."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence, cast

import numpy as np

from organizer.ai.base import Embedder

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = Path(__file__).parent / "models" / "minilm-l6-v2"
_EMBED_DIM = 384
_MAX_LENGTH = 256


class AIEmbedder(Embedder):
    """Concrete Embedder that runs quantized MiniLM-L6-v2 via onnxruntime.

    Lazy loading: the ONNX session and tokenizer are initialized on first
    use. This keeps `organizer --help` fast for users who never invoke ML.
    """

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        *,
        threads: Optional[int] = None,
    ) -> None:
        self.model_dir = Path(model_dir) if model_dir else _DEFAULT_MODEL_DIR
        self._threads = threads
        self._session = None
        self._tokenizer = None
        self._input_names: set[str] = set()

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return

        onnx_path = self.model_dir / "model.onnx"
        tok_path = self.model_dir / "tokenizer.json"
        if not onnx_path.exists() or not tok_path.exists():
            raise FileNotFoundError(
                f"MiniLM model files missing in {self.model_dir}. "
                "Run: python scripts/fetch_ml_model.py"
            )

        import onnxruntime as ort
        from tokenizers import Tokenizer

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if self._threads is not None:
            opts.intra_op_num_threads = self._threads

        logger.info("Loading ONNX model from %s", onnx_path)
        self._session = ort.InferenceSession(
            str(onnx_path),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {i.name for i in self._session.get_inputs()}

        self._tokenizer = Tokenizer.from_file(str(tok_path))
        self._tokenizer.enable_truncation(max_length=_MAX_LENGTH)
        self._tokenizer.enable_padding(
            length=_MAX_LENGTH,
            pad_id=0,
            pad_token="[PAD]",
        )

    def generate_embedding(self, text: str) -> Sequence[float]:
        """Return a 384-dim, L2-normalized embedding for a single string."""
        return self.encode_batch([text])[0]

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Return one 384-dim vector per input. Faster than N single calls."""
        if not texts:
            return []

        self._ensure_loaded()
        assert self._tokenizer is not None and self._session is not None

        encodings = self._tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

        feed: dict[str, np.ndarray] = {}
        if "input_ids" in self._input_names:
            feed["input_ids"] = input_ids
        if "attention_mask" in self._input_names:
            feed["attention_mask"] = attention_mask
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.zeros_like(input_ids, dtype=np.int64)

        outputs = self._session.run(None, feed)
        tensor = cast(np.ndarray, outputs[0])

        if tensor.ndim == 3:
            mask = attention_mask[..., None].astype(np.float32)
            summed = tensor * mask
            counts = np.maximum(mask.sum(axis=1), 1e-9)
            pooled = summed.sum(axis=1) / counts
        elif tensor.ndim == 2:
            pooled = tensor.astype(np.float32)
        else:
            raise RuntimeError(f"Unexpected ONNX output rank: {tensor.shape}")

        norms = np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
        normalized = pooled / norms

        return [vec.tolist() for vec in normalized]