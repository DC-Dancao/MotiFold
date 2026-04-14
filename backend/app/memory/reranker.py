"""
Cross-encoder reranking for memory search.

Uses a neural cross-encoder model to re-rank candidate documents
against the query for improved retrieval precision.
"""
import logging
from typing import List
import asyncio

logger = logging.getLogger(__name__)

# Default cross-encoder model - lightweight and fast
DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Fallback model with better quality
QUALITY_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"


class CrossEncoderReranker:
    """
    Cross-encoder reranker using SentenceTransformers.

    Re-ranks initial retrieval candidates by scoring query-document pairs
    using a neural cross-encoder model.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_CROSS_ENCODER_MODEL,
        device: str = None,
        max_length: int = 512,
    ):
        """
        Initialize cross-encoder reranker.

        Args:
            model_name: HuggingFace model name for cross-encoder
            device: Device to run on ('cpu', 'cuda', 'mps'). Auto-detected if None.
            max_length: Maximum sequence length
        """
        self.model_name = model_name
        self.device = device or self._detect_device()
        self.max_length = max_length
        self._model = None

    def _detect_device(self) -> str:
        """Auto-detect the best available device."""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=self.max_length,
            )
            logger.info(f"Loaded cross-encoder model: {self.model_name} on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}")
            raise

    async def rerank(
        self,
        query: str,
        candidates: List[dict],
        top_k: int = 5,
    ) -> List[dict]:
        """
        Re-rank candidates using cross-encoder scores.

        Args:
            query: The search query
            candidates: List of candidate dicts with 'id', 'content', 'similarity'
            top_k: Number of top results to return

        Returns:
            Re-ranked list of candidates with cross-encoder scores
        """
        if not candidates:
            return []

        # Load model if not already loaded
        if self._model is None:
            self._load_model()

        # Prepare query-document pairs
        pairs = [[query, candidate["content"]] for candidate in candidates]

        # Score in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            self._model.predict,
            pairs,
        )

        # Handle different score formats (can be 1D or 2D array)
        if hasattr(scores, 'tolist'):
            scores = scores.tolist()
        if isinstance(scores[0], list):
            scores = [s[0] for s in scores]

        # Normalize scores with sigmoid
        normalized_scores = [self._sigmoid(s) for s in scores]

        # Combine original similarity with cross-encoder score
        # Use a weighted combination: 0.3 * original + 0.7 * cross-encoder
        combined_results = []
        for i, candidate in enumerate(candidates):
            original_sim = candidate.get("similarity", 0.0)
            ce_score = normalized_scores[i]
            combined_score = 0.3 * original_sim + 0.7 * ce_score

            combined_results.append({
                **candidate,
                "cross_encoder_score": ce_score,
                "combined_score": combined_score,
            })

        # Sort by combined score descending
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)

        return combined_results[:top_k]

    def _sigmoid(self, x: float) -> float:
        """Sigmoid function for score normalization."""
        import math
        return 1 / (1 + math.exp(-x))


# Global singleton
_reranker_instance = None


def get_reranker() -> CrossEncoderReranker:
    """Get or create the global reranker instance."""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = CrossEncoderReranker()
    return _reranker_instance
