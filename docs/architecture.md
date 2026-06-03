# Lab-Sidecar Phase 1 架构说明

本文件描述 Phase 1 应该落地什么、为什么这样分层，以及后续如何在不推翻核心实现的前提下扩展。Phase 0 只写设计，不实现核心代码。

## 总体分层

```text
CLI (Typer)
  -> Python Core Library
       -> Runner
       -> Collectors
       -> Figures
       -> Reports
       -> Storage (Artifact files + SQLite index)
```

更具体地说：

```text
labsidecar CLI
  |
  +-- core.models / core.config / core.manifest
  |
  +-- runner
  |     +-- subprocess.Popen
  |     +-- status transitions
  |     +-- cancellation
  |
  +-- collectors
  |     +-- csv
  |     +-- json
  |     +-- simple log parsing
  |
  +-- figures
  |     +-- chart specs
  |     +-- matplotlib rendering
  |
  +-- reports
        +-- markdown templates
        +-- provenance-aware summaries
```

核心要求：CLI 只是薄外壳，业务逻辑都在 Core Library 内部。后续 API、Web UI、MCP 都只能复用这套核心库，而不是各自重写一遍。

## 为什么 Phase 1 不做 Web UI / FastAPI / MCP

原因很直接：

- 真实用户最先需要的是一个能在终端里跑起来的实验任务系统，而不是另一层壳。
- Web UI、FastAPI、MCP 会同时引入状态同步、进程管理、权限边界和交互设计复杂度。
- 只要 CLI + 核心库闭环不稳，外层界面越多，返工成本越高。

因此 Phase 1 的落地原则是：

- 不做 Web UI。
- 不做 FastAPI。
- 不做 MCP Server。
- 不做通用 Agent 编排框架。

先把这些事情做稳：

- `init`
- `run`
- `status`
- `logs`
- `cancel`
- `ingest`
- `artifacts`

`collect`、`figures`、`report` 预留模块边界，但可分阶段实现。

## 核心模块职责

### `core`

定义领域模型和协议：

- `TaskRecord`
- `ArtifactRecord`
- `LabConfig`
- `ManifestSchema`
- 路径解析与 workspace 规则

职责边界：不关心 CLI 解析，不直接启动进程，不直接画图。

### `runner`

负责本地任务执行和生命周期管理：

- 创建 `task_id`
- 创建任务目录
- 启动 `subprocess.Popen`
- 采集 stdout / stderr
- 更新 `manifest.json`
- 处理中止与状态流转

### `collectors`

负责从 CSV / JSON / 简单日志中提取结构化指标：

- 扫描候选结果文件
- 识别字段
- 标准化到 `metrics/`
- 保留来源路径

### `figures`

负责把规范化指标转为静态图表：

- 校验图表输入是否满足规范
- 使用固定样式生成 PNG / SVG
- 保存图表配置

### `reports`

负责 Markdown 报告片段生成：

- 引用真实 artifact
- 生成实验摘要、失败摘要和展示 bullet
- 不虚构结论

### `storage`

负责两类存储：

- 文件系统：真实产物与任务目录
- SQLite：任务和 artifact 的索引

这里必须坚持：SQLite 只做索引，不做唯一事实来源。

## 推荐目录结构

Phase 1 推荐的工程结构如下，注意这只是目标结构，不要求 Phase 0 现在就搭建：

```text
Lab-Sidecar/
  PRODUCT_ITERATION_PLAN.md
  docs/
  examples/
  lab_sidecar/
    cli/
      app.py
    core/
      config.py
      manifest.py
      models.py
      paths.py
    storage/
      artifact_store.py
      sqlite_index.py
    runner/
      service.py
      process.py
      cancel.py
    collectors/
      scan.py
      csv_collector.py
      json_collector.py
      log_collector.py
    figures/
      specs.py
      render.py
    reports/
      templates.py
      generate.py
  tests/
    fixtures/
    smoke/
```

不建议在 Phase 1 提前创建这些目录：

- `web/`
- `frontend/`
- `mcp_server/`
- `fastapi_app/`

除非 CLI 闭环已经稳定，否则这些目录只会制造错觉上的“平台感”。

