from __future__ import annotations

from typing import Any


SUPPORTED_TEMPLATES = {"zh-lab", "zh-summary", "en-paper"}
UNKNOWN = "未自动推断"


def render_report(template: str, summary: dict[str, Any]) -> str:
    if template == "zh-lab":
        return _render_zh_lab(summary)
    if template == "zh-summary":
        return _render_zh_summary(summary)
    if template == "en-paper":
        return _render_en_paper(summary)
    raise ValueError(f"unsupported report template: {template}")


def _render_zh_lab(summary: dict[str, Any]) -> str:
    status = summary["provenance"]["status"]
    if status == "failed":
        return _render_zh_failure(summary, title="失败实验报告片段")
    if status == "cancelled":
        return _render_zh_cancelled(summary, title="取消实验报告片段")

    metrics = summary["metrics"]
    figures = summary["figures"]
    provenance = summary["provenance"]
    lines = [
        "# 实验报告片段",
        "",
        "## 实验概览",
        "",
        f"- task_id: `{provenance['task_id']}`",
        f"- status: `{provenance['status']}`",
        f"- mode: `{provenance['mode']}`",
        f"- 自动结论: 指标行数为 `{metrics['row_count']}`，其余实验目的和复杂科研结论为{UNKNOWN}。",
        "",
        "## 实验设置与来源",
        "",
        *_provenance_table(provenance),
        "",
        "## 指标摘要",
        "",
        f"- 指标文件: `{metrics['path']}`",
        f"- 指标行数: `{metrics['row_count']}`",
        f"- 指标列名: {_format_columns(metrics)}",
        f"- collection summary: `{metrics.get('collection_summary_path') or UNKNOWN}`",
    ]
    lines.extend(_scenario_lines(metrics))
    detected_fields = metrics.get("detected_fields") or []
    if detected_fields:
        lines.append(f"- detected fields: {', '.join(f'`{field}`' for field in detected_fields)}")
    lines.extend(["", *_numeric_summary_table(metrics), "", "## 图表与结果", ""])
    lines.extend(_figure_section(figures))
    lines.extend(
        [
            "",
            "## 复现信息",
            "",
            f"- command: `{provenance['command']}`",
            f"- source_path: `{provenance['source_path']}`",
            f"- working_dir: `{provenance['working_dir']}`",
            f"- reproduce command: `{summary['reproduce'].get('command_path') or UNKNOWN}`",
            f"- exit_code: `{provenance['exit_code']}`",
            "",
            "## 注意事项",
            "",
            "- 本报告由确定性模板生成，不使用 AI。",
            "- 报告只汇总已存在 artifact 中的数值，不保证自动解释复杂科研结论。",
            f"- 无法从 artifact 判断的内容标记为{UNKNOWN}。",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_zh_summary(summary: dict[str, Any]) -> str:
    status = summary["provenance"]["status"]
    if status == "failed":
        return _render_zh_failure(summary, title="失败实验摘要")
    if status == "cancelled":
        return _render_zh_cancelled(summary, title="取消实验摘要")

    metrics = summary["metrics"]
    provenance = summary["provenance"]
    lines = [
        "# 实验摘要",
        "",
        f"- task_id: `{provenance['task_id']}`",
        f"- status: `{provenance['status']}`",
        f"- mode: `{provenance['mode']}`",
        f"- 来源: `{provenance['command'] if provenance['command'] != UNKNOWN else provenance['source_path']}`",
        f"- 指标: `{metrics['path']}`，共 `{metrics['row_count']}` 行。",
        f"- 场景摘要: {_scenario_inline(metrics)}",
        f"- 图表数量: `{summary['figures']['figure_count']}`",
        f"- 复现目录信息: command=`{summary['reproduce'].get('command_path') or UNKNOWN}`，working_dir=`{provenance['working_dir']}`。",
        f"- 注意事项: 本摘要不使用 AI；无法判断的内容为{UNKNOWN}。",
        "",
    ]
    numeric = metrics.get("numeric_summaries") or []
    if numeric:
        lines.extend(["## 主要数值列", "", *_numeric_summary_table(metrics, limit=3), ""])
    lines.extend(["## 图表", "", *_figure_section(summary["figures"])])
    return "\n".join(lines) + "\n"


def _render_en_paper(summary: dict[str, Any]) -> str:
    status = summary["provenance"]["status"]
    if status == "failed":
        return _render_en_failure(summary)
    if status == "cancelled":
        return _render_en_cancelled(summary)

    metrics = summary["metrics"]
    provenance = summary["provenance"]
    lines = [
        "# Experimental Summary Fragment",
        "",
        "## Overview",
        "",
        f"- task_id: `{provenance['task_id']}`",
        f"- status: `{provenance['status']}`",
        f"- mode: `{provenance['mode']}`",
        f"- Automatically inferred conclusion: `{metrics['row_count']}` metric row(s) were found; higher-level interpretation is {UNKNOWN}.",
        "",
        "## Provenance",
        "",
        *_provenance_table(provenance),
        "",
        "## Metrics",
        "",
        f"- Metrics artifact: `{metrics['path']}`",
        f"- Row count: `{metrics['row_count']}`",
        f"- Columns: {_format_columns(metrics)}",
        *_scenario_lines(metrics, english=True),
        "",
        *_numeric_summary_table(metrics),
        "",
        "## Figures",
        "",
        *_figure_section(summary["figures"], missing_text=f"No figures are recorded. Run `labsidecar figures {provenance['task_id']}` before using this section."),
        "",
        "## Reproducibility",
        "",
        f"- command: `{provenance['command']}`",
        f"- source_path: `{provenance['source_path']}`",
        f"- working_dir: `{provenance['working_dir']}`",
        f"- exit_code: `{provenance['exit_code']}`",
        "",
        "## Notes",
        "",
        "- This fragment is generated by deterministic templates and does not use AI.",
        "- Scenario summaries are descriptive only and do not infer statistical significance.",
        f"- Any unsupported inference is marked as {UNKNOWN}.",
    ]
    return "\n".join(lines) + "\n"


def _render_zh_failure(summary: dict[str, Any], title: str) -> str:
    provenance = summary["provenance"]
    failure = summary["failure"]
    lines = [
        f"# {title}",
        "",
        "## 失败概览",
        "",
        f"- task_id: `{provenance['task_id']}`",
        f"- status: `{provenance['status']}`",
        f"- exit_code: `{provenance['exit_code']}`",
        f"- failure_summary: {failure.get('failure_summary') or UNKNOWN}",
        "",
        "## 实验设置与来源",
        "",
        *_provenance_table(provenance),
        "",
        "## stderr.log 尾部",
        "",
        *_log_block(failure.get("stderr_tail") or []),
        "",
        "## 复现信息",
        "",
        f"- command: `{provenance['command']}`",
        f"- working_dir: `{provenance['working_dir']}`",
        f"- reproduce/command.txt: `{failure.get('reproduce_command_path') or UNKNOWN}`",
        "",
        "## 注意事项",
        "",
        "- 该任务状态不是 completed，本报告不写成成功实验结果分析。",
        "- 本报告由确定性模板生成，不使用 AI。",
    ]
    return "\n".join(lines) + "\n"


def _render_zh_cancelled(summary: dict[str, Any], title: str) -> str:
    provenance = summary["provenance"]
    cancellation = summary["cancellation"]
    lines = [
        f"# {title}",
        "",
        "## 取消概览",
        "",
        f"- task_id: `{provenance['task_id']}`",
        f"- status: `{provenance['status']}`",
        f"- cancellation note: {cancellation.get('note') or UNKNOWN}",
        "",
        "## 实验设置与来源",
        "",
        *_provenance_table(provenance),
        "",
        "## stderr.log 尾部",
        "",
        *_log_block(cancellation.get("stderr_tail") or []),
        "",
        "## 复现信息",
        "",
        f"- command: `{provenance['command']}`",
        f"- working_dir: `{provenance['working_dir']}`",
        f"- started_at: `{provenance['started_at']}`",
        f"- finished_at: `{provenance['finished_at']}`",
        "",
        "## 注意事项",
        "",
        "- 该任务状态为 cancelled，本报告不写成成功实验结果分析。",
        "- 本报告由确定性模板生成，不使用 AI。",
    ]
    return "\n".join(lines) + "\n"


def _render_en_failure(summary: dict[str, Any]) -> str:
    provenance = summary["provenance"]
    failure = summary["failure"]
    lines = [
        "# Failed Experiment Fragment",
        "",
        "## Failure Summary",
        "",
        f"- task_id: `{provenance['task_id']}`",
        f"- status: `{provenance['status']}`",
        f"- exit_code: `{provenance['exit_code']}`",
        f"- failure_summary: {failure.get('failure_summary') or UNKNOWN}",
        "",
        "## Provenance",
        "",
        *_provenance_table(provenance),
        "",
        "## stderr.log Tail",
        "",
        *_log_block(failure.get("stderr_tail") or []),
        "",
        "## Reproduce",
        "",
        f"- command: `{provenance['command']}`",
        f"- working_dir: `{provenance['working_dir']}`",
        f"- reproduce/command.txt: `{failure.get('reproduce_command_path') or UNKNOWN}`",
        "",
        "## Notes",
        "",
        "- This task is not completed, so this report does not summarize it as a successful experiment.",
        "- This fragment is generated by deterministic templates and does not use AI.",
    ]
    return "\n".join(lines) + "\n"


def _render_en_cancelled(summary: dict[str, Any]) -> str:
    provenance = summary["provenance"]
    cancellation = summary["cancellation"]
    lines = [
        "# Cancelled Experiment Fragment",
        "",
        "## Cancellation Summary",
        "",
        f"- task_id: `{provenance['task_id']}`",
        f"- status: `{provenance['status']}`",
        f"- cancellation note: {cancellation.get('note') or UNKNOWN}",
        "",
        "## Provenance",
        "",
        *_provenance_table(provenance),
        "",
        "## stderr.log Tail",
        "",
        *_log_block(cancellation.get("stderr_tail") or []),
        "",
        "## Notes",
        "",
        "- This task is cancelled, so this report does not summarize it as a successful experiment.",
        "- This fragment is generated by deterministic templates and does not use AI.",
    ]
    return "\n".join(lines) + "\n"


def _scenario_inline(metrics: dict[str, Any]) -> str:
    scenario = metrics.get("scenario") if isinstance(metrics.get("scenario"), dict) else {}
    if not scenario.get("present"):
        return f"`{UNKNOWN}`"
    primary = scenario.get("primary_metric") if isinstance(scenario.get("primary_metric"), dict) else {}
    return (
        f"`{scenario.get('scenario_type') or UNKNOWN}`; "
        f"primary_metric=`{primary.get('name') or UNKNOWN}`; "
        "no statistical significance inferred"
    )


def _scenario_lines(metrics: dict[str, Any], english: bool = False) -> list[str]:
    scenario = metrics.get("scenario") if isinstance(metrics.get("scenario"), dict) else {}
    if not scenario.get("present"):
        return []
    primary = scenario.get("primary_metric") if isinstance(scenario.get("primary_metric"), dict) else {}
    seed_aggregates = scenario.get("seed_aggregates") if isinstance(scenario.get("seed_aggregates"), dict) else {}
    if english:
        lines = [
            f"- Scenario summary: `{scenario.get('path') or 'metrics/scenario-summary.json'}`",
            f"- Scenario type: `{scenario.get('scenario_type') or UNKNOWN}`",
            f"- Primary metric: `{primary.get('name') or UNKNOWN}` ({primary.get('direction') or UNKNOWN})",
        ]
        if seed_aggregates.get("present"):
            lines.append("- Seed aggregates: descriptive aggregate only; no statistical significance is inferred.")
        return lines
    lines = [
        f"- scenario summary: `{scenario.get('path') or 'metrics/scenario-summary.json'}`",
        f"- 场景类型: `{scenario.get('scenario_type') or UNKNOWN}`",
        f"- 主指标: `{primary.get('name') or UNKNOWN}` ({primary.get('direction') or UNKNOWN})",
    ]
    if seed_aggregates.get("present"):
        lines.append("- seed aggregates: 仅描述性聚合，不推断统计显著性。")
    return lines


def _provenance_table(provenance: dict[str, Any]) -> list[str]:
    rows = [
        ("task_id", provenance["task_id"]),
        ("status", provenance["status"]),
        ("mode", provenance["mode"]),
        ("command", provenance["command"]),
        ("source_path", provenance["source_path"]),
        ("working_dir", provenance["working_dir"]),
        ("created_at", provenance["created_at"]),
        ("started_at", provenance["started_at"]),
        ("finished_at", provenance["finished_at"]),
        ("exit_code", provenance["exit_code"]),
    ]
    return [
        "| 字段 | 值 |",
        "| --- | --- |",
        *[f"| {key} | `{value}` |" for key, value in rows],
    ]


def _numeric_summary_table(metrics: dict[str, Any], limit: int | None = None) -> list[str]:
    numeric = metrics.get("numeric_summaries") or []
    if limit is not None:
        numeric = numeric[:limit]
    if not numeric:
        return [f"数值列摘要: {UNKNOWN}"]

    lines = [
        "| column | count | mean | min | max |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in numeric:
        lines.append(
            "| {column} | {count} | {mean} | {min} | {max} |".format(
                column=item["column"],
                count=item["count"],
                mean=_format_number(item["mean"]),
                min=_format_number(item["min"]),
                max=_format_number(item["max"]),
            )
        )
    omitted = metrics.get("numeric_omitted_count", 0)
    if omitted:
        lines.append(f"| ... | omitted {omitted} numeric column(s) |  |  |  |")
    return lines


def _figure_section(figures: dict[str, Any], missing_text: str | None = None) -> list[str]:
    items = figures.get("items") or []
    if not items:
        return [missing_text or f"尚未生成图表，可运行 labsidecar figures {figures['task_id']}。"]

    lines = [
        "| figure_id | chart_type | PNG | SVG | x | y | group_by |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        png = item.get("png_path") or UNKNOWN
        svg = item.get("svg_path") or UNKNOWN
        lines.append(
            "| {figure_id} | {chart_type} | {png} | {svg} | {x} | {y} | {group_by} |".format(
                figure_id=item.get("figure_id") or UNKNOWN,
                chart_type=item.get("chart_type") or UNKNOWN,
                png=f"[PNG]({png})" if png != UNKNOWN else UNKNOWN,
                svg=f"[SVG]({svg})" if svg != UNKNOWN else UNKNOWN,
                x=item.get("x") or UNKNOWN,
                y=item.get("y") or UNKNOWN,
                group_by=item.get("group_by") or UNKNOWN,
            )
        )
    return lines


def _log_block(lines: list[str]) -> list[str]:
    if not lines:
        return [UNKNOWN]
    return ["```text", *lines, "```"]


def _format_columns(metrics: dict[str, Any]) -> str:
    columns = metrics.get("displayed_columns") or []
    if not columns:
        return UNKNOWN
    text = ", ".join(f"`{column}`" for column in columns)
    omitted = metrics.get("omitted_column_count", 0)
    if omitted:
        text += f", ... (omitted {omitted})"
    return text


def _format_number(value: Any) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
