# Lab-Sidecar 产品迭代计划书

## 1. 项目定位

**Lab-Sidecar** 是一个面向实验场景的本地 AI agent sidecar。

它的主要调用者是正在本地 workspace 中工作的主 AI agent；人类用户是实验目标、取舍和最终验收的决策者，通常是计算机相关专业学生、科研新手和个人开发者。它的目标不是做一个泛泛的 AI 聊天助手，也不是重新发明一个多 Agent 框架，而是专注解决本地实验委派、artifact 隔离、场景级摘要和可复现交付中反复遇到的实际问题：

- 长实验运行时需要持续看日志、记录参数、处理失败。
- 实验结束后需要从 CSV、JSON、log、TensorBoard 等结果中提取指标。
- 报告和论文需要规范、清晰、可复现的图表。
- PPT 展示需要快速整理图表、结论和简易流程动画。
- 主 AI 对话或主工作流不应该被海量日志、报错重试、完整指标表和中间文件污染。

一句话定位：

> A local-first AI agent sidecar for experiment scenarios, producing bounded scenario summaries and reproducible artifacts from local runs or result files.

中文定位：

> 一个本地优先的实验场景 AI agent sidecar，把长实验、结果导入、指标抽取、场景摘要、自动图表和报告素材生成放到隔离的 artifact 工作流中，最后只向主上下文返回 bounded summary 和可追溯产物路径。

项目优先级：

1. **实用性优先**：先解决自己平时实验、报告和科研任务中的真实痛点。
2. **质量优先**：以足以产品化甚至商业化的标准设计可靠性、可复现性和用户体验。
3. **技术创新优先**：保留 Delegation Layer、上下文隔离、Artifact 协议、异步任务系统等核心创新。
4. **商业化次要**：不以快速挣钱为第一目标，但产品形态和工程质量应具备商业化潜力。

## 2. 核心理念

### 2.1 不是通用 Agent，而是实验 Sidecar

Lab-Sidecar 不试图替代用户思考，也不试图自动完成所有科研任务。

它更像一个一直在旁边工作的实验助理：

- 用户在前台写代码、看论文、写报告。
- Lab-Sidecar 在后台跑实验、整理日志、抽取指标、生成图表。
- 用户最终看到的是结构化结果和可复现产物，而不是混乱的执行轨迹。

### 2.2 Context Quarantine

长实验、网页检索、日志分析和图表生成会产生大量中间信息。如果这些信息全部进入主 AI 对话，会降低主模型的判断质量，也会让用户难以追踪重点。

Lab-Sidecar 的基本原则是：

- 原始日志、报错重试、中间分析过程保存在后台任务中。
- 主界面和主 Agent 默认只接收摘要、图表、表格、结论和证据链接。
- 用户需要时可以展开完整日志，但系统不会主动把脏上下文倒灌到主对话。

### 2.3 Artifact-first Protocol

每个任务的最终价值不是一段聊天回复，而是一组可复用 artifact：

- 图表：PNG、SVG、HTML。
- 表格：CSV、Markdown table。
- 报告片段：Markdown。
- 演示素材：PPTX、GIF、MP4。
- 复现信息：命令、参数、环境、Git commit、随机种子、输入文件 hash。

所有自动生成的结论都必须能追溯到具体 artifact。

### 2.4 Local-first

V1 默认本地运行，不依赖云端服务。

原因：

- 学生和个人研究者的数据、课程作业、实验环境通常都在本机。
- 本地优先更容易做可复现、低成本和隐私保护。
- 后续可以扩展到远程服务器、实验室集群或云端 runner，但不作为第一阶段目标。

## 3. 目标用户与典型场景

### 3.1 目标用户

优先用户：

- 计算机科学与技术、人工智能、软件工程、数据科学等专业本科生。
- 参与科研训练、课程设计、毕业设计或论文复现的学生。
- 需要频繁写实验报告和 PPT 的个人开发者。
- 小型科研/课程项目组。

暂不优先：

- 大型企业 Agent 平台团队。
- 完整 MLOps 团队。
- 需要复杂权限、审计和多租户的组织级客户。

### 3.2 高频场景

#### 场景 A：长实验托管

用户提交命令：

```bash
python train.py --config configs/cnn_exp.yaml --seed 42
```

Lab-Sidecar 后台执行并记录：

