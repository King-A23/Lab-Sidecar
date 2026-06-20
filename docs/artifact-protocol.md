# Lab-Sidecar 本地 Artifact 协议

本协议只定义 V1 需要的本地文件约定，目标是简单、可恢复、可迁移，不做企业级平台设计。

## 设计原则

- `manifest.json` 是单任务的最小事实来源。
- SQLite 只做索引和查询加速，不做唯一事实来源。
- 所有自动产物默认写入 `.lab-sidecar/`，不覆盖用户原始文件。
- 优先记录相对 workspace 的路径，保证项目可整体移动。
- 大文件默认引用而不是复制。

## `.lab-sidecar/` 目录结构

```text
.lab-sidecar/
  config.yaml
  index.sqlite
  tasks/
    task_20260531_143000_a1b2c3/
      manifest.json
      stdout.log
      stderr.log
      raw/
      metrics/
      figures/
      reports/
      reproduce/
      slides/
      intelligence/
```

## 单个 task 目录结构

```text
.lab-sidecar/tasks/<task_id>/
  manifest.json
  stdout.log
  stderr.log
  raw/
    source_refs.json
  metrics/
    normalized_metrics.csv
    normalized_metrics.json
  figures/
    figure-spec.yaml
    figure-summary.json
    accuracy_curve.png
    accuracy_curve.svg
  intelligence/
    worker_run_20260620_120000_a1b2c3/
      figure-request.json
      worker-request.json
      worker-result.json
      validator-result.json
      adoption-record.json
      diagnostics.md
      sandbox/
  reports/
    report-fragment.md
    report-summary.json
  slides/
    presentation-draft.pptx
    slides-summary.json
  reproduce/
    command.txt
    env.json
    git.json
    inputs.json
```

V1 中不强制每个子目录都存在；只有在对应阶段产物出现时才创建。

## `manifest.json` 最小字段

最小字段应足够支持 `status`、`logs`、`artifacts` 和 SQLite 重建：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | string | 协议版本，例如 `1` |
| `task_id` | string | 任务唯一 ID |
| `mode` | string | `run` 或 `ingest` |
| `status` | string | 见状态定义 |
| `created_at` | string | ISO 8601 时间 |
| `updated_at` | string | ISO 8601 时间 |
| `working_dir` | string | 相对 workspace 路径，若不在 workspace 内则存绝对路径 |
| `command` | string or null | `run` 模式下的原始命令 |
| `source_path` | string or null | `ingest` 模式下的源目录或源文件 |
| `exit_code` | integer or null | 进程结束后填写 |
| `paths` | object | 至少包含 `stdout`、`stderr`、`task_dir` |
| `artifacts` | array | 当前任务产生的 artifact 列表 |

推荐但非最小必需字段：

- `name`
- `started_at`
- `finished_at`
- `failure_summary`
- `source_refs`
- `git_commit`

示例：

```json
{
  "schema_version": "1",
  "task_id": "task_20260531_143000_a1b2c3",
  "mode": "run",
  "status": "completed",
  "created_at": "2026-05-31T14:30:00+08:00",
  "updated_at": "2026-05-31T14:55:12+08:00",
  "working_dir": ".",
  "command": "python train.py --config configs/exp.yaml",
  "source_path": null,
  "exit_code": 0,
  "paths": {
    "task_dir": ".lab-sidecar/tasks/task_20260531_143000_a1b2c3",
    "stdout": ".lab-sidecar/tasks/task_20260531_143000_a1b2c3/stdout.log",
    "stderr": ".lab-sidecar/tasks/task_20260531_143000_a1b2c3/stderr.log"
  },
  "artifacts": [
    {
      "artifact_id": "fig_accuracy_curve",
      "type": "figure",
      "path": ".lab-sidecar/tasks/task_20260531_143000_a1b2c3/figures/accuracy_curve.png",
      "source_paths": [
        "runs/exp/metrics.csv"
      ],
      "description": "Validation accuracy curve"
    }
  ]
}
```

## stdout / stderr 日志保存规则

- `stdout.log` 和 `stderr.log` 分开保存，默认 UTF-8。
- 任务创建时就生成两个文件；没有内容时允许为空文件。
- 运行期间只追加，不覆盖，不截断。
- `labsidecar logs` 直接读取这两个文件，不依赖数据库。
- 若用户命令本身已把输出重定向到别处，Lab-Sidecar 仍应保存自己捕获到的 stdout/stderr。
- 失败任务的最后一段 stderr 应额外写入 `manifest.json` 的 `failure_summary`，便于快速诊断。

## 目录职责

### `metrics/`

