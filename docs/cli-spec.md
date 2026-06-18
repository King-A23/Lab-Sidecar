# Lab-Sidecar CLI 规范（V1）

本规范冻结命令名和基本行为，但不要求所有命令都在 Phase 1 同时实现。输出风格以学生和开发者易读为先，默认人类可读，不追求企业平台式冗长 JSON。

## 通用约定

- 默认 workspace 为当前目录。
- `task_id` 推荐格式：`task_YYYYMMDD_HHMMSS_<6位短随机串>`。
- 默认所有产物写入 `.lab-sidecar/tasks/<task_id>/`。
- 除 `open` 外，所有命令都应在终端里给出明确的下一步提示。

建议退出码：

- `0`：成功
- `2`：参数错误
- `3`：任务不存在
- `4`：任务当前状态不允许该操作
- `5`：所需 artifact 尚未准备好

## `labsidecar init`

**用途**

初始化当前 workspace 的 `.lab-sidecar/` 目录和基础配置。

**参数**

- 无必需参数
- 可选：`--force` 仅重建缺失的配置与索引，不删除旧任务

**成功输出示例**

```text
Initialized Lab-Sidecar workspace.
Root: C:\code\Lab-Sidecar
State dir: .lab-sidecar
Index: .lab-sidecar/index.sqlite
```

**失败输出示例**

```text
Error: C:\code\Lab-Sidecar is already initialized.
Hint: use 'labsidecar init --force' to recreate missing files only.
```

**会读取哪些文件**

- 当前目录是否已存在 `.lab-sidecar/`
- 若使用 `--force`，会读取现有 `.lab-sidecar/config.yaml`

**会写入哪些文件**

- `.lab-sidecar/config.yaml`
- `.lab-sidecar/index.sqlite`
- `.lab-sidecar/tasks/`

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

必须。

## `labsidecar run "python train.py --config configs/exp.yaml"`

**用途**

把一条本地命令注册为 Sidecar 任务并执行，保存日志、状态和复现信息。

**参数**

- 必需：一条完整命令字符串
- 可选：`--name <task_name>`
- 可选：`--cwd <path>`

**成功输出示例**

```text
Task created: task_20260531_153044_8fd2ac
Status: running
Command: python train.py --config configs/exp.yaml
Logs: .lab-sidecar/tasks/task_20260531_153044_8fd2ac/stdout.log
Use 'labsidecar status task_20260531_153044_8fd2ac' to check progress.
```

**失败输出示例**

```text
Error: command could not be started.
Reason: python was not found in PATH.
```

**会读取哪些文件**

- `.lab-sidecar/config.yaml`
- `.lab-sidecar/index.sqlite`（若存在）
- `--cwd` 指定目录中的命令与输入文件由用户命令自己读取

**会写入哪些文件**

- 新任务目录下的 `manifest.json`
- `stdout.log`
- `stderr.log`
- `reproduce/command.txt`
- `reproduce/env.json`
- `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

Lab-Sidecar 自身不会直接修改；但用户提供的命令可能会修改自己的工作目录产物。

**Phase 1 是否必须实现**

必须。

## `labsidecar status <task_id>`

**用途**

查看任务状态、开始时间、退出码和主要 artifact 摘要。

**参数**

- 必需：`<task_id>`

**成功输出示例**

```text
Task: task_20260531_153044_8fd2ac
Name: baseline cnn
Status: completed
Mode: run
Command: python train.py --config configs/exp.yaml
Working dir: .
Artifact dir: .lab-sidecar/tasks/task_20260531_153044_8fd2ac
Exit code: 0
Created: 2026-05-31T15:30:44+08:00
Started: 2026-05-31T15:30:44+08:00
Finished: 2026-05-31T15:41:12+08:00
Artifacts: 5
Artifact types: config=2, log=2, table=1
Key artifacts:
- metrics: metrics/normalized_metrics.csv
Next:
- labsidecar summarize task_20260531_153044_8fd2ac
- labsidecar collect task_20260531_153044_8fd2ac
- labsidecar figures task_20260531_153044_8fd2ac
- labsidecar report task_20260531_153044_8fd2ac
```

**失败输出示例**

```text
Error: task 'task_20260531_153044_8fd2ac' was not found.
Hint: check whether the task directory still exists under .lab-sidecar/tasks/.
```

**会读取哪些文件**

- `.lab-sidecar/index.sqlite`
- 对应任务的 `manifest.json`

**会写入哪些文件**

- 默认不写
- 若实现自动索引修复，可重建 `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