## 依赖选择

### Python 3.11+

原因：

- 更好的类型系统和标准库体验。
- 足够稳定，适合本地 CLI 工具。

### Typer

原因：

- 适合快速构建可读 CLI。
- 参数声明清晰，方便后续补 `--help` 和测试。

### Pydantic

原因：

- 用于校验 `manifest.json`、配置文件和图表规范。
- 可以减少“字段猜错但静默继续”的隐患。

### YAML

原因：

- 用户显式配置实验字段、图表规格时更易读。
- 推荐 `PyYAML`，不必引入更重的配置系统。

### pandas

原因：

- 适合处理 CSV / JSON 表格结果。
- 对课程实验和基准对比足够通用。

### matplotlib

原因：

- 生成静态 PNG / SVG 成熟稳定。
- 适合报告和 PPT 素材，不依赖浏览器渲染。

### SQLite

原因：

- 标准库可用，部署成本低。
- 足够承担本地索引职责。

## 任务执行建议：先用 `subprocess.Popen`

Phase 1 不要过早上复杂任务框架。推荐：

- 用 `subprocess.Popen` 启动用户命令。
- 分别捕获 stdout / stderr。
- 在任务目录下持续写日志。
- 把 PID、启动时间、退出码等信息写回 `manifest.json`。

这样做的好处：

- 实现简单。
- 易于跨平台理解和调试。
- 足够支撑 `cancel`、`logs`、`status`。

暂不建议：

- 一开始就引入 asyncio 任务总线。
- 一开始就上 Celery、RQ、Redis。
- 一开始就做远程 runner。

## SQLite 只做索引，不做唯一事实来源

这一点必须明确：

- 任务目录里的 `manifest.json`、日志和 artifact 文件是真实记录。
- SQLite 只是让 `status`、`artifacts`、任务列表查询更快。
- 删除 `index.sqlite` 后，系统应该能从 `manifest.json` 扫描重建。

理由：

- 本地工具优先可恢复性，不优先“数据库优雅”。
- 学生用户出问题时，最直观的排障方式就是直接打开文件夹。

## 后续如何扩展到 FastAPI / Web UI / MCP

扩展顺序应是：

1. 先固定 Core Library 的服务接口。
2. 再给这些服务加 API 包装。
3. 最后根据需要做 UI 或 MCP。

建议扩展方式：

- FastAPI：把 `run/status/logs/artifacts` 封装成 HTTP 层，仍调用同一组 core service。
- Web UI：只消费 API 或直接调用 core service，不自行维护另一套任务语义。
- MCP：暴露 `run_experiment`、`inspect_artifacts` 之类工具，但仍以本地 artifact 协议为底层事实来源。

判断标准：

- 如果未来新增一层壳需要重新定义任务状态或 artifact 协议，说明当前核心分层失败。

## 主要风险和规避策略

### 风险 1：Windows / Linux 进程行为差异

规避：

- 先把进程创建、终止、路径解析封装在 `runner` 层，不让 CLI 直接碰系统细节。

### 风险 2：Collector 自动识别误判

规避：

- 先让显式 YAML 配置一定可用，再逐步增强自动推断。

### 风险 3：SQLite 与文件状态漂移

规避：

- 所有命令优先信任 `manifest.json`，必要时触发索引重建。

### 风险 4：图表输出质量不稳定

规避：

- 限制首批图表种类。
- 严格执行拒绝生成规则。
- 把默认标题、坐标轴和导出规范写死在实现里。

### 风险 5：范围膨胀

规避：

- 在 Phase 1 明确只做 CLI、本地任务和 artifact 协议。
- 不在核心模块里引入 AI、Web、MCP 依赖。

## Phase 1 最小闭环

在进入更高级功能之前，最小可运行闭环应是：

```text
labsidecar init
  -> labsidecar run "<command>"
  -> labsidecar status <task_id>
  -> labsidecar logs <task_id>
  -> labsidecar artifacts <task_id>
```

这是 Phase 1 的底线。只有这个闭环稳定后，再推进 `collect`、`figures` 和 `report`。