保存结构化、可复用的指标结果，例如规范化后的 CSV、JSON。
`metrics/collection-summary.json` 还可以包含 `bounded_analysis`，用于记录受限的
best-row、checkpoint 和 anomaly 摘要。这些摘要只引用
`metrics/normalized_metrics.csv` 的行号和少量字段，不内嵌完整指标表。

### `figures/`

保存图表输出和图表配置，例如 `.png`、`.svg`、`figure-spec.yaml`。

确定性图表生成只支持受控的 `line`、`bar`、`box` 路径。显式 spec 请求
其他图表类型时，`figures/figure-summary.json` 会记录
`unsupported_chart_diagnostics`。只有在用户显式传入 `--fallback bounded`
时，才会创建 `intelligence/<worker_run_id>/` 下的 bounded fallback 记录。

fallback 状态记录在 `figure-summary.json` 的 `fallback` 字段：

- `not_needed`：未尝试 fallback。确定性图表已生成，或 fallback 为默认
  `off`。
- `unavailable`：写入了 `figure-request.json`，但没有可用 chart worker。
- `rejected`：worker 输出未通过 validator；不得写入 official `figures/`
  或 manifest figure artifact。
- `adopted`：validator 接受 sandbox 输出后，才复制 official PNG/SVG 到
  `figures/`，写入 `adoption-record.json`，并刷新 manifest 与
  `provenance/traceability.json`。

official `figures/` 只能由确定性 renderer 或 validator/adoption 路径写入。
worker 不允许直接写入 `figures/`、`manifest.json`、`provenance/`、`reports/`
或 `slides/`。

### `intelligence/`

保存 bounded worker/fallback 审计记录。Alpha4 chart fallback 使用：

```text
intelligence/<worker_run_id>/
  figure-request.json
  worker-request.json        # worker 被调用时存在
  worker-result.json         # worker 被调用时存在
  validator-result.json
  adoption-record.json       # 只有 adopted 时存在
  diagnostics.md
  sandbox/
```

`sandbox/` 是 worker 唯一可写区域。validator 会拒绝绝对路径、`..` 路径、
缺失文件、未声明字段、缺失 source metrics traceability、不可解析或过小/空白
PNG/SVG。被拒绝的输出只能保留为 sandbox diagnostics，不能污染 official
artifacts。

`figure-request.json`、`validator-result.json`、`adoption-record.json` 和
traceability fallback lineage 必须保持 bounded：记录路径、hash、列名、行数、
字段来源、validator checks 和 omission notes，但不内嵌完整 raw source、
完整 `metrics/normalized_metrics.csv` 行、完整 stdout/stderr、report body、
PPTX 内容、worker prompt/response body、sandbox proposal body 或 artifact body。

### `reports/`

保存 Markdown 报告片段、摘要和展示用 bullet 列表。

### `raw/`

保存轻量级原始结果引用或经授权复制的小型原始输出。默认优先存 `source_refs.json`，不直接复制大数据集。

### `reproduce/`

保存复现所需的命令、环境和源文件引用，例如 `command.txt`、`env.json`、`git.json`、`inputs.json`。

## Artifact 类型定义

| 类型 | 含义 | 典型文件 |
| --- | --- | --- |
| `figure` | 可直接放入报告或 PPT 的静态图 | `.png`, `.svg` |
| `table` | 结构化结果表 | `.csv`, `.md` |
| `report` | Markdown 报告片段或摘要 | `.md` |
| `presentation` | 可编辑的静态演示文稿草稿 | `.pptx` |
| `log` | stdout / stderr 或摘要日志 | `.log` |
| `config` | 图表配置、任务配置快照 | `.yaml`, `.json` |
| `raw` | 原始结果引用或小型拷贝 | `.json`, `.csv`, `.txt` |
| `reproduce` | 复现信息 | `.txt`, `.json`, `.md` |

每个 artifact 记录至少应包含：

- `artifact_id`
- `type`
- `path`
- `description`
- `source_paths`（可为空数组）

### `presentation` 当前约定

当前已实现的 presentation artifact 是静态、可编辑 PPTX 草稿：

- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

`manifest.json` 中的 PPTX artifact 使用：

```json
{
  "artifact_id": "slides_presentation_draft_pptx",
  "type": "presentation",
  "path": "slides/presentation-draft.pptx",
  "description": "Static editable presentation draft",
  "source_paths": [
    "manifest.json",
    "metrics/normalized_metrics.csv",
    "figures/figure-summary.json",
    "reports/report-fragment.md"
  ]
}
```

`slides-summary.json` 是 presentation 的 provenance 入口，至少应记录：

- `task_id`
- `template`
- `slide_count`
- 每页的 `slide_index`、`title`、`purpose`、`source_artifacts`
- 使用到的 metrics、figures、reports、logs
- 截断记录；非日志长文本可保留 `full`，但 stdout/stderr 日志类截断只保留
  bounded `display` 和 omitted metadata，不保留完整日志正文