- 命令和工作目录。
- stdout / stderr。
- 开始时间、结束时间、退出码。
- Python 版本、依赖版本、Git commit。
- 输出文件路径。
- 失败摘要或成功摘要。

#### 场景 B：实验结果自动图表

用户已有多个实验结果：

```text
results/baseline.csv
results/model_a.csv
results/model_b.csv
```

Lab-Sidecar 自动识别：

- epoch / step。
- loss / accuracy / F1。
- seed。
- model_name。

然后生成：

- 训练曲线。
- 多模型对比图。
- 多 seed 均值方差图。
- 最终结果表。

#### 场景 C：课程实验报告素材

实验完成后，Lab-Sidecar 生成：

- `report-fragment.md`
- `figures/accuracy_curve.svg`
- `tables/final_metrics.csv`
- `reproduce.md`

用户可以直接把内容整理进实验报告。

#### 场景 D：PPT 与简易动画

在后续阶段，Lab-Sidecar 根据实验结果生成：

- 5-8 页 PPT 草稿。
- 算法流程图。
- 简单 GIF/MP4 动画，例如排序过程、状态机转移、神经网络训练流程。

## 4. 产品边界

### 4.1 V1 应该做

- 提供 CLI-first 的本地使用方式。
- 后台运行本地实验命令。
- 保存任务状态和日志。
- 自动识别常见结果文件。
- 抽取基础指标。
- 生成常见科研图表。
- 输出 Markdown 报告片段。
- 保存复现信息。

### 4.2 V1 不应该做

- 不把 Web UI 作为第一可用形态。
- 不做复杂多用户系统。
- 不做企业级权限和审计。
- 不做完整 AutoML。
- 不做大而全 Notebook 平台。
- 不做复杂 PowerPoint 原生动画。
- 不做强依赖云端的闭源服务。
- 不做通用 Agent 编排框架。

### 4.3 后续可以做

- MCP Server 接入 Claude Desktop、Codex、Cursor 等 AI 工具。
- 远程服务器 runner。
- PPT 草稿生成。
- Manim / HTML Canvas 动画生成。
- 实验组管理。
- 数据集版本记录。
- 图表质量自动检查。
- 基于历史任务的智能建议。

## 5. 落地优先技术路线

本项目的技术路线应遵循“先闭环、再平台化、最后智能化”的顺序。

第一阶段不要急着做完整 Web 平台、复杂 Agent 或 MCP 接入。最稳妥的路线是先做一个可以在本机真实使用的 CLI-first 垂直切片：

```text
运行实验命令
  -> 保存日志和任务元数据
  -> 识别结果文件
  -> 抽取指标
  -> 生成图表
  -> 生成 Markdown 报告片段
```

只要这个闭环可靠，后续增加 Web UI、FastAPI、MCP Server、PPT 和动画都只是外层能力扩展；如果这个闭环不可靠，过早做界面和 Agent 接入会放大复杂度。

### 5.1 技术路线原则

#### 原则一：CLI-first，而不是 UI-first

V1 的第一可用形态应是命令行工具。

原因：

- 学生和开发者本来就在终端里跑实验。
- CLI 更容易测试、复现和自动化。
- 避免一开始就同时处理后端、前端、任务系统和交互设计。
- 后续 Web UI 和 MCP Server 可以复用同一套核心库。

推荐第一批命令：

```bash
labsidecar init
labsidecar run "python train.py --config configs/exp.yaml"
labsidecar status <task_id>
labsidecar logs <task_id>
labsidecar cancel <task_id>
labsidecar ingest ./existing-results
labsidecar collect <task_id>
labsidecar figures <task_id>
labsidecar report <task_id>
labsidecar artifacts <task_id>
labsidecar open <task_id>
```

#### 原则二：File-first，SQLite second

任务结果应优先落到本地文件系统，而不是只存在数据库里。

推荐做法：

- 每个任务一个独立目录。
- 每个任务目录里都有 `manifest.json`。
- 原始日志、指标、图表、报告都作为普通文件保存。
- SQLite 只做索引、查询和状态加速，不作为唯一事实来源。

这样即使数据库损坏，用户仍然能直接打开 artifact 目录查看实验结果。

#### 原则三：V1 不强依赖 AI

AI 是增强能力，不是基础能力。

V1 应先通过确定性规则完成：

- 任务记录。
- 日志保存。
- CSV / JSON 解析。
- 常见指标识别。
- 标准图表生成。
- Markdown 模板报告。

