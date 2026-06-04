import os
import re
import json
import math
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("JARVIS.AgentRouter")

# Centroid vocabulary mappings representing core agent competencies
AGENT_CENTROIDS = {
    "system": [
        "system", "status", "shutdown", "telemetry", "cpu", "ram", "memory", "battery", 
        "processes", "tasks", "brightness", "volume", "wifi", "mute", "reboot", "diagnostic", 
        "gauges", "health", "hardware", "power", "turnoff", "close"
    ],
    "file": [
        "file", "directory", "folder", "read", "write", "create", "delete", "move", "copy", 
        "search", "list", "glob", "text", "disk", "scans", "save", "path", "txt", "modify"
    ],
    "web": [
        "web", "internet", "google", "search", "website", "url", "open", "browser", "dossier", 
        "country", "news", "geoint", "perplexity", "scrape", "online", "link", "network", "weather"
    ],
    "code": [
        "code", "program", "python", "script", "neural", "network", "algorithm", "compile", 
        "run", "neural-network", "embedding", "vector", "train", "test", "math", "calculator", 
        "ai", "learn", "deep", "regression", "model"
    ]
}

class TaskVectorRouter:
    """
    Pure Python TF-IDF Task Vectorizer and Cosine Similarity Multi-Agent Router.
    Analyzes user queries, vectorizes them, computes agent match similarity metrics,
    persists history logs, and integrates visual metrics directly into the HUD.
    """
    def __init__(self):
        # Create global vocabulary
        self.vocabulary = set()
        for doc in AGENT_CENTROIDS.values():
            self.vocabulary.update(doc)
        self.vocab_list = list(self.vocabulary)
        
        # Build IDF dictionary
        self.idf = {}
        total_docs = len(AGENT_CENTROIDS)
        for term in self.vocabulary:
            # Count documents containing term
            doc_count = sum(1 for doc in AGENT_CENTROIDS.values() if term in doc)
            # Standard smooth IDF formula
            self.idf[term] = math.log((1 + total_docs) / (1 + doc_count)) + 1
            
        # Build vectorized Agent Centroids
        self.agent_vectors = {}
        for name, doc in AGENT_CENTROIDS.items():
            self.agent_vectors[name] = self._vectorize(doc)
            
        # Persistence path for user tasks database
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_tasks_vectors.json")
        
    def _tokenize(self, text: str) -> List[str]:
        """Convert string to normalized alphanumeric lowercase tokens."""
        text_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', text.lower())
        return [w.strip() for w in text_clean.split() if w.strip()]
        
    def _vectorize(self, tokens: List[str]) -> Dict[str, float]:
        """Compute TF-IDF weight vector for a list of tokens."""
        tf = {}
        for token in tokens:
            if token in self.vocabulary:
                tf[token] = tf.get(token, 0) + 1
                
        # Apply TF-IDF weights
        vector = {}
        for term, freq in tf.items():
            vector[term] = freq * self.idf[term]
        return vector

    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity score between two TF-IDF vectors."""
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum(vec1[x] * vec2[x] for x in intersection)
        
        sum1 = sum(val**2 for val in vec1.values())
        sum2 = sum(val**2 for val in vec2.values())
        
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        if not denominator:
            return 0.0
        return float(numerator / denominator)

    def route_task(self, query: str) -> Tuple[str, Dict[str, float]]:
        """
        Embeds user query in vector space, calculates cosine scores, logs details, and routes.
        Returns matched agent key and list of all scores.
        """
        query_tokens = self._tokenize(query)
        # If no vocabulary matches, default to system
        if not any(token in self.vocabulary for token in query_tokens):
            scores = {name: 0.0 for name in AGENT_CENTROIDS.keys()}
            scores["system"] = 0.5 # Default seed
            self._log_task(query, "system", scores)
            return "system", scores
            
        query_vector = self._vectorize(query_tokens)
        
        # Calculate similarity with all Agent Centroids
        scores = {}
        for name, agent_vector in self.agent_vectors.items():
            scores[name] = round(self._cosine_similarity(query_vector, agent_vector), 4)
            
        # Select best matching agent
        matched_agent = max(scores, key=scores.get)
        
        # Log classified task to file database
        self._log_task(query, matched_agent, scores)
        
        return matched_agent, scores

    def _log_task(self, query: str, agent: str, scores: Dict[str, float]):
        """Persist task classification record to local user_tasks_vectors.json database."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "allocated_agent": agent,
            "cosine_scores": scores
        }
        
        try:
            data = []
            if os.path.exists(self.db_path):
                with open(self.db_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        
            data.append(record)
            
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Task vector logged successfully: '{query[:30]}' -> {agent}")
        except Exception as e:
            logger.error(f"Failed to log task vector to database: {e}")

    def get_user_activity_summary(self) -> Dict[str, Any]:
        """Aggregate classified records from the json database to generate user analytics."""
        if not os.path.exists(self.db_path):
            return {"total_tasks": 0, "categories": {}}
            
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            counts = {}
            for item in data:
                cat = item.get("allocated_agent")
                counts[cat] = counts.get(cat, 0) + 1
                
            return {
                "total_tasks": len(data),
                "categories": counts,
                "last_active": data[-1]["timestamp"] if data else None
            }
        except Exception as e:
            logger.error(f"Error compiling activity summary: {e}")
            return {"total_tasks": 0, "categories": {}}