- `qa_checks`，包括页数、空白页、标题、artifact 重复、表格和 caption 溢出保护

MCP-facing 响应只返回 presentation artifact 路径、摘要和 QA 状态，不返回 PPTX 二进制内容、完整 `slides-summary.json` body 或完整 report body。

### `media` / `animation` 预留约定

`media` 与 `animation` 是协议预留，不是当前已实现能力。

未来如果实现，必须先补充验收清单和 provenance 字段。建议边界：

| 类型 | 预留含义 | 典型文件 | 当前状态 |
| --- | --- | --- | --- |
| `media` | 可被报告或 PPT 引用的静态/动态媒体文件 | `.png`, `.jpg`, `.gif`, `.mp4` | deferred |
| `animation` | 可复现的动画源描述或渲染输出 | `.json`, `.py`, `.mp4`, `.gif` | deferred |

在未实现前，Lab-Sidecar 不应把 GIF、MP4、Manim、Remotion、PowerPoint 原生动画或类似输出描述成已支持能力。未来媒体 artifact 也应遵守同样的路径、source_paths、summary/provenance 和不覆盖用户源文件规则。

## Task 状态定义

| 状态 | 含义 |
| --- | --- |
| `pending` | 任务已创建，尚未启动实际执行 |
| `running` | 用户命令或导入扫描正在进行 |
| `completed` | 主任务成功完成，核心产物可用 |
| `failed` | 主任务失败，需保留可诊断信息 |
| `cancelled` | 用户主动取消，进程已终止或导入已中止 |

V1 推荐状态流转：

- `pending -> running -> completed`
- `pending -> running -> failed`
- `pending -> running -> cancelled`

## 路径规则

- 只要目标在 workspace 内，`manifest.json` 中一律保存相对 workspace 路径。
- JSON 中统一使用正斜杠 `/` 作为路径分隔符；CLI 展示时再转回当前系统样式。
- 如果源路径不在 workspace 内，允许保存绝对路径，但应额外标注 `path_kind: "absolute"`。
- `working_dir`、`source_path`、`artifact.path` 都遵循同一规则。

## 不覆盖用户原文件的规则

- 默认所有 Sidecar 生成物都写到 `.lab-sidecar/tasks/<task_id>/` 下。
- `ingest` 只读取用户提供的目录或文件，不回写源目录。
- 同一命令重跑时创建新的 `task_id`，而不是复用旧任务目录。
- `collect`、`figures`、`report` 只覆盖当前任务目录中的同名派生产物，不覆盖用户原始输入文件。

## 不复制大型未授权数据文件的规则

- 默认不复制数据集、checkpoint、视频、压缩包等大型文件。
- 建议 V1 的默认复制阈值为 50 MB；大于该阈值时只记录路径、大小、修改时间和可选 hash。
- 对于 workspace 外的大文件，一律只记录引用，不自动搬运进 `.lab-sidecar/`。
- 如未来需要支持复制，必须通过显式参数开启，而不是默认行为。

## 失败任务如何保存可诊断信息

失败任务至少应保留：

- `manifest.json` 中的 `status=failed`、`exit_code`、`failure_summary`
- 完整 `stdout.log`
- 完整 `stderr.log`
- `reproduce/command.txt`
- `reproduce/env.json`
- `raw/source_refs.json` 或 `reproduce/inputs.json`

如果失败前已经产生部分产物：

- 保留这些文件，不自动删除。
- 不把明显不完整的图表或报告标记为最终可用 artifact。
- 允许在 `manifest.json` 中附加 `notes` 或 `partial_artifacts` 字段说明哪些文件只是中间残留。

## 如何从 `manifest.json` 重建 SQLite 索引

SQLite 丢失或损坏时，以 `.lab-sidecar/tasks/*/manifest.json` 为准重建：

1. 扫描 `.lab-sidecar/tasks/` 下所有一级子目录。
2. 读取每个目录中的 `manifest.json`。
3. 校验 `task_id`、`status`、`updated_at` 和 `paths.task_dir`。
4. 将任务摘要字段 upsert 到 `tasks` 表。
5. 将 `manifest.artifacts` 展开后 upsert 到 `artifacts` 表。
6. 若同一个 `task_id` 出现冲突，以 `updated_at` 更新更晚的一份为准。

推荐最小索引表：

- `tasks(task_id, mode, status, created_at, updated_at, working_dir, command, source_path, exit_code)`
- `artifacts(task_id, artifact_id, type, path, description)`

结论：删掉 `index.sqlite` 不应导致任务不可恢复；最多只是查询变慢，直到重建完成。