AI 可以作为可选增强，用于日志摘要、失败解释、报告润色和图表建议。这样项目即使没有 API key、没有网络，也能正常工作。

#### 原则四：先支持显式配置，再追求自动智能

自动识别指标和图表类型很有价值，但不能一开始就完全依赖“猜”。

V1 同时支持：

- 自动扫描常见列名。
- 用户通过简单 YAML/JSON 配置指定指标、分组和图表。

推荐优先让“显式配置一定能成功”，再逐步增强自动推断。

#### 原则五：核心库与外壳分离

从第一天开始就把核心能力写成可复用 Python package，而不是写死在 CLI、Web 或 MCP 中。

建议分层：

- `core`：任务、artifact、协议、配置。
- `runner`：实验命令执行与状态管理。
- `collectors`：CSV、JSON、log 解析。
- `figures`：图表配置与渲染。
- `reports`：Markdown 报告生成。
- `cli`：命令行入口。
- `api`：后续 FastAPI 入口。
- `mcp`：后续 MCP Server 入口。

## 6. 迭代路线

### Phase 0：准备与地基设计

目标：在正式编码前，把真实工作流、数据协议、质量标准和扩展方向定义清楚。

建议周期：1-2 周。

#### 6.1 交付物

- `PRODUCT_ITERATION_PLAN.md`
- `docs/use-cases.md`
- `docs/artifact-protocol.md`
- `docs/chart-guidelines.md`
- `docs/architecture.md`
- `docs/cli-spec.md`
- `examples/` 中的真实或模拟实验样例。
  - `examples/simple-success/`
  - `examples/simple-failure/`
  - `examples/csv-comparison/`
  - `examples/algorithm-benchmark/`
  - `examples/project-presentation-pack/`

#### 6.2 准备工作

收集至少 5 个真实任务样例：

1. 一个课程实验训练脚本。
2. 一个算法性能对比实验。
3. 一个 CSV 数据分析报告。
4. 一个论文复现实验。
5. 一个需要 PPT 展示的课程项目。

每个样例记录：

- 输入是什么。
- 实验命令是什么。
- 输出文件有哪些。
- 用户最终需要什么图表。
- 用户最终需要什么报告文字。
- 哪些中间过程不应该进入主对话。

同时冻结 V1 技术决策：

- Python 3.11+。
- 包管理优先使用 `uv`，无法使用时退回 `pip`。
- CLI 使用 Typer。
- 图表优先使用 pandas + matplotlib。
- 任务文件协议使用 JSON。
- 配置文件优先使用 YAML，内部数据结构使用 Pydantic。
- SQLite 作为索引和查询层，不作为唯一事实来源。

#### 6.3 阶段验收标准

- 至少 5 个真实或高仿真用例被写清楚，并能映射到 artifact 协议。
- 至少 4 个最小样例可用于后续 Phase 1/2 smoke test。
- 图表质量标准足够明确，可以判断图表是否合格。
- V1 的功能边界清楚，不会滑向通用大平台。
- `labsidecar run -> figures -> report` 的最小垂直切片已经能在设计层面走通。

### Phase 1：CLI Experiment Runner

目标：先做可靠的本地 CLI 实验任务系统，不依赖 Web UI。

建议周期：2-3 周。

#### 6.4 核心功能

- 创建实验任务。
- 运行 shell / Python 命令。
- 保存 stdout / stderr。
- 保存任务状态。
- 支持查看完整日志。
- 支持中断或取消运行中的任务。
- 每个任务拥有独立 artifact 目录。
- 允许导入已有实验目录，不强制所有实验都由 Lab-Sidecar 启动。

