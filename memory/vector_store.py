"""Dorothy OS v2.0 — Hybrid Cloud/Local Semantic Vector Database.

Provides high-fidelity semantic embeddings search via Gemini API (when online)
cascading into a fast, zero-dependency TF-IDF + Cosine Similarity keyword index (when offline).
"""

import os
import json
import sqlite3
import math
import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from configs import settings
from api.llm_service import is_internet_available

logger = logging.getLogger("Dorothy.Memory.Vector")

# Common English stop words to filter out during offline TF-IDF tokenization
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'arent',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'cant',
    'cannot', 'could', 'couldnt', 'did', 'didnt', 'do', 'does', 'doesnt', 'doing', 'dont', 'down', 'during',
    'each', 'few', 'for', 'from', 'further', 'had', 'hadnt', 'has', 'hasnt', 'have', 'havent', 'having',
    'he', 'hed', 'hell', 'hes', 'her', 'here', 'heres', 'hers', 'herself', 'him', 'himself', 'his', 'how',
    'hows', 'i', 'id', 'ill', 'im', 'ive', 'if', 'in', 'into', 'is', 'isnt', 'it', 'its', 'itself', 'lets',
    'me', 'more', 'most', 'mustnt', 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only',
    'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', 'shant', 'she', 'shed',
    'shell', 'shes', 'should', 'shouldnt', 'so', 'some', 'such', 'than', 'that', 'thats', 'the', 'their',
    'theirs', 'them', 'themselves', 'then', 'there', 'theres', 'these', 'they', 'theyd', 'theyll', 'theyre',
    'theyve', 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasnt', 'we',
    'wed', 'well', 'were', 'weve', 'werent', 'what', 'whats', 'when', 'whens', 'where', 'wheres', 'which',
    'while', 'who', 'whos', 'whom', 'why', 'whys', 'with', 'wont', 'would', 'wouldnt', 'you', 'youd', 'youll',
    'youre', 'youve', 'your', 'yours', 'yourself', 'yourselves'
}


