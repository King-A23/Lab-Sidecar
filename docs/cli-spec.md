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
Status: completed
Exit code: 0
Started: 2026-05-31T15:30:44+08:00
Finished: 2026-05-31T15:41:12+08:00
Artifacts: 5
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