任务状态：

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`

#### 6.5 推荐技术栈

- CLI: Typer。
- Task runner: `subprocess.Popen` 起步，后续再封装 asyncio。
- Storage: 本地 artifact 目录 + SQLite 索引。
- Config: YAML + Pydantic。
- Artifact storage: 本地文件目录。

第一版不做 Web UI。等 CLI 闭环稳定后，再添加 FastAPI 和前端。

#### 6.6 核心 CLI 草案

```bash
labsidecar init
labsidecar run "python train.py --config configs/exp.yaml"
labsidecar status <task_id>
labsidecar logs <task_id> --tail 100
labsidecar cancel <task_id>
labsidecar ingest ./existing-results
labsidecar artifacts <task_id>
```

#### 6.7 阶段验收标准

- 可以稳定运行一个超过 30 分钟的实验任务。
- 实验失败时能保存 stderr、退出码和失败摘要。
- 关闭终端后，任务记录仍可恢复查看。
- 每个任务都有独立 artifact 目录。
- 不自动覆盖用户文件。
- 不启动任何 Web 服务也能完成一次实验记录。

### Phase 2：Metrics Extraction & Auto Figures

目标：形成“实验结果 -> 指标 -> 图表 -> 报告素材”的核心闭环。

建议周期：3-4 周。

#### 6.8 核心功能

- 自动扫描任务目录下的 CSV、JSON、log 文件。
- 识别常见指标。
- 生成标准科研图表。
- 导出 PNG、SVG 和 Markdown 引用片段。
- 支持手动修正图表配置。
- 保存图表生成配置，保证可复现。
- 优先支持 CSV / JSON，log 解析只做简单正则和常见训练日志。

#### 6.9 首批支持指标

- `loss`
- `accuracy`
- `precision`
- `recall`
- `f1`
- `latency`
- `memory`
- `epoch`
- `step`
- `seed`
- `model`
- `method`

#### 6.10 首批支持图表

- 单实验训练曲线。
- 多实验对比曲线。
- 最终指标柱状图。
- 多 seed 均值方差图。
- 消融实验结果表。

暂不优先：

- 复杂交互式图表。
- 自动论文级排版。
- 任意日志格式的智能解析。

#### 6.11 图表质量标准

默认图表必须满足：

- 标题明确。
- 坐标轴名称完整。
- 单位明确。
- 图例可读。
- 配色适合报告和 PPT。
- 支持中文和英文标题。
- 导出分辨率足够用于报告。
- 相同输入和配置可以重复生成相同结果。

#### 6.12 阶段验收标准

- 给定 3 组真实实验 CSV，可以自动生成可用对比图。
- 给定一个训练 log，可以抽取 loss / accuracy 曲线。
- 每张图都能追溯到来源文件和生成配置。
- 图表可直接插入课程实验报告。
- 同一个 `figure.yaml` 重复运行可以生成一致图表。

### Phase 3：Report Artifact Generator

目标：把实验结果整理成报告可用材料，而不是只停留在图表工具。

建议周期：2-3 周。

#### 6.13 核心功能

- 自动生成实验摘要 Markdown。
- 输出实验设置、结果分析、失败原因、关键图表和复现命令。
- 支持一键生成 `report-fragment.md`。
- 支持将多个任务合并成一次实验组总结。
- 支持中文和英文报告模板，默认中文。
- V1 报告采用模板生成，AI 润色作为可选增强。

#### 6.14 报告结构

- 实验目的。
- 实验环境。
- 方法与参数。
- 结果图表。
- 结果分析。
- 问题与改进。
- 复现信息。

#### 6.15 质量原则

- 不虚构实验结果。
- 无法判断时明确标注“未自动推断”。
- 所有数值结论必须来自 artifact。
- 所有图表必须包含来源。
- 报告片段应该便于用户继续修改。

#### 6.16 阶段验收标准

- 生成的 Markdown 能直接复制进课程实验报告。
- 所有结论都能追溯到具体 artifact。
- 失败实验能生成失败分析，而不是错误地写成成功总结。

### Phase 4：Presentation & Simple Animation Extension

目标：把实验报告材料转成演示素材。

建议周期：3-5 周。

#### 6.17 核心功能

- 根据实验摘要生成 PPT 草稿。
- 自动插入图表、表格和关键结论。
- 生成简单流程动画素材。
- 支持算法过程可视化模板。

#### 6.18 推荐策略

不要第一版就追求复杂 PowerPoint 原生动画。

更稳妥的路线：

1. 先生成静态 PPTX。
2. 再用 Manim、Remotion 或 HTML Canvas 生成 GIF / MP4。
3. 最后把动画作为媒体插入 PPT。

#### 6.19 首批动画模板

- 排序过程。
- 搜索过程。
- 状态机转移。
- 数据处理 pipeline。
- 神经网络训练流程。
- 实验流程图。

#### 6.20 阶段验收标准

- 能从一个实验组自动生成 5-8 页 PPT 草稿。
- PPT 中图表清晰、文字不过载。
- 简单算法动画可以作为视频插入 PPT。
- 输出文件可以被用户继续编辑。
- 静态 PPTX 收敛后，按 `docs/real-sample-visual-acceptance-checklist.md` 完成至少一个真实样例视觉验收。

Phase 4.1 静态 PPTX 真实样例视觉验收已于 2026-06-04 完成，覆盖 `examples/project-presentation-pack/`、`examples/simple-success/`、`examples/csv-comparison/` 和 `examples/simple-failure/`，blocking 为 0。验收记录见 `docs/phase-4-real-sample-visual-acceptance.md`。

Phase 4.2 于 2026-06-04 完成最小产品可用性收敛：动画 artifact 暂缓，优先修复直接 `run -> collect -> figures -> report -> slides` 链路。`collect` 现在可在 run 工作目录顶层识别任务开始后生成的 CSV/JSON，并记录来源 `run_working_dir`；不递归扫描 workspace 或 `.lab-sidecar`。验收记录见 `docs/phase-4-2-direct-run-collect-acceptance.md`，blocking 为 0。

### Phase 5：MCP Sidecar Integration

目标：把 Lab-Sidecar 接入主流 AI 工具，让它成为真正的 Delegation Layer。

建议周期：3-4 周。

#### 6.21 核心功能

提供 MCP Server，并暴露工具：

- `run_experiment`
- `inspect_results`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`

