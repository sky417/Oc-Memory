"""
Memory Store for OC-Memory
ChromaDB-based vector storage for semantic search

Provides persistent vector storage with semantic search
capabilities for the Hot memory tier.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Memory Store
# =============================================================================

class MemoryStore:
    """
    ChromaDB-backed vector store for observations.
    Provides semantic search over stored observations.
    """

    def __init__(
        self,
        persist_dir: str = ".chromadb",
        collection_name: str = "observations",
    ):
        """
        Args:
            persist_dir: Directory for ChromaDB persistence
            collection_name: Name of the ChromaDB collection
        """
        self.persist_dir = Path(persist_dir).expanduser().resolve()
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _ensure_initialized(self):
        """Lazy-initialize ChromaDB client and collection"""
        if self._collection is not None:
            return

        try:
            import chromadb
            self._client = chromadb.PersistentClient(
                path=str(self.persist_dir)
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"ChromaDB initialized: {self.persist_dir} "
                f"(collection: {self.collection_name})"
            )
        except ImportError:
            logger.error("chromadb not installed. Run: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    def add_observation(
        self,
        obs_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add an observation to the store.

        Args:
            obs_id: Unique observation ID
            content: Observation text content
            metadata: Optional metadata dict
        """
        self._ensure_initialized()

        meta = metadata or {}
        # ChromaDB metadata must be str/int/float/bool
        clean_meta = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
            elif isinstance(v, datetime):
                clean_meta[k] = v.isoformat()
            else:
                clean_meta[k] = str(v)

        self._collection.upsert(
            ids=[obs_id],
            documents=[content],
            metadatas=[clean_meta],
        )
        logger.debug(f"Added observation: {obs_id}")

    def add_observations(self, observations: list) -> int:
        """
        Add multiple observations from Observation objects.

        Args:
            observations: List of Observation objects

        Returns:
            Number of observations added
        """
        self._ensure_initialized()

        if not observations:
            return 0

        ids = [obs.id for obs in observations]
        documents = [obs.content for obs in observations]
        metadatas = [
            {
                'priority': obs.priority,
                'category': obs.category,
                'timestamp': obs.timestamp.isoformat(),
            }
            for obs in observations
        ]

        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info(f"Added {len(observations)} observations to store")
        return len(observations)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over stored observations.

        Args:
            query: Search query text
            n_results: Number of results to return
            where: Optional metadata filter

        Returns:
            List of result dicts with 'id', 'content', 'metadata', 'distance'
        """
        self._ensure_initialized()

        kwargs = {
            "query_texts": [query],
            "n_results": min(n_results, self.count()),
        }
        if where:
            kwargs["where"] = where

        if kwargs["n_results"] == 0:
            return []

        results = self._collection.query(**kwargs)

        items = []
        if results and results.get('ids'):
            for i in range(len(results['ids'][0])):
                items.append({
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i] if results.get('documents') else '',
                    'metadata': results['metadatas'][0][i] if results.get('metadatas') else {},
                    'distance': results['distances'][0][i] if results.get('distances') else 0.0,
                })

        return items

    def get(self, obs_id: str) -> Optional[Dict[str, Any]]:
        """Get a single observation by ID"""
        self._ensure_initialized()

        result = self._collection.get(ids=[obs_id])
        if result and result['ids']:
            return {
                'id': result['ids'][0],
                'content': result['documents'][0] if result.get('documents') else '',
                'metadata': result['metadatas'][0] if result.get('metadatas') else {},
            }
        return None

    def delete(self, obs_id: str) -> None:
        """Delete an observation by ID"""
        self._ensure_initialized()
        self._collection.delete(ids=[obs_id])
        logger.debug(f"Deleted observation: {obs_id}")

    def count(self) -> int:
        """Get total number of stored observations"""
        self._ensure_initialized()
        return self._collection.count()

    def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List all observations with pagination"""
        self._ensure_initialized()

        result = self._collection.get(
            limit=limit,
            offset=offset,
        )

        items = []
        if result and result['ids']:
            for i in range(len(result['ids'])):
                items.append({
                    'id': result['ids'][i],
                    'content': result['documents'][i] if result.get('documents') else '',
                    'metadata': result['metadatas'][i] if result.get('metadatas') else {},
                })
        return items

    def clear(self) -> None:
        """Delete all observations"""
        self._ensure_initialized()
        # Re-create collection
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Memory store cleared")


def create_memory_store(config: Dict[str, Any]) -> MemoryStore:
    """Create a MemoryStore from config dictionary"""
    memory_config = config.get('memory', {})
    persist_dir = memory_config.get('chromadb_dir', '.chromadb')

    return MemoryStore(persist_dir=persist_dir)
