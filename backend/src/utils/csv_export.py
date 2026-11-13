"""CSV export for the optimisation list (UTF-8 BOM so Excel 不出现乱码)."""
import csv
import io

from src.utils.formatting import cny, gib, pct

COLUMNS = [
    "建议编号",
    "查询编号",
    "业务标题",
    "目标表",
    "反模式",
    "风险级别",
    "置信度",
    "改写前扫描(GiB)",
    "改写后扫描(GiB)",
    "节省(GiB)",
    "节省比例",
    "单次节省(元)",
    "排序分",
    "状态",
]


def suggestions_csv(rows: list[dict]) -> str:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for row in rows:
        writer.writerow(
            [
                row["suggestion_no"],
                row["query_external_id"],
                row["query_title"],
                row["target_table"] or "-",
                "/".join(row["anti_patterns"]),
                row["risk_level"],
                f"{row['confidence']:.2f}",
                f"{gib(row['before_scan_bytes']):.3f}",
                f"{gib(row['after_scan_bytes']):.3f}",
                f"{gib(row['saving_bytes']):.3f}",
                pct(row["saving_pct"]),
                cny(row["saving_cost_cny"]),
                f"{row['score']:.0f}",
                row["status"],
            ]
        )
    return buffer.getvalue()