#### 6.22 MCP 设计原则

- MCP 是接入层，不是 V1 核心。
- 主 Agent 只接收摘要和 artifact 列表，不接收完整日志。
- 长任务立即返回 `task_id`，后续查询状态。
- 危险命令必须有权限确认机制。
- 默认只允许在用户选择的 workspace 内运行命令。

#### 6.23 阶段验收标准

- Claude Desktop、Codex 或其他 MCP 客户端可以调用 Lab-Sidecar。
- 长任务不会污染主对话上下文。
- 主 Agent 能根据 artifact 生成最终回答或报告。

Phase 5 于 2026-06-04 完成最小 MCP-facing 工具适配层：`lab_sidecar.mcp` 暴露 `run_experiment`、`inspect_results`、`make_figures`、`generate_report_fragment`、`generate_slides`，并复用既有 runner/collectors/figures/reports/slides service。默认响应只返回摘要和 artifact 列表，不返回完整 stdout/stderr、metrics rows、报告正文或 PPT 内容；`run_experiment` 增加 workspace 与危险命令安全闸门。初始阶段验收采用本地工具层等价 smoke，未宣称真实 stdio MCP 客户端验收完成。Public alpha readiness 于 2026-06-05 增加 `.[mcp]` optional extra，pin `mcp==1.27.2`，并完成真实 stdio MCP client/server smoke；smoke 使用 `run_experiment(background=True)` 返回 `task_id`，再轮询 `inspect_results` 并调用后续 4 个工具。验收记录见 `docs/phase-5-mcp-sidecar-acceptance.md` 和 `docs/public-alpha-readiness-acceptance.md`。

### Phase 6：真实产品效果检验与安全可用性收敛

目标：在完整链路打通后，用真实或高仿真的课程/实验项目检验 Lab-Sidecar 是否已经达到“安全、可用、可复现、值得长期使用”的产品状态。

建议周期：1-2 周。

#### 6.24 核心功能与验证范围

围绕真实使用闭环做验收，不再扩大功能面：

- 使用至少 3 个真实或高仿真项目跑通 `run -> collect -> figures -> report -> slides`。
- 至少覆盖成功实验、失败实验、多结果对比、课程项目汇报四类场景。
- 验证 CLI 直用体验，也验证 MCP/主 Agent 调用时的上下文隔离效果。
- 检查所有生成物是否能被用户直接打开、编辑、复现和追溯。
- 记录每次验收的输入、命令、生成目录、关键 artifact、人工观察结论和问题清单。
- PPTX 视觉验收沿用 `docs/real-sample-visual-acceptance-checklist.md`，不临时放宽页数、溢出和可追溯标准。

#### 6.25 安全与可靠性检查

Phase 6 的重点不是增加新能力，而是确认产品默认行为足够保守：

