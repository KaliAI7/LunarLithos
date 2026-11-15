import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> str:
    value = value or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class ObservationStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    site TEXT,
                    latitude REAL,
                    longitude REAL,
                    confidence_threshold REAL NOT NULL,
                    total_detections INTEGER NOT NULL,
                    lunar_pct REAL NOT NULL,
                    mars_pct REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observation_classes (
                    observation_id INTEGER NOT NULL REFERENCES observations(id)
                        ON DELETE CASCADE,
                    class_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    confidence_sum REAL NOT NULL,
                    PRIMARY KEY (observation_id, class_name)
                );
                CREATE TABLE IF NOT EXISTS reference_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_name TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    site TEXT,
                    latitude REAL,
                    longitude REAL,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS reference_classes (
                    reference_id INTEGER NOT NULL REFERENCES reference_records(id)
                        ON DELETE CASCADE,
                    class_name TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (reference_id, class_name)
                );
                CREATE INDEX IF NOT EXISTS observations_site_date
                    ON observations(site, created_at);
                CREATE INDEX IF NOT EXISTS reference_site_date
                    ON reference_records(site, observed_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def add_observation(
        self,
        inference: Any,
        *,
        source: str,
        site: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = _as_utc(created_at)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO observations (
                    created_at, source, site, latitude, longitude,
                    confidence_threshold, total_detections, lunar_pct, mars_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    source,
                    site,
                    latitude,
                    longitude,
                    inference.confidence_threshold,
                    inference.total_detections,
                    inference.lunar_pct,
                    inference.mars_pct,
                ),
            )
            observation_id = cursor.lastrowid
            connection.executemany(
                """
                INSERT INTO observation_classes (
                    observation_id, class_name, category, count, confidence_sum
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        observation_id,
                        row["class_name"],
                        row["category"],
                        row["count"],
                        row["confidence_sum"],
                    )
                    for row in inference.class_counts
                ],
            )
        return {
            "observation_id": observation_id,
            "created_at": timestamp,
            "site": site,
            "latitude": latitude,
            "longitude": longitude,
            "confidence_threshold": inference.confidence_threshold,
            "total_detections": inference.total_detections,
            "lunar_pct": inference.lunar_pct,
            "mars_pct": inference.mars_pct,
            "class_counts": inference.class_counts,
            "detections": inference.detections,
        }

    def add_reference(
        self,
        *,
        dataset_name: str,
        counts: dict[str, int],
        site: str | None,
        latitude: float | None,
        longitude: float | None,
        observed_at: datetime | None,
        notes: str | None,
    ) -> dict[str, Any]:
        timestamp = _as_utc(observed_at)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reference_records (
                    dataset_name, observed_at, site, latitude, longitude, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (dataset_name, timestamp, site, latitude, longitude, notes),
            )
            reference_id = cursor.lastrowid
            connection.executemany(
                """
                INSERT INTO reference_classes (reference_id, class_name, count)
                VALUES (?, ?, ?)
                """,
                [
                    (reference_id, class_name, count)
                    for class_name, count in counts.items()
                ],
            )
        return {
            "reference_id": reference_id,
            "dataset_name": dataset_name,
            "site": site,
            "observed_at": timestamp,
            "counts": counts,
        }

    def list_observations(
        self,
        *,
        site: str | None,
        class_name: str | None,
        since: str | None,
        until: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        conditions = []
        parameters: list[Any] = []
        if site is not None:
            conditions.append("o.site = ?")
            parameters.append(site)
        if since is not None:
            conditions.append("o.created_at >= ?")
            parameters.append(since)
        if until is not None:
            conditions.append("o.created_at <= ?")
            parameters.append(until)
        if class_name is not None:
            conditions.append(
                "EXISTS (SELECT 1 FROM observation_classes c "
                "WHERE c.observation_id = o.id AND c.class_name = ?)"
            )
            parameters.append(class_name)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT o.* FROM observations o {where}
                ORDER BY o.created_at DESC LIMIT ?
                """,
                parameters,
            ).fetchall()
            observations = []
            for row in rows:
                class_rows = connection.execute(
                    """
                    SELECT class_name, category, count, confidence_sum
                    FROM observation_classes WHERE observation_id = ?
                    ORDER BY class_name
                    """,
                    (row["id"],),
                ).fetchall()
                observations.append(
                    {
                        "observation_id": row["id"],
                        "created_at": row["created_at"],
                        "source": row["source"],
                        "site": row["site"],
                        "latitude": row["latitude"],
                        "longitude": row["longitude"],
                        "confidence_threshold": row["confidence_threshold"],
                        "total_detections": row["total_detections"],
                        "lunar_pct": row["lunar_pct"],
                        "mars_pct": row["mars_pct"],
                        "class_counts": [dict(class_row) for class_row in class_rows],
                    }
                )
            return observations

    def summary(
        self,
        *,
        site: str | None,
        since: str | None,
        until: str | None,
    ) -> dict[str, Any]:
        conditions = []
        parameters: list[Any] = []
        if site is not None:
            conditions.append("o.site = ?")
            parameters.append(site)
        if since is not None:
            conditions.append("o.created_at >= ?")
            parameters.append(since)
        if until is not None:
            conditions.append("o.created_at <= ?")
            parameters.append(until)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as connection:
            observation_count = connection.execute(
                f"SELECT COUNT(*) FROM observations o {where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT c.class_name, c.category, SUM(c.count) AS count,
                    SUM(c.confidence_sum) AS confidence_sum
                FROM observation_classes c
                JOIN observations o ON o.id = c.observation_id
                {where}
                GROUP BY c.class_name, c.category
                ORDER BY c.class_name
                """,
                parameters,
            ).fetchall()
        return {
            "site": site,
            "observation_count": observation_count,
            "class_counts": [dict(row) for row in rows],
        }

    def compare(
        self,
        *,
        site: str | None,
        dataset_name: str | None,
        since: str | None,
        until: str | None,
    ) -> dict[str, Any]:
        observation_conditions = []
        observation_parameters: list[Any] = []
        reference_conditions = []
        reference_parameters: list[Any] = []
        if site is not None:
            observation_conditions.append("o.site = ?")
            observation_parameters.append(site)
            reference_conditions.append("r.site = ?")
            reference_parameters.append(site)
        if since is not None:
            observation_conditions.append("o.created_at >= ?")
            observation_parameters.append(since)
            reference_conditions.append("r.observed_at >= ?")
            reference_parameters.append(since)
        if until is not None:
            observation_conditions.append("o.created_at <= ?")
            observation_parameters.append(until)
            reference_conditions.append("r.observed_at <= ?")
            reference_parameters.append(until)
        if dataset_name is not None:
            reference_conditions.append("r.dataset_name = ?")
            reference_parameters.append(dataset_name)
        observation_where = (
            f"WHERE {' AND '.join(observation_conditions)}"
            if observation_conditions
            else ""
        )
        reference_where = (
            f"WHERE {' AND '.join(reference_conditions)}"
            if reference_conditions
            else ""
        )
        with self._connect() as connection:
            model_rows = connection.execute(
                f"""
                SELECT c.class_name, SUM(c.count) AS count
                FROM observation_classes c
                JOIN observations o ON o.id = c.observation_id
                {observation_where}
                GROUP BY c.class_name
                """,
                observation_parameters,
            ).fetchall()
            reference_rows = connection.execute(
                f"""
                SELECT c.class_name, SUM(c.count) AS count
                FROM reference_classes c
                JOIN reference_records r ON r.id = c.reference_id
                {reference_where}
                GROUP BY c.class_name
                """,
                reference_parameters,
            ).fetchall()
            observation_count = connection.execute(
                f"SELECT COUNT(*) FROM observations o {observation_where}",
                observation_parameters,
            ).fetchone()[0]
            reference_count = connection.execute(
                f"SELECT COUNT(*) FROM reference_records r {reference_where}",
                reference_parameters,
            ).fetchone()[0]
        model_counts = {row["class_name"]: row["count"] for row in model_rows}
        reference_counts = {
            row["class_name"]: row["count"] for row in reference_rows
        }
        classes = sorted(model_counts.keys() | reference_counts.keys())
        return {
            "site": site,
            "dataset_name": dataset_name,
            "model_observation_count": observation_count,
            "reference_record_count": reference_count,
            "class_comparison": [
                {
                    "class_name": class_name,
                    "model_count": model_counts.get(class_name, 0),
                    "reference_count": reference_counts.get(class_name, 0),
                    "difference": model_counts.get(class_name, 0)
                    - reference_counts.get(class_name, 0),
                }
                for class_name in classes
            ],
        }