必须。

## `labsidecar list --limit 20`

**用途**

扫描当前 workspace 的任务 manifest，按最近更新时间列出任务，帮助用户不进入 `.lab-sidecar/tasks/` 也能找到任务。

**参数**

- 可选：`--limit <N>`，默认 `20`
- 可选：`--status pending|running|completed|failed|cancelled`

**成功输出示例**

```text
task_id                         status     created_at                 finished_at                updated_at                 artifacts  name
task_20260531_160210_3b20ef     completed  2026-05-31T16:02:10+08:00  2026-05-31T16:02:11+08:00  2026-05-31T16:02:11+08:00  8          csv import
task_20260531_153044_8fd2ac     failed     2026-05-31T15:30:44+08:00  2026-05-31T15:31:02+08:00  2026-05-31T15:31:02+08:00  6          failure smoke
```

若没有任务，输出：

```text
No tasks found.
```

**失败输出示例**

```text
Usage: labsidecar list [OPTIONS]
Error: Invalid value for '--status': 'unknown' is not one of 'pending', 'running', 'completed', 'failed', 'cancelled'.
```

**会读取哪些文件**

- `.lab-sidecar/tasks/*/manifest.json`
- 运行中任务的进程状态（用于安全刷新 stale running 状态）

**会写入哪些文件**

- 若刷新运行中任务状态或修复本地索引，可能更新对应 `manifest.json` 与 `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会。

**Stage 1 是否必须实现**

必须。

## `labsidecar summarize <task_id>`

**用途**

打印一个有边界的任务摘要：任务身份、状态、命令或来源、artifact 概览、指标行数、图表数量、报告和 PPT 路径，以及下一步命令。它是 CLI 里的 compact preview，不打印完整日志、完整指标表、报告正文或 PPT 内容。

**参数**

- 必需：`<task_id>`

**成功输出示例**

```text
Task: task_20260531_160210_3b20ef
Name: csv import
Status: completed
Mode: ingest
Source: examples/csv-comparison
Artifact dir: .lab-sidecar/tasks/task_20260531_160210_3b20ef
Created: 2026-05-31T16:02:10+08:00
Finished: 2026-05-31T16:02:10+08:00
Artifacts: 12
Artifact types: config=3, figure=4, raw=1, report=1, table=2
Key artifacts:
- metrics: metrics/normalized_metrics.csv
- figures: figures/figure-summary.json
- report: reports/report-fragment.md
- slides: slides/presentation-draft.pptx
Metrics:
- rows: 15
- detected fields: epoch, model, seed, val_accuracy, val_loss
- summary: metrics/collection-summary.json
- normalized table: metrics/normalized_metrics.csv
Figures:
- generated figures: 2
- summary: figures/figure-summary.json
Report:
- reports/report-fragment.md
Slides:
- slides/presentation-draft.pptx
Next:
- labsidecar summarize task_20260531_160210_3b20ef
- labsidecar collect task_20260531_160210_3b20ef
- labsidecar figures task_20260531_160210_3b20ef
- labsidecar report task_20260531_160210_3b20ef
```

**失败输出示例**

```text
Error: task 'task_20260531_160210_3b20ef' was not found.
Hint: check whether the task directory still exists under .lab-sidecar/tasks/.
```

**会读取哪些文件**

- `manifest.json`
- `metrics/collection-summary.json`（若存在）
- `figures/figure-summary.json`（若存在）
- `reports/report-fragment.md` 与 `slides/presentation-draft.pptx` 的存在性

**会写入哪些文件**

- 若刷新运行中任务状态，可能更新对应 `manifest.json` 与 `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会。