- 默认只在用户指定 workspace 内读写。
- 不自动删除、覆盖或移动用户原始文件。
- 对潜在危险命令给出明确提示或阻断策略。
- 失败任务必须保留 stderr、退出码、运行命令和可诊断摘要。
- 生成报告和 PPT 时，所有数值、图表和结论都必须能回溯到 artifact。
- 对空数据、坏 CSV、坏 JSON、缺失图表、缺失字体、PPT 渲染失败等情况给出可理解错误。
- 长任务、中断任务和重复运行不会破坏已有任务目录或索引。

#### 6.26 真实效果验收标准

- 一个新用户可以在 10 分钟内完成本地初始化和第一个样例运行。
- 至少 3 个验收项目完整产出指标、图表、报告片段和 PPT 草稿。
- 生成的 Markdown、图表和 PPT 可以直接用于课程实验汇报的一轮人工修改。
- 主 Agent 通过摘要和 artifact 列表即可完成说明，不需要读取完整日志。
- 所有高风险行为都有保守默认值，不会静默破坏用户数据。
- `pytest`、CLI smoke、真实样例验收和人工视觉检查均通过。
- 剩余问题被分为 blocking / follow-up / out-of-scope，blocking 项清零后才视为产品可用。

## 7. 核心数据协议

### 7.1 Task Record

```json
{
  "task_id": "exp_20260601_001",
  "name": "cnn_baseline_seed_42",
  "status": "completed",
  "created_at": "2026-06-01T10:00:00+08:00",
  "started_at": "2026-06-01T10:01:00+08:00",
  "finished_at": "2026-06-01T10:35:00+08:00",
  "working_dir": "./examples/cnn-exp",
  "command": "python train.py --config configs/exp1.yaml --seed 42",
  "exit_code": 0
}
```

### 7.2 Artifact Result

```json
{
  "task_id": "exp_20260601_001",
  "status": "completed",
  "summary": "实验完成，best accuracy 为 91.3%。",
  "artifacts": [
    {
      "type": "figure",
      "path": "figures/accuracy_curve.svg",
      "source": "metrics.csv",
      "description": "训练准确率曲线"
    },
    {
      "type": "table",
      "path": "tables/final_metrics.csv",
      "source": "results.json",
      "description": "最终指标表"
    },
    {
      "type": "report",
      "path": "report-fragment.md",
      "description": "实验报告片段"
    }
  ],
  "provenance": {
    "command": "python train.py --config configs/exp1.yaml --seed 42",
    "working_dir": "./examples/cnn-exp",
    "git_commit": "optional",
    "python_version": "3.12.0",
    "started_at": "2026-06-01T10:01:00+08:00",
    "finished_at": "2026-06-01T10:35:00+08:00",
    "exit_code": 0
  }
}
```

### 7.3 Figure Config

```json
{
  "figure_id": "accuracy_curve",
  "title": "Validation Accuracy over Epochs",
  "chart_type": "line",
  "x": "epoch",
  "y": "accuracy",
  "group_by": "model",
  "source_files": [
    "baseline.csv",
    "model_a.csv"
  ],
  "output": [
    "figures/accuracy_curve.png",
    "figures/accuracy_curve.svg"
  ]
}
```

### 7.4 本地目录协议

推荐每个 workspace 下维护一个 `.lab-sidecar/` 目录：

```text
.lab-sidecar/
  config.yaml
  index.sqlite
  tasks/
    exp_20260601_001/
      manifest.json
      stdout.log
      stderr.log
      raw/
      metrics/
        metrics.csv
        metrics.json
      figures/
        accuracy_curve.png
        accuracy_curve.svg
        figure.yaml
      reports/
        report-fragment.md
      reproduce.md
```

落地原则：

- `manifest.json` 是单个任务的最小可恢复记录。
- `index.sqlite` 用于快速查询任务列表和状态，但可以从 `manifest.json` 重建。
- `raw/` 保存原始输入或链接，不保存用户未授权复制的大文件。
- `metrics/`、`figures/`、`reports/` 只保存生成产物。
- 所有路径优先保存相对 workspace 的路径，便于迁移。

## 8. 架构建议

### 8.1 V1 架构

```text
User
  |
  v
CLI: labsidecar
  |
  v
Python Core Library
  |
  +--> Task Runner
  |      |
  |      +--> subprocess.Popen
  |
  +--> Artifact Manager
  |      |
  |      +--> .lab-sidecar/tasks/<task_id>/
  |
  +--> SQLite Index
  |
  +--> Collectors
  |      |
  |      +--> CSV / JSON / simple log parser
  |
  +--> Figure Generator
  |      |
  |      +--> pandas + matplotlib
  |
  +--> Report Generator
```

