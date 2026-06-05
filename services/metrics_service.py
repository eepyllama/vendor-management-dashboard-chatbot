"""
services/metrics_service.py
───────────────────────────
SQLite service to record and aggregate LLM token usage and costs.
"""

import os
import sqlite3
import logging
from datetime import datetime, timezone
import threading

logger = logging.getLogger(__name__)

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "metrics.db")

# Standard model pricing per token (USD)
# Prices are:
# llama-3.1-8b-instant: Prompt $0.05/1M ($0.00000005), Completion $0.08/1M ($0.00000008)
# llama-3.1-70b-versatile: Prompt $0.59/1M ($0.00000059), Completion $0.79/1M ($0.00000079)
# mixtral-8x7b-32768: Prompt $0.27/1M ($0.00000027), Completion $0.27/1M ($0.00000027)
MODEL_PRICING = {
    "llama-3.1-8b-instant": {
        "prompt": 0.05 / 1_000_000,
        "completion": 0.08 / 1_000_000,
    },
    "llama-3.1-70b-versatile": {
        "prompt": 0.59 / 1_000_000,
        "completion": 0.79 / 1_000_000,
    },
    "mixtral-8x7b-32768": {
        "prompt": 0.27 / 1_000_000,
        "completion": 0.27 / 1_000_000,
    }
}

# Fallback pricing (per token)
FALLBACK_PROMPT_PRICE = 0.15 / 1_000_000
FALLBACK_COMPLETION_PRICE = 0.15 / 1_000_000

class MetricsService:
    """
    Thread-safe SQLite storage for tracking token usage metrics.
    """
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self._ensure_db_initialized()

    def _ensure_db_initialized(self) -> None:
        """Create data directory and initialize SQLite schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS token_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        prompt_tokens INTEGER NOT NULL,
                        completion_tokens INTEGER NOT NULL,
                        total_tokens INTEGER NOT NULL,
                        model_name TEXT NOT NULL,
                        endpoint_source TEXT NOT NULL
                    )
                """)
                conn.commit()
            except Exception as e:
                logger.error("Failed to initialize SQLite metrics db: %s", e)
                raise
            finally:
                conn.close()

    def log_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        model_name: str,
        endpoint_source: str,
    ) -> None:
        """Record a single LLM request's token usage."""
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO token_usage (
                        timestamp, prompt_tokens, completion_tokens, total_tokens, model_name, endpoint_source
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (timestamp, prompt_tokens, completion_tokens, total_tokens, model_name, endpoint_source)
                )
                conn.commit()
                logger.info(
                    "Logged token usage: model=%s, prompt=%d, completion=%d, source=%s",
                    model_name, prompt_tokens, completion_tokens, endpoint_source
                )
            except Exception as e:
                logger.error("Failed to log token usage to SQLite: %s", e)
            finally:
                conn.close()

    def get_aggregated_metrics(self) -> dict:
        """Return total aggregated requests, tokens, and estimated cost."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT model_name, SUM(prompt_tokens), SUM(completion_tokens), COUNT(id)
                    FROM token_usage
                    GROUP BY model_name
                    """
                )
                rows = cursor.fetchall()
                
                total_requests = 0
                total_prompt = 0
                total_completion = 0
                estimated_cost = 0.0

                for row in rows:
                    model, prompt_sum, comp_sum, count = row
                    prompt_sum = prompt_sum or 0
                    comp_sum = comp_sum or 0
                    count = count or 0
                    
                    total_requests += count
                    total_prompt += prompt_sum
                    total_completion += comp_sum
                    
                    # Calculate cost for this specific model
                    pricing = MODEL_PRICING.get(model)
                    if pricing:
                        p_price = pricing["prompt"]
                        c_price = pricing["completion"]
                    else:
                        p_price = FALLBACK_PROMPT_PRICE
                        c_price = FALLBACK_COMPLETION_PRICE
                    
                    estimated_cost += (prompt_sum * p_price) + (comp_sum * c_price)

                return {
                    "total_requests": total_requests,
                    "prompt_tokens": total_prompt,
                    "completion_tokens": total_completion,
                    "total_tokens": total_prompt + total_completion,
                    "estimated_cost": round(estimated_cost, 6)
                }
            except Exception as e:
                logger.error("Failed to fetch aggregated metrics: %s", e)
                return {
                    "total_requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost": 0.0
                }
            finally:
                conn.close()

_metrics_service_instance = None
_metrics_lock = threading.Lock()

def get_metrics_service() -> MetricsService:
    """Singleton getter for the MetricsService."""
    global _metrics_service_instance
    with _metrics_lock:
        if _metrics_service_instance is None:
            _metrics_service_instance = MetricsService()
    return _metrics_service_instance
