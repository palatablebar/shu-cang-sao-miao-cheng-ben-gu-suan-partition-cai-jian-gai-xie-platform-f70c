"""Offline regression tests for the multi-table analysis core (no DB, no network).

Run:
    cd backend && PYTHONPATH=. python3 -m unittest tests.test_multitable_analysis

Covers the four contracts the UI depends on:
    1. 表级明细之和 == 查询总量（reconciliation.balanced）
    2. 逐表裁剪判定独立（一张表失效不会掩盖另一张表的命中分区）
    3. 改写逐表进行，且任一张表无法确定等价改写时不生成建议
    4. 改写 SQL 重新跑算法 1 后，表级命中分区确实变化（不是系数估算）
"""
from __future__ import annotations

import unittest

from scripts import demo_dataset
from src.analysis.rewriter import build_rewrite
from src.analysis.sql_analyzer import ColumnProfile, TableProfile, analyze_query


def make_catalog() -> dict[str, TableProfile]:
    catalog: dict[str, TableProfile] = {}
    for spec in demo_dataset.build_tables():
        columns = [
            ColumnProfile(
                name=column["name"],
                data_type=column["data_type"],
                bytes=column["bytes"],
                is_partition_key=column["is_partition_key"],
            )
            for column in spec["columns"]
        ]
        profile = TableProfile(
            schema_name=spec["schema_name"],
            table_name=spec["table_name"],
            partition_key=spec["partition_key"],
            partition_type=spec["partition_type"],
            partitions=[(p["dt"], p["bytes"]) for p in spec["partitions"]],
            columns=columns,
            suggested_columns=spec["suggested_columns"],
            total_bytes=spec["total_bytes"],
        )
        catalog[profile.table_name] = profile
    return catalog


JOIN_SQL = (
    "SELECT d.order_id, p.pay_id, sum(d.pay_amount) AS gmv\n"
    "FROM dwd_order_detail d\n"
    "JOIN dwd_payment_flow p ON d.order_id = p.order_id\n"
    "WHERE d.dt = '2026-11-11' AND to_char(p.dt, 'YYYY-MM-DD') = '2026-11-12'"
)


class MultiTableAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = make_catalog()

    def test_single_table_behaviour_unchanged(self) -> None:
        sql = "SELECT order_id FROM dwd_order_detail WHERE dt = '2026-11-12'"
        analysis = analyze_query(sql, self.catalog)
        self.assertEqual(analysis.parse_status, "parsed")
        self.assertTrue(analysis.prunable)
        self.assertEqual(analysis.hit_partition_count, 1)
        self.assertEqual(len(analysis.tables), 1)
        self.assertTrue(analysis.reconciliation["balanced"])

    def test_table_breakdown_reconciles_with_query_total(self) -> None:
        analysis = analyze_query(JOIN_SQL, self.catalog)
        self.assertEqual(analysis.parse_status, "parsed")
        self.assertEqual(len(analysis.tables), 2)
        per_table = sum(row["scan_bytes"] for row in analysis.tables)
        self.assertEqual(per_table, analysis.scan_bytes)
        self.assertEqual(analysis.reconciliation["table_scan_sum_bytes"], analysis.scan_bytes)
        self.assertEqual(analysis.reconciliation["delta_bytes"], 0)
        self.assertTrue(analysis.reconciliation["balanced"])

    def test_pruning_is_judged_per_table(self) -> None:
        analysis = analyze_query(JOIN_SQL, self.catalog)
        detail_row = next(row for row in analysis.tables if row["table_name"] == "dwd_order_detail")
        pay_row = next(row for row in analysis.tables if row["table_name"] == "dwd_payment_flow")
        self.assertTrue(detail_row["prunable"])
        self.assertEqual(detail_row["hit_partition_count"], 1)
        self.assertFalse(pay_row["prunable"])
        self.assertEqual(pay_row["blocked_reason"], "function_wrapped")
        # 查询级标记必须反映「至少一张表失效」，而不是只看第一张表。
        self.assertFalse(analysis.prunable)
        self.assertEqual(analysis.blocked_reason, "function_wrapped")

    def test_ambiguous_partition_column_is_not_used_for_pruning(self) -> None:
        sql = (
            "SELECT count(*) FROM dwd_order_detail d JOIN dwd_payment_flow p "
            "ON d.order_id = p.order_id WHERE dt = '2026-11-11'"
        )
        analysis = analyze_query(sql, self.catalog)
        self.assertFalse(analysis.prunable)
        self.assertTrue(all(row["blocked_reason"] == "ambiguous_predicate" for row in analysis.tables))

    def test_missing_metadata_table_fails_whole_query(self) -> None:
        sql = (
            "SELECT count(*) FROM unknown_tbl u JOIN dwd_payment_flow p ON u.id = p.order_id "
            "WHERE p.dt = '2026-11-12'"
        )
        analysis = analyze_query(sql, self.catalog)
        self.assertEqual(analysis.parse_status, "missing_table")
        self.assertEqual(analysis.scan_bytes, 0)
        self.assertGreaterEqual(analysis.reconciliation["missing_table_count"], 1)
        self.assertTrue(any(row["status"] == "missing_table" for row in analysis.tables))

    def test_rewrite_is_applied_per_table_and_requalified(self) -> None:
        result = build_rewrite(JOIN_SQL, self.catalog)
        self.assertTrue(result.rewritable)
        self.assertIn("p.dt = '2026-11-12'", result.rewritten_sql)
        self.assertIn("d.dt = '2026-11-11'", result.rewritten_sql)
        pay_change = next(row for row in result.table_changes if row["table_name"] == "dwd_payment_flow")
        detail_change = next(row for row in result.table_changes if row["table_name"] == "dwd_order_detail")
        self.assertTrue(pay_change["changed"])
        self.assertEqual(pay_change["after_hit_partition_count"], 1)
        self.assertEqual(detail_change["after_hit_partition_count"], 1)
        # 改写后扫描量来自算法 1 重新求解，而不是系数。
        self.assertEqual(sum(row["after_scan_bytes"] for row in result.table_changes), result.after_scan_bytes)

    def test_rewrite_rejected_when_any_table_is_not_equivalent(self) -> None:
        # 未限定 * 同时覆盖两张表 → 无法拆成保留另一张表的等价投影 → 不生成建议。
        sql = (
            "SELECT * FROM dwd_order_detail d JOIN dwd_payment_flow p "
            "ON d.order_id = p.order_id "
            "WHERE d.dt = '2026-11-11' AND p.dt = '2026-11-12'"
        )
        result = build_rewrite(sql, self.catalog)
        self.assertFalse(result.rewritable)
        self.assertEqual(result.rewritten_sql, "")
        self.assertIn("无法确定等价改写", result.note)

    def test_or_branch_with_business_condition_is_not_rewritten(self) -> None:
        sql = "SELECT order_id FROM dwd_order_detail WHERE dt = 20261110 OR pay_amount > 5000"
        result = build_rewrite(sql, self.catalog)
        self.assertFalse(result.rewritable)
        self.assertIn("无法确定等价改写", result.note)

    def test_demo_dataset_contract(self) -> None:
        rows = demo_dataset.build_queries()
        self.assertEqual(len(rows), 60)
        blocked = 0
        for row in rows:
            analysis = analyze_query(row["sql_text"], self.catalog)
            if analysis.parse_status == "parsed" and not analysis.prunable:
                blocked += 1
            if analysis.parse_status == "parsed":
                self.assertTrue(
                    analysis.reconciliation["balanced"],
                    f"{row['external_id']} 表级明细与查询总量不一致",
                )
        self.assertEqual(blocked, 18)


if __name__ == "__main__":
    unittest.main()