后续扩展层：

```text
FastAPI / Web UI / MCP Server
  |
  v
Same Python Core Library
```

架构要求：

- CLI、API、MCP 不各自实现业务逻辑，只调用同一套核心库。
- 核心库不依赖 Web 框架。
- 图表和报告生成可以独立于实验运行使用，方便导入已有结果。

### 8.2 目录结构建议

```text
Lab-Sidecar/
  PRODUCT_ITERATION_PLAN.md
  pyproject.toml
  docs/
    use-cases.md
    artifact-protocol.md
    chart-guidelines.md
    architecture.md
    cli-spec.md
  examples/
    cnn-exp/
    csv-analysis/
    algorithm-benchmark/
  lab_sidecar/
    core/
    runner/
    collectors/
    figures/
    reports/
    cli/
    api/
    mcp/
  tests/
    fixtures/
```

### 8.3 技术选型默认值

- Python: 3.11+。
- Package / environment: `uv` 优先，`pip` 兼容。
- CLI: Typer。
- Config / schema: Pydantic + YAML。
- Storage: 文件系统 artifact + SQLite 索引。
- Data processing: pandas。
- Figures: Matplotlib 起步，后续按需加入 Altair / Plotly。
- Report generation: Markdown first。
- Backend: FastAPI，Phase 1 不引入。
- PPT generation: `python-pptx` 或 `pptxgenjs`，后续阶段决定。
- Animation: Manim 优先作为实验性扩展。
- MCP: 后续作为独立 server 模块加入。

## 9. 质量标准

### 9.1 产品质量

- 用户可以在 10 分钟内理解核心工作流。
- 默认输出能直接用于课程实验报告。
- 失败时给出明确原因和下一步建议。
- 不要求用户理解多 Agent 或 MCP 才能使用。
- 不把 AI 生成内容包装成确定事实。

### 9.2 工程质量

- 每个后台任务可追踪。
- 每个 artifact 可追溯。
- 每个图表可复现。
- 原始数据和生成数据分离。
- 不自动删除用户数据。
- 不自动覆盖用户文件。
- 任务失败不影响其他任务。

### 9.3 图表质量

- 图表有标题、坐标轴、图例。
- 支持中英文。
- 默认风格适合报告和 PPT。
- 同一实验组内配色一致。
- 支持 PNG 和 SVG。
- 图表配置可保存、可修改、可复现。

### 9.4 AI 使用原则

AI 可以用于：

- 日志摘要。
- 失败原因解释。
- 报告片段草稿。
- 图表选择建议。
- PPT 结构建议。

AI 不应该：

- 虚构实验数值。
- 覆盖用户原始数据。
- 默认执行高风险命令。
- 把不确定推断写成确定结论。

## 10. 测试计划

### 10.1 任务系统测试

- 成功运行一个 Python 脚本，状态应为 `completed`。
- 运行一个报错脚本，状态应为 `failed`，并保存 stderr。
- 运行长任务后重新打开终端，任务记录仍可通过 CLI 查看。
- 取消运行中任务后状态应为 `cancelled`。
- 多个任务并行时互不影响。
- 删除 SQLite 后，可以从 `manifest.json` 重建基础任务索引。

### 10.2 指标抽取测试

- CSV 中含 `epoch,loss,accuracy` 时生成训练曲线。
- 多 seed CSV 可以生成均值和方差图。
- JSON 结果文件可以抽取最终指标。
- 无法识别指标时返回清晰提示。
- 混合中英文列名时给出映射建议。

### 10.3 图表生成测试

- PNG 和 SVG 均可导出。
- 图表有标题、坐标轴、图例。
- 相同输入重复生成结果一致。
- 中文标题不乱码。
- 空数据、缺失列、非数值列都有明确错误信息。

### 10.4 报告生成测试

- Markdown 中包含实验设置、结果、图表引用和复现命令。
- 报告结论不能包含 artifact 中不存在的数值。
- 失败实验生成失败分析，而不是成功总结。
- 多任务合并报告能区分不同实验配置。

### 10.5 MCP 集成测试

- MCP 客户端可以提交任务并获得 `task_id`。
- 主 Agent 查询任务时只获得摘要和 artifact 列表。
- 完整日志不会默认返回给主 Agent。
- 长任务不会阻塞主 Agent 对话。

