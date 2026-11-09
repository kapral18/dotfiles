#!/usr/bin/env python3
"""Offline protection for vector search ranking and candidate limits."""

from __future__ import annotations

import math
import re
import sqlite3
import struct
import unittest

import vec_runner


class VecConnection(sqlite3.Connection):
    """Model vec0 MATCH/k using SQLite ORDER BY/LIMIT; scalar cosine follows sqlite-vec's API.

    Contract: https://alexgarcia.xyz/sqlite-vec/features/knn.html
    Constraint: https://github.com/asg017/sqlite-vec/blob/v0.1.9/sqlite-vec.c#L5200-L5203
    """

    def execute(self, sql, parameters=()):
        if sql == "SELECT sql FROM sqlite_master WHERE type='table' AND name='vec_index'":
            return super().execute("SELECT 'embedding float[2]'")
        if "embedding MATCH ? AND k = ?" in sql:
            if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
                raise sqlite3.OperationalError("Only LIMIT or 'k =?' can be provided, not both")
            sql = re.sub(
                r"FROM vec_index\s+WHERE embedding MATCH \? AND k = \?",
                "FROM (SELECT * FROM vec_index ORDER BY distance LIMIT ?)",
                sql,
            )
            parameters = parameters[1:]
        return super().execute(sql, parameters)


class TestFilteredVectorSearch(unittest.TestCase):
    def test_filters_before_the_nearest_neighbor_limit(self):
        with sqlite3.connect(":memory:", factory=VecConnection) as db:
            db.execute("CREATE TABLE capsules(id, scope, kind, domain_tags, workspace_path, embedding, embedding_dim)")
            db.execute("CREATE TABLE vec_index(id, embedding, distance)")

            def cosine_distance(left, right):
                a, b = struct.unpack("ff", left), struct.unpack("ff", right)
                return 1 - sum(x * y for x, y in zip(a, b)) / (math.hypot(*a) * math.hypot(*b))

            db.create_function("vec_distance_cosine", 2, cosine_distance)
            for index in range(50):
                db.execute(
                    "INSERT INTO capsules VALUES (?, 'workspace', 'fact', 'foreign', '/ws/other', ?, 2)",
                    (f"foreign-{index}", struct.pack("ff", 1, 0)),
                )
            db.execute(
                "INSERT INTO capsules VALUES ('local', 'project', 'gotcha', 'build', '/ws/here', ?, 2)",
                (struct.pack("ff", 0.6, 0.8),),
            )
            db.execute(
                "INSERT INTO vec_index SELECT id, embedding, CASE id WHEN 'local' THEN 0.4 ELSE 0 END FROM capsules"
            )
            for filters in (
                {"scopes": ["project"]},
                {"workspace": "/ws/here"},
                {"kinds": ["gotcha"]},
                {"domains": ["build"]},
            ):
                with self.subTest(filters=filters):
                    actual = vec_runner._knn(db, {"query_vector": [1.0, 0.0], "k": 20, "limit": 1, "filters": filters})
                    self.assertEqual([hit["id"] for hit in actual["hits"]], ["local"])
                    self.assertAlmostEqual(actual["hits"][0]["cosine"], 0.6, places=6)


class TestMixedDimensionSearch(unittest.TestCase):
    def test_query_dimension_selects_capsules_mid_reembed(self):
        with sqlite3.connect(":memory:", factory=VecConnection) as db:
            db.execute("CREATE TABLE capsules(id, scope, kind, domain_tags, workspace_path, embedding, embedding_dim)")
            db.create_function("vec_distance_cosine", 2, lambda left, right: 0.0)
            db.execute(
                "INSERT INTO capsules VALUES ('old', 'project', 'fact', '', NULL, ?, 3)", (struct.pack("fff", 1, 0, 0),)
            )
            db.execute(
                "INSERT INTO capsules VALUES ('new', 'project', 'fact', '', NULL, ?, 2)", (struct.pack("ff", 1, 0),)
            )
            actual = vec_runner._knn(db, {"query_vector": [1.0, 0.0], "limit": 5, "filters": {"scopes": ["project"]}})
            self.assertEqual([hit["id"] for hit in actual["hits"]], ["new"])


class TestUnfilteredVectorSearch(unittest.TestCase):
    def test_returns_nearest_capsules_with_requested_result_limit(self):
        with sqlite3.connect(":memory:", factory=VecConnection) as db:
            db.execute("CREATE TABLE capsules(id, embedding, embedding_dim)")
            db.execute("CREATE TABLE vec_index(id, embedding, distance)")
            for capsule_id, vector, distance in (
                ("far", (0.0, 1.0), 1.0),
                ("near", (1.0, 0.0), 0.0),
                ("middle", (0.6, 0.8), 0.4),
            ):
                embedding = struct.pack("ff", *vector)
                db.execute("INSERT INTO capsules VALUES (?, ?, 2)", (capsule_id, embedding))
                db.execute("INSERT INTO vec_index VALUES (?, ?, ?)", (capsule_id, embedding, distance))

            for k, limit, expected_ids in (
                (3, 2, ["near", "middle"]),
                (1, 3, ["near", "middle", "far"]),
                (2, 0, []),
                (2, -1, ["near", "middle"]),
            ):
                with self.subTest(k=k, limit=limit):
                    actual = vec_runner._knn(db, {"query_vector": [1.0, 0.0], "k": k, "limit": limit})
                    self.assertEqual([hit["id"] for hit in actual["hits"]], expected_ids)
                    if expected_ids:
                        self.assertEqual(actual["hits"][0]["cosine"], 1.0)
                    if "middle" in expected_ids:
                        self.assertAlmostEqual(actual["hits"][1]["cosine"], 0.6, places=6)


if __name__ == "__main__":
    unittest.main()
