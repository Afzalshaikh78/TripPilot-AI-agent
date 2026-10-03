import os

import psycopg
from psycopg.rows import dict_row


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is missing.")
    return url if "sslmode=" in url else f"{url}{'&' if '?' in url else '?'}sslmode=require"


def setup_metrics() -> None:
    with psycopg.connect(_database_url(), autocommit=True, row_factory=dict_row) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS request_metrics (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                outcome TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                llm_calls INTEGER NOT NULL DEFAULT 0
            )
        """)


def record_metric(outcome: str, duration_ms: int, llm_calls: int = 0) -> None:
    with psycopg.connect(_database_url(), autocommit=True) as connection:
        connection.execute(
            "INSERT INTO request_metrics (outcome, duration_ms, llm_calls) VALUES (%s, %s, %s)",
            (outcome, duration_ms, llm_calls),
        )


def get_metrics() -> dict:
    with psycopg.connect(_database_url(), autocommit=True, row_factory=dict_row) as connection:
        row = connection.execute("""
            SELECT
                COUNT(*) AS total_requests,
                COUNT(*) FILTER (WHERE outcome = 'ready') AS completed_plans,
                COUNT(*) FILTER (WHERE outcome = 'needs_clarification') AS clarification_pauses,
                COUNT(*) FILTER (WHERE outcome = 'error') AS failed_requests,
                COALESCE(ROUND(AVG(duration_ms)), 0) AS average_latency_ms,
                COALESCE(ROUND(AVG(llm_calls), 2), 0) AS average_llm_calls
            FROM request_metrics
        """).fetchone()

    return dict(row)