## 11. 风险与应对

### 11.1 范围膨胀

风险：

项目容易从实验工具膨胀成通用 Agent 平台。

应对：

V1 只围绕“实验任务、指标、图表、报告片段”闭环，不做通用聊天、不做复杂编排。

### 11.2 图表质量不稳定

风险：

自动生成图表如果质量低，会直接影响用户信任。

应对：

先支持少量高频图表类型，把默认样式、标题、坐标轴和导出质量做好。

### 11.3 AI 生成内容不可靠

风险：

报告摘要可能编造结果或过度解释。

应对：

所有数值必须来自 artifact；无法确认的结论必须标注不确定。

### 11.4 本地命令安全

风险：

后台执行命令可能误删文件或执行危险操作。

应对：

默认限制 workspace；高风险命令需要确认；不自动执行删除或覆盖操作。

### 11.5 过早做 MCP

风险：

在核心实验工作流未稳定前接入 MCP，会导致架构复杂但价值不清晰。

应对：

MCP 放在 Phase 5。前期只保证内部任务协议和 artifact 协议足够干净。

### 11.6 过早做 Web UI / API

风险：

前端、接口、状态同步和后台任务管理会同时引入大量工程复杂度，导致核心实验闭环迟迟不可用。

应对：

先做 CLI-first 垂直切片。只有当 `run -> collect -> figures -> report` 在真实实验中稳定后，再添加 FastAPI 和 Web UI。

## 12. 商业化可能性

商业化不是近期第一目标，但可以作为质量标准。

潜在商业形态：

- 免费开源本地版。
- 付费高级模板包，例如科研图表模板、PPT 模板、课程报告模板。
- 托管同步服务，用于跨设备管理实验 artifact。
- 团队版，用于课程项目组或实验室小组共享实验记录。
- 教育场景版本，用于老师管理学生实验提交和可复现记录。

不建议早期商业化：

- 不建议一开始做企业销售。
- 不建议一开始做云端闭源平台。
- 不建议一开始做复杂权限系统。

## 13. 近期行动清单

### 第 1 周

- 整理 5 个真实实验/报告/PPT 场景。
- 写 `docs/use-cases.md`。
- 初步定义 artifact 协议。
- 写 `docs/cli-spec.md`。
- 冻结 V1 技术栈和目录协议。

### 第 2 周

- 写 `docs/artifact-protocol.md`。
- 写 `docs/chart-guidelines.md`。
- 准备至少 4 个最小 examples。
- 准备最小实验 fixture：成功脚本、失败脚本、CSV 结果、JSON 结果。

### 第 3-4 周

- 搭建 Python package 和 Typer CLI。
- 实现 `init`、`run`、`status`、`logs`、`cancel`、`artifacts`。
- 实现 artifact 目录管理和 `manifest.json`。
- 实现 SQLite 索引，但保证可从文件重建。

### 第 5-6 周

- 实现 CSV/JSON 指标抽取。
- 实现第一批图表生成。
- 生成 Markdown 报告片段。
- 用真实课程实验测试闭环。
- 暂不做 Web UI，除非 CLI 闭环已经稳定。

## 14. 最终判断

Lab-Sidecar 是一个适合本科生独立推进、同时又具备技术创新和产品潜力的方向。

它把原本抽象的 Delegation Layer 收敛到一个高频、真实、可自用的场景中：

- 长实验后台化。
- 脏上下文隔离。
- 指标和图表自动化。
- 报告和演示 artifact 化。
- 后续通过 MCP 接入 AI 工具。

这个方向的关键不是做得大，而是把一个学生和个人研究者每天都会遇到的工作流做得足够可靠、足够清晰、足够可复现。

如果 V1 能做到“我跑完实验后，Lab-Sidecar 自动帮我整理日志、生成图表、写出可追溯的报告片段”，它就已经是一个真正有价值的产品。

## 15. 开源后路线

本文件保留为 V1 与 public alpha 的历史产品设计背景。

项目开源后的阶段性迭代计划见 `docs/post-open-source-product-roadmap.md`。后续产品推进以该路线图为准，重点从“把基础闭环做出来”转向：

- 任务导航与跨任务对比
- 可交付结果包
- 混乱真实结果集适配
- Agent-native bounded delegation
- provenance 与 claim traceability