**Stage 1 是否必须实现**

必须。

## `labsidecar package <task_id> --output <dir>`

**用途**

为单个任务创建一个可分享、可检查的结果包或失败诊断包。输出是一个普通目录，适合交给同学、导师、reviewer 或主 Agent 查看。它只复制 Stage 2 allowlist 中的交付物，不把整个 `.lab-sidecar/tasks/<task_id>/` 实现目录打包。

成功任务会标记为 result package。失败、取消或仍在运行的任务会标记为 diagnostic package；失败任务 README 必须明确说明这是失败任务诊断包，不是成功实验总结。

**参数**

- 必需：`<task_id>`
- 必需：`--output <dir>` 或 `-o <dir>`，目标 package 目录。目录不存在时会创建；目录已存在时必须为空。

**成功输出示例**

```text
Package created: /tmp/lab-sidecar-package-task_20260531_160210_3b20ef
Type: result
Included files: 18
Omitted by default: 4
Unavailable optional files: 0
```

失败任务示例：

```text
Package created: /tmp/lab-sidecar-package-task_20260531_160315_aa22bb
Type: diagnostic
Included files: 5
Omitted by default: 3
Unavailable optional files: 9
```

**Package 目录形状**

```text
lab-sidecar-package-<task_id>/
  README.md
  manifest.json
  package-summary.json
  artifact-index.json
  redaction-notes.md
  reproduce/
  metrics/
  figures/
  reports/
  slides/
```

**默认会包含哪些文件**

- `manifest.json`
- `reproduce/command.txt`、`reproduce/env.json`、`reproduce/git.json`、`reproduce/dependencies.json`（若存在）
- `metrics/normalized_metrics.csv`、`metrics/normalized_metrics.json`、`metrics/collection-summary.json`（若存在）
- `figures/*.png`、`figures/*.svg`、`figures/figure-spec.yaml`、`figures/figure-summary.json`（若存在）
- `reports/report-fragment.md`、`reports/report-summary.json`（若存在）
- `slides/presentation-draft.pptx`、`slides/slides-summary.json`（若存在）
- package 自身的 `README.md`、`package-summary.json`、`artifact-index.json`、`redaction-notes.md`

缺失的可选 artifact 会记录到 `artifact-index.json` 的 `unavailable` 列表，不应导致 package 失败。

**默认不会包含哪些文件**

- 完整 `stdout.log`
- 完整 `stderr.log`
- raw source files 与 `raw/source_refs.json`
- `.lab-sidecar/index.sqlite`
- worker prompt/response bodies
- worker transcript / worker log
- temporary sandbox files
- unrelated workspace files

这些默认 omission 会写入 `redaction-notes.md` 和 `artifact-index.json`。

**失败输出示例**

```text
Error: task 'task_missing' was not found.
Hint: run 'labsidecar list' to find available task ids.
```

```text
Error: package output path is not usable.
Reason: /tmp/package-output already exists and is not empty
```

**会读取哪些文件**

- `manifest.json`
- allowlist 中列出的 task-local artifact
- task-local generated figure PNG/SVG files
- 只检查是否存在的默认 omission 文件，如 `stdout.log`、`stderr.log`、worker audit、sandbox、`.lab-sidecar/index.sqlite`

**会写入哪些文件**

- 目标 package 目录
- `README.md`
- `manifest.json`
- `package-summary.json`
- `artifact-index.json`
- `redaction-notes.md`
- allowlist artifact copies

**是否会修改用户原始文件**

不会。

**Stage 2 是否必须实现**

必须。

## `labsidecar compare <task_id_a> <task_id_b> [task_id...]`

**用途**

对 2 到 5 个已收集指标的本地任务做保守对比。命令读取每个任务的 `metrics/normalized_metrics.csv`，只使用每个任务的最后一行，只展示共同的数字字段，并列出跳过的非数字字段或任务特有字段。

它不做统计显著性检验，不推断科研结论，不默认聚合 seed。