class SemanticMemoryStore:
    """Hybrid cloud/local vector database client for long-term memory."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the semantic store and establish SQLite table structures."""
        self.db_path = db_path or str(settings.DB_PATH)
        self.api_key = settings.GEMINI_API_KEY
        self._init_db()
        logger.info("SemanticMemoryStore initialized.")

    def _init_db(self) -> None:
        """Create the semantic memory table inside dorothy.db if missing."""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    text        TEXT    NOT NULL,
                    metadata    TEXT    NOT NULL,  -- JSON formatted dict
                    vector      TEXT,              -- JSON formatted float list (if online)
                    timestamp   TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_semantic_ts 
                ON semantic_memory (timestamp DESC)
            """)
            conn.commit()
        finally:
            conn.close()

    # ─── Embedding Generation (Gemini Cloud API) ──────────────────────────────

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Fetch high-fidelity 768-dimension text embedding from Gemini API."""
        if not self.api_key or not is_internet_available():
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={self.api_key}"
        payload = {
            "model": "models/text-embedding-004",
            "content": {
                "parts": [{"text": text}]
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    embedding_values = data.get("embedding", {}).get("values")
                    if isinstance(embedding_values, list):
                        return embedding_values
                logger.warning(f"Embedding request returned status: {res.status_code}")
        except Exception as e:
            logger.warning(f"Failed to generate online embeddings: {e}")
        return None

    # ─── Vector Insertion API ──────────────────────────────────────────────────

    async def add_document(self, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Embed and persist a document chunk. Falls back dynamically to local
        keyword indices if offline.
        """
        text = text.strip()
        if not text:
            return False

        embedding = await self._generate_embedding(text)
        vector_str = json.dumps(embedding) if embedding else None
        metadata_str = json.dumps(metadata)
        ts = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO semantic_memory (text, metadata, vector, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (text, metadata_str, vector_str, ts)
            )
            conn.commit()
            logger.info(f"Successfully cached document chunk (online={bool(embedding)})")
            return True
        except Exception as e:
            logger.error(f"Failed to save document to semantic store: {e}")
            return False
        finally:
            conn.close()

    # ─── Search API ────────────────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search documents. Automatically performs semantic cosine similarity (online)
        or optimized TF-IDF cosine matching (offline fallback).
        """
        query = query.strip()
        if not query:
            return []

        # Try online semantic embeddings search first
        query_embedding = await self._generate_embedding(query)
        if query_embedding:
            return await self._search_semantic(query_embedding, limit)

        # Fallback: Zero-dependency local TF-IDF Cosine Search
        logger.info("Executing zero-dependency offline TF-IDF cosine matching.")
        return await self._search_offline_tfidf(query, limit)

    # ─── Online Semantic Cosine Matcher ────────────────────────────────────────

    async def _search_semantic(self, query_vec: List[float], limit: int) -> List[Dict[str, Any]]:
        """Performs cosine similarity search against stored high-fidelity vectors."""
        conn = sqlite3.connect(self.db_path)
        results = []
        try:
            cur = conn.cursor()
            cur.execute("SELECT text, metadata, vector, timestamp FROM semantic_memory WHERE vector IS NOT NULL")
            rows = cur.fetchall()

            for text, meta_json, vec_json, ts in rows:
                try:
                    doc_vec = json.loads(vec_json)
                    score = cosine_similarity(query_vec, doc_vec)
                    results.append({
                        "text": text,
                        "metadata": json.loads(meta_json),
                        "score": score,
                        "timestamp": ts
                    })
                except Exception:
                    continue

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]
        finally:
            conn.close()

    # ─── Offline Local TF-IDF Matcher ──────────────────────────────────────────

    async def _search_offline_tfidf(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Zero-dependency local search using cosine similarity over tokenized TF-IDF vectors."""
        conn = sqlite3.connect(self.db_path)
        results = []
        try:
            cur = conn.cursor()
            cur.execute("SELECT text, metadata, timestamp FROM semantic_memory")
            rows = cur.fetchall()
            
            if not rows:
                return []

            # 1. Tokenize query & stored documents
            query_tokens = tokenize(query)
            if not query_tokens:
                return []

            documents: List[Tuple[str, Dict[str, Any], List[str], str]] = []
            doc_frequencies = {}  # Document Frequency (DF) registry for IDF
            
            for text, meta_json, ts in rows:
                tokens = tokenize(text)
                documents.append((text, json.loads(meta_json), tokens, ts))
                
                # Update document frequency for each unique word
                unique_tokens = set(tokens)
                for token in unique_tokens:
                    doc_frequencies[token] = doc_frequencies.get(token, 0) + 1

            num_docs = len(documents)
            
            # 2. Compute Inverse Document Frequency (IDF)
            idf = {}
            for token, freq in doc_frequencies.items():
                # Standard smooth IDF formula
                idf[token] = math.log(1.0 + (num_docs / freq))

            # 3. Vectorize documents & query
            query_vec = get_tfidf_vector(query_tokens, idf)
            
            for text, metadata, tokens, ts in documents:
                doc_vec = get_tfidf_vector(tokens, idf)
                score = tfidf_cosine_similarity(query_vec, doc_vec)
                
                if score > 0.05:  # Relevance threshold
                    results.append({
                        "text": text,
                        "metadata": metadata,
                        "score": round(score, 4),
                        "timestamp": ts
                    })
                    
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]
        finally:
            conn.close()


# ─── Vector Algebra Helpers ──────────────────────────────────────────────────

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute mathematical cosine similarity between two float arrays."""
    dot_product = sum(x * y for x, y in zip(v1, v2))
    magnitude_v1 = math.sqrt(sum(x * x for x in v1))
    magnitude_v2 = math.sqrt(sum(y * y for y in v2))
    if magnitude_v1 == 0 or magnitude_v2 == 0:
        return 0.0
    return dot_product / (magnitude_v1 * magnitude_v2)


def tokenize(text: str) -> List[str]:
    """Tokenize and filter text into lowercase alphanumeric tokens, skipping stop words."""
    import re
    # Lowercase & split on non-alphanumeric boundaries
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def get_tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
    """Compute term frequency weighted by IDF to construct a sparse vector."""
    tf = {}
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1
        
    vector = {}
    for token, count in tf.items():
        if token in idf:
            vector[token] = count * idf[token]
    return vector


def tfidf_cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse term-frequency-IDF dictionaries."""
    # Find matching keys (dot product)
    intersection = set(v1.keys()) & set(v2.keys())
    dot_product = sum(v1[x] * v2[x] for x in intersection)
    
    # Magnitudes
    mag_v1 = math.sqrt(sum(x * x for x in v1.values()))
    mag_v2 = math.sqrt(sum(x * x for x in v2.values()))
    
    if mag_v1 == 0 or mag_v2 == 0:
        return 0.0
    return dot_product / (mag_v1 * mag_v2)
