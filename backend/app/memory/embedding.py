"""
Embedding service using SentenceTransformers.

Uses BAAI/bge-m3 model which supports 100+ languages including Chinese.
"""

import logging
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)

# Default model - supports Chinese and 100+ languages
DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_DIMENSION = 1024  # BGE-M3 output dimension


class EmbeddingService:
    """
    Local embedding service using SentenceTransformers.

    Uses BAAI/bge-m3 model which is optimized for multilingual retrieval,
    with excellent Chinese support.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        normalize: bool = True,
    ):
        """
        Initialize embedding service.

        Args:
            model_name: HuggingFace model name for SentenceTransformers
            device: Device to use ('cuda', 'cpu', or None for auto-detection)
            normalize: Whether to normalize embeddings (recommended for cosine similarity)
        """
        self.model_name = model_name
        self.device = device or self._detect_device()
        self.normalize = normalize
        self._model = None
        self._dimension: Optional[int] = None

    def _detect_device(self) -> str:
        """Auto-detect the best available device."""
        try:
            import torch
        except ModuleNotFoundError:
            return "cpu"

        if torch.cuda.is_available():
            return "cuda"
        try:
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    async def initialize(self) -> None:
        """
        Initialize the embedding model.

        Should be called once during application startup to avoid cold-start latency.
        """
        if self._model is not None:
            return

        logger.info(f"Initializing embedding model: {self.model_name} on {self.device}")

        # Run model loading in executor to avoid blocking
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            None,
            self._load_model,
        )

        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(f"Embedding initialized: {self.model_name}, dimension={self._dimension}")

    def _load_model(self):
        """Load the SentenceTransformer model (runs in thread pool)."""
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            self.model_name,
            device=self.device,
            backend="torch",
        )

    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        if self._dimension is None:
            raise RuntimeError(
                "Embedding service not initialized. Call initialize() first."
            )
        return self._dimension

    def encode(self, texts: list[str]) -> list[list[float]]:
        """
        Encode texts into embedding vectors.

        Args:
            texts: List of text strings to encode

        Returns:
            List of embedding vectors (each is a list of floats)
        """
        if self._model is None:
            # Auto-initialize if not yet initialized (lazy loading)
            self._model = self._load_model()
            self._dimension = self._model.get_sentence_embedding_dimension()

        embeddings = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )

        return [emb.tolist() for emb in embeddings]

    async def aencode(self, texts: list[str]) -> list[list[float]]:
        """
        Async wrapper for encode.

        Args:
            texts: List of text strings to encode

        Returns:
            List of embedding vectors
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.encode, texts)


# Global singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get the global embedding service singleton.

    Returns:
        The global EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def init_embedding_service() -> EmbeddingService:
    """
    Initialize and return the global embedding service.

    Call this during application startup.

    Returns:
        The initialized EmbeddingService
    """
    service = get_embedding_service()
    await service.initialize()
    return service