**参数**

- 必需：2 到 5 个 `<task_id>`

**成功输出示例**

```text
Compared tasks: 2
Source: metrics/normalized_metrics.csv
Common numeric fields: epoch, val_accuracy, val_loss
Skipped common non-numeric fields: model
task_id                         status     metric        value  source
task_20260531_160210_3b20ef     completed  val_accuracy  0.86   metrics/normalized_metrics.csv
task_20260531_160215_33c8d1     completed  val_accuracy  0.89   metrics/normalized_metrics.csv
```

**失败输出示例**

```text
Error: metrics are missing for task(s): task_20260531_160210_3b20ef
Hint: run 'labsidecar collect <task_id>' before comparing.
```

```text
Error: no common numeric metric fields were found across the selected tasks.
Hint: compare tasks after collecting metrics with shared numeric columns.
```

```text
Error: compare supports at most 5 task ids.
```

**会读取哪些文件**

- 每个任务的 `manifest.json`
- 每个任务的 `metrics/normalized_metrics.csv`

**会写入哪些文件**

- 若刷新运行中任务状态，可能更新对应 `manifest.json` 与 `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会。

**Stage 1 是否必须实现**

必须。

## `labsidecar logs <task_id> --tail 100`

**用途**

查看某个任务的 stdout / stderr 日志尾部，用于确认进度或排查失败。

**参数**

- 必需：`<task_id>`
- 可选：`--tail <N>`，默认 `100`
- 可选：`--stream stdout|stderr|both`，默认 `both`

**成功输出示例**

```text
== stdout (last 5 lines) ==
epoch=4 train_loss=0.58 val_accuracy=0.83
epoch=5 train_loss=0.47 val_accuracy=0.86
Wrote metrics to runs/cnn_seed42/metrics.csv

== stderr (last 5 lines) ==
(empty)
```

**失败输出示例**

```text
Error: log files are not available for task 'task_20260531_153044_8fd2ac'.
Reason: task directory exists but stdout.log is missing.
```

**会读取哪些文件**

- 对应任务的 `stdout.log`
- 对应任务的 `stderr.log`
- `manifest.json`

**会写入哪些文件**

不会。

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

必须。

## `labsidecar cancel <task_id>`

**用途**

取消正在运行的任务，并把状态更新为 `cancelled`。

**参数**

- 必需：`<task_id>`

**成功输出示例**

```text
Cancellation requested: task_20260531_153044_8fd2ac
Status: cancelled
```

**失败输出示例**

```text
Error: task 'task_20260531_153044_8fd2ac' is not running.
Current status: completed
```

**会读取哪些文件**

- `manifest.json`
- `.lab-sidecar/index.sqlite`
- 任务进程记录（例如 PID，若实现）

**会写入哪些文件**

- `manifest.json`
- `stderr.log` 或 `reports/` 中的取消说明（实现自选）
- `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会直接修改；只终止 Sidecar 启动的进程。

**Phase 1 是否必须实现**

必须。

## `labsidecar ingest ./existing-results`

**用途**

把已有结果目录登记为 Sidecar 任务，而不重新执行实验。

**参数**

- 必需：`<path>`，可以是目录或单个文件
- 可选：`--name <task_name>`

**成功输出示例**

```text
Imported as task: task_20260531_160210_3b20ef
Source: .\existing-results
Status: completed
Next step: run 'labsidecar collect task_20260531_160210_3b20ef'
```

**失败输出示例**

```text
Error: path '.\existing-results' does not exist.
```

**会读取哪些文件**

- 目标目录中的 CSV、JSON、log 或其他结果文件
- `.lab-sidecar/config.yaml`

**会写入哪些文件**

