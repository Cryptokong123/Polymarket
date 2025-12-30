"""
Vector Store - ChromaDB integration for RAG
Stores and retrieves news/context for market analysis
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class VectorStore:
    """
    ChromaDB-based vector store for news and market context.
    Used for RAG (Retrieval Augmented Generation) in market analysis.
    """

    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        collection_name: str = "polymarket_context",
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._initialized = False

    def _initialize(self):
        """Initialize ChromaDB client and collection"""
        if self._initialized:
            return

        try:
            import chromadb
            from chromadb.config import Settings

            # Create persistent client
            self._client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_directory,
                anonymized_telemetry=False,
            ))

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Polymarket news and context"}
            )

            self._initialized = True
            logger.info(f"VectorStore initialized with {self._collection.count()} documents")

        except ImportError:
            logger.error("chromadb not installed. Run: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize VectorStore: {e}")
            raise

    def _generate_id(self, content: str) -> str:
        """Generate unique ID for content"""
        return hashlib.md5(content.encode()).hexdigest()

    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of document texts
            metadatas: Optional list of metadata dicts
            ids: Optional list of IDs (generated if not provided)

        Returns:
            List of document IDs
        """
        self._initialize()

        if not documents:
            return []

        # Generate IDs if not provided
        if ids is None:
            ids = [self._generate_id(doc) for doc in documents]

        # Add timestamps to metadata
        if metadatas is None:
            metadatas = [{} for _ in documents]

        for meta in metadatas:
            if "added_at" not in meta:
                meta["added_at"] = datetime.utcnow().isoformat()

        try:
            self._collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info(f"Added {len(documents)} documents to vector store")
            return ids

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return []

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the vector store for relevant documents.

        Args:
            query_text: Query text
            n_results: Number of results to return
            where: Optional filter conditions

        Returns:
            List of matching documents with metadata
        """
        self._initialize()

        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where,
            )

            # Format results
            documents = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                documents.append({
                    "content": doc,
                    "metadata": results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {},
                    "id": results.get("ids", [[]])[0][i] if results.get("ids") else None,
                    "distance": results.get("distances", [[]])[0][i] if results.get("distances") else None,
                })

            return documents

        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []

    def add_news_article(
        self,
        title: str,
        content: str,
        source: str,
        url: Optional[str] = None,
        published_at: Optional[str] = None,
    ) -> Optional[str]:
        """
        Add a news article to the vector store.

        Args:
            title: Article title
            content: Article content
            source: Source name
            url: Article URL
            published_at: Publication date

        Returns:
            Document ID if successful
        """
        document = f"{title}\n\n{content}"

        metadata = {
            "title": title,
            "source": source,
            "type": "news",
        }
        if url:
            metadata["url"] = url
        if published_at:
            metadata["published_at"] = published_at

        ids = self.add_documents([document], [metadata])
        return ids[0] if ids else None

    def search_by_market(
        self,
        market_question: str,
        n_results: int = 5,
        days_back: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for context relevant to a market question.

        Args:
            market_question: The market question to find context for
            n_results: Number of results
            days_back: Only return docs from last N days

        Returns:
            List of relevant documents
        """
        where = None
        if days_back:
            # Filter by date (if metadata available)
            # Note: This is a simplified filter
            from datetime import timedelta
            cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
            where = {"added_at": {"$gte": cutoff}}

        return self.query(market_question, n_results=n_results, where=where)

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        self._initialize()

        return {
            "collection": self.collection_name,
            "document_count": self._collection.count(),
            "persist_directory": self.persist_directory,
        }

    def clear(self):
        """Clear all documents from the collection"""
        self._initialize()

        # Delete and recreate collection
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={"description": "Polymarket news and context"}
        )
        logger.info("Vector store cleared")