- 新任务目录下的 `manifest.json`
- `raw/source_refs.json`
- `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

必须。

## `labsidecar collect <task_id>`

**用途**

扫描任务相关结果文件，提取或规范化指标到 `metrics/` 目录。

**参数**

- 必需：`<task_id>`
- 可选：`--config <yaml_path>` 指定显式字段映射或图表输入规则

**成功输出示例**

```text
Collected metrics for task_20260531_160210_3b20ef
Detected fields: epoch, val_accuracy, seed
Wrote: .lab-sidecar/tasks/task_20260531_160210_3b20ef/metrics/normalized_metrics.csv
```

**失败输出示例**

```text
Error: no supported metrics files were found for task 'task_20260531_160210_3b20ef'.
Hint: provide a mapping file with --config.
```

**会读取哪些文件**

- `manifest.json`
- `raw/source_refs.json`
- 任务关联的 CSV、JSON、log
- 可选的显式配置文件

**会写入哪些文件**

- `metrics/normalized_metrics.csv`
- `metrics/normalized_metrics.json`
- 更新后的 `manifest.json`
- `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

不是。建议在 Phase 2 实现。

## `labsidecar figures <task_id>`

**用途**

基于 `metrics/` 目录生成报告和 PPT 可直接使用的图表文件。

**参数**

- 必需：`<task_id>`
- 可选：`--spec <yaml_path>` 指定图表类型和字段映射

**成功输出示例**

```text
Generated 2 figures for task_20260531_160210_3b20ef
- figures/accuracy_curve.png
- figures/accuracy_curve.svg
```

**失败输出示例**

```text
Error: figure generation was refused.
Reason: required field 'epoch' is missing from normalized_metrics.csv.
```

**会读取哪些文件**

- `manifest.json`
- `metrics/normalized_metrics.csv`
- 可选图表配置文件

**会写入哪些文件**

- `figures/*.png`
- `figures/*.svg`
- `figures/figure-spec.yaml`
- 更新后的 `manifest.json`
- `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

不是。建议在 Phase 2 实现。

## `labsidecar report <task_id>`

**用途**

基于任务信息、指标和图表生成 Markdown 报告片段。

**参数**

- 必需：`<task_id>`
- 可选：`--template zh-lab|zh-summary|en-paper`

**成功输出示例**

```text
Report fragment created:
.lab-sidecar/tasks/task_20260531_160210_3b20ef/reports/report-fragment.md
```

**失败输出示例**

```text
Error: report generation requires collected metrics.
Hint: run 'labsidecar collect task_20260531_160210_3b20ef' first.
```

**会读取哪些文件**

- `manifest.json`
- `metrics/`
- `figures/`
- 可选模板文件

**会写入哪些文件**

- `reports/report-fragment.md`
- 可选 `reports/presentation-bullets.md`
- 更新后的 `manifest.json`
- `.lab-sidecar/index.sqlite`

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

不是。建议在 Phase 3 实现。

## `labsidecar artifacts <task_id>`

**用途**

列出任务当前已知的 artifact，帮助用户决定下一步去看日志、图表还是报告。

**参数**

- 必需：`<task_id>`

**成功输出示例**

```text
Artifacts for task_20260531_160210_3b20ef
[log] stdout.log
[log] stderr.log
[table] metrics/normalized_metrics.csv
[figure] figures/accuracy_curve.png
[report] reports/report-fragment.md
```

**失败输出示例**

```text
Error: no manifest was found for task 'task_20260531_160210_3b20ef'.
```

**会读取哪些文件**

- `manifest.json`
- `.lab-sidecar/index.sqlite`

**会写入哪些文件**

不会。

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

必须。

## `labsidecar open <task_id>`

**用途**

打开任务 artifact 目录；如果当前环境没有可用桌面文件管理器，则打印绝对路径。

**参数**

- 必需：`<task_id>`

**成功输出示例**

```text
Opened task directory:
C:\code\Lab-Sidecar\.lab-sidecar\tasks\task_20260531_160210_3b20ef
```

**失败输出示例**

```text
Error: task directory does not exist for 'task_20260531_160210_3b20ef'.
```

**会读取哪些文件**

- `manifest.json`

**会写入哪些文件**

不会。

**是否会修改用户原始文件**

不会。

**Phase 1 是否必须实现**

不是。建议在 Phase 2 之后作为便利命令实现。
