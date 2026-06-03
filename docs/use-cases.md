# Lab-Sidecar 用例清单

本文件只收录 Phase 1/2 真正要面对的工作流，不写抽象愿景。每个用例都按后续开发、手工测试和回归测试可直接复用的粒度描述。

## 用例 1：课程实验训练脚本

**背景**

机器学习课程要求提交一次图像分类实验。学生需要运行 `train.py`，保留训练日志、最佳验证集准确率、配置参数和一张可直接放进实验报告的训练曲线。

**输入文件**

- `train.py`
- `configs/cnn_baseline.yaml`
- `data/fashion-mnist/`
- `requirements.txt`

**运行命令**

```bash
labsidecar run "python train.py --config configs/cnn_baseline.yaml --seed 42 --output runs/cnn_seed42"
```

**当前手工流程**

1. 在终端直接运行训练命令。
2. 盯着终端等待 30-90 分钟，偶尔手动截屏日志。
3. 训练结束后从 stdout 里翻找 best accuracy。
4. 打开 `runs/cnn_seed42/metrics.csv` 或 Notebook 手动画图。
5. 手工把图和结论复制到课程实验报告。

**痛点**

- 训练日志很长，真正有价值的信息只有少量指标和最终结果。
- 容易忘记本次到底用了哪个配置文件、哪个 seed。
- 失败时常只剩一个终端窗口里的报错，无法复查。
- 不同同学画出来的图风格不一致，报告质量不稳定。

**期望 Lab-Sidecar 输出的 artifacts**

- `manifest.json`
- `stdout.log`
- `stderr.log`
- `metrics/metrics.csv`
- `figures/val_accuracy_curve.png`
- `figures/val_accuracy_curve.svg`
- `reports/report-fragment.md`
- `reproduce/command.txt`
- `reproduce/env.json`

**不希望进入主 Agent 上下文的内容**

- 每个 epoch 的完整训练日志。
- 框架 warning、下载进度、显存分配细节。
- 中间 checkpoint 文件名和路径。
- 数据集扫描输出。

**V1 是否必须支持**

必须支持。这是 `run -> collect -> figures -> report` 最核心的单任务闭环。

**验收标准**

- 可以把命令作为一个任务提交并拿到 `task_id`。
- 训练成功后，`manifest.json` 能记录命令、工作目录、时间戳和退出码。
- `collect` 能从 `metrics.csv` 识别 `epoch`、`val_accuracy`。
- `figures` 能生成至少一张单实验训练曲线。
- `report` 生成的 Markdown 中必须引用真实指标，不能虚构数值。

## 用例 2：算法性能对比实验

**背景**

数据结构或算法课程中，学生需要比较不同算法在不同输入规模下的性能，例如快速排序、归并排序和堆排序的运行时间与内存占用。

**输入文件**

- `bench.py`
- `configs/benchmark.yaml`
- `results/benchmark.json`
- `README.md`

**运行命令**

```bash
labsidecar run "python bench.py --config configs/benchmark.yaml --output results/benchmark"
```

**当前手工流程**

1. 反复运行 benchmark 脚本，手工修改输入规模或 seed。
2. 把每次结果复制到 Excel。
3. 手工计算平均运行时间和标准差。
4. 在 Excel 或 Notebook 里另画柱状图和折线图。
5. 手工总结“哪个算法更快、在哪个规模下开始反超”。

**痛点**

- 多次运行结果分散在多个 JSON/CSV 文件里，不易统一管理。
- 单位容易混乱，例如毫秒和秒混用。
- 统计均值和误差条时容易出错。
- 最终报告常只留下截图，没有保留复现实验条件。

**期望 Lab-Sidecar 输出的 artifacts**

- `manifest.json`
- `raw/source_refs.json`
- `metrics/final_metrics.csv`
- `figures/runtime_comparison.png`
- `figures/runtime_by_size.svg`
- `reports/benchmark-summary.md`
- `reproduce/command.txt`

**不希望进入主 Agent 上下文的内容**

- 每一次重复运行的原始 timing 明细。
- 大段 JSON 原文。
- 进度条和 warmup 输出。
- 与最终结论无关的系统信息。

**V1 是否必须支持**

必须支持。算法 benchmark 是非深度学习实验的重要场景，能验证 Sidecar 不是只服务训练脚本。

**验收标准**

- 能导入或运行至少 3 个算法、2 个输入规模、3 个 seed 的结果。
- `collect` 能识别 `algorithm`、`input_size`、`seed`、`runtime_ms`。
- `figures` 能生成可直接用于报告的柱状图或对比曲线。
- 输出必须保留单位信息，不能把不同单位画在同一坐标轴上。

## 用例 3：CSV / JSON 数据分析报告

**背景**

数据分析课程或课程项目中，学生已经用脚本或 Notebook 生成了 `metrics.csv` 和 `summary.json`，现在需要整理成报告图表和结论，但不希望整个 Notebook 历史或原始数据进入主工作流。

**输入文件**

- `data/student_sleep.csv`
- `analysis/metrics.csv`
- `analysis/summary.json`
- `analysis/schema.json`

**运行命令**

```bash
labsidecar ingest ./analysis
```

**当前手工流程**

1. 在 Jupyter 里清洗数据并导出图表。
2. 手工把关键列复制到另一个 CSV。
3. 截图 Notebook 图表。
4. 根据 `summary.json` 自己写报告摘要。
5. 后续改一次数据就再走一遍。

**痛点**

- Notebook 单元格执行历史很脏，不适合直接复用。
- 图表来源不清晰，后续很难确认对应的是哪份 CSV。
- 报告里的结论和源文件经常脱节。
- 导入已有结果目录时，很容易误改原始分析文件。

**期望 Lab-Sidecar 输出的 artifacts**

- `manifest.json`
- `raw/source_refs.json`
- `metrics/normalized_metrics.csv`
- `figures/distribution.png`
- `figures/comparison.svg`
- `reports/data-report-fragment.md`
- `raw/source_refs.json`

**不希望进入主 Agent 上下文的内容**

- 原始 CSV 的逐行数据。
- Notebook cell 输出和临时变量。
- pandas warning、JSON dump 全文。
- 与最终分析无关的清洗中间文件。

**V1 是否必须支持**

必须支持。`ingest` 场景能证明 Lab-Sidecar 不要求所有结果都由自身启动产生。

**验收标准**

- `ingest` 不修改 `./analysis` 目录下的原始文件。
- `collect` 能把 CSV/JSON 中的关键字段规范化到 `metrics/` 下。
- `report` 生成的摘要必须能回指源文件路径。
- `artifacts` 能清楚列出图表、表格和报告片段。

## 用例 4：论文复现实验

**背景**

科研训练或毕业设计中，学生需要复现论文基线并和论文表格对齐。通常要跑多 seed、多配置，还要记录依赖版本、Git commit 和失败原因。

**输入文件**

- `scripts/run_reproduce_suite.py`
- `configs/gcn_reproduce.yaml`
- `paper_table.md`
- `requirements-lock.txt`

**运行命令**

```bash
labsidecar run "python scripts/run_reproduce_suite.py --config configs/gcn_reproduce.yaml --seeds 1,2,3 --output runs/gcn_suite"
```

**当前手工流程**

1. 克隆论文仓库并调整配置。
2. 分别运行多个 seed。
3. 手工记下每次的最终指标。
4. 再和论文表格逐项对比。
5. 如果某个 seed 失败，就从终端历史里找错误信息。

**痛点**

- 复现实验时间长，失败成本高。
- 不记录 commit、Python 版本和依赖时，后续几乎无法复查。
- 多 seed 统计和论文对照表经常靠手工维护。
- 很多失败是环境问题，但手工记录不完整。

**期望 Lab-Sidecar 输出的 artifacts**

- `manifest.json`
- `stdout.log`
- `stderr.log`
- `metrics/final_metrics.csv`
- `figures/multiseed_mean_std.png`
- `reports/reproduction-note.md`
- `reproduce/command.txt`
- `reproduce/env.json`
- `reproduce/git.json`

**不希望进入主 Agent 上下文的内容**

- 多轮安装依赖输出。
- CUDA / 驱动 warning。
- 每个 seed 的完整训练过程。
- 大型 checkpoint 文件名。

**V1 是否必须支持**

必须支持。论文复现是 Sidecar 与“普通脚本记录器”拉开差异的高价值场景。

**验收标准**

- 能保留命令、工作目录、Git commit、退出码。
- 失败时必须保留 stderr 和可复现信息。
- 成功时能输出多 seed 的均值/方差图或表。
- 报告片段里必须区分“论文原始结果”和“本地复现实验结果”。

## 用例 5：需要生成报告或 PPT 素材的课程项目

**背景**

课程项目组每周要汇报进展。成员已经有训练结果、消融结果和最终指标，但需要快速整理出统一风格的图表和简洁结论，供报告和 PPT 直接使用。

**输入文件**

- `examples/project-presentation-pack/weekly_metrics.csv`
- `examples/project-presentation-pack/ablation.json`
- `examples/project-presentation-pack/final_metrics.csv`
- `examples/project-presentation-pack/project_goal.md`

**运行命令**

```bash
labsidecar ingest ./examples/project-presentation-pack
```

**当前手工流程**

1. 组员把截图和 CSV 丢到聊天群。
2. 负责人手工挑图、改标题、统一颜色。
3. 再把关键结论浓缩成几条汇报 bullet。
4. 下一周数据更新后重复一次。

**痛点**

- 图表风格不统一，PPT 看起来像拼接品。
- 很难确认哪一张图对应哪一版结果。
- 课程项目不需要复杂自动排版，但非常需要稳定的素材产出。
- 若把所有原始结果和群聊讨论都送进主 Agent，上下文会迅速失控。

**期望 Lab-Sidecar 输出的 artifacts**

- `manifest.json`
- `metrics/final_metrics.csv`
- `figures/figure-pack/`
- `figures/ablation_table.png`
- `figures/ablation_table.svg`
- `reports/project-summary.md`
- `reports/presentation-bullets.md`
- `raw/source_refs.json`

**不希望进入主 Agent 上下文的内容**

- 原始结果目录中的所有旧版本文件。
- 每周重复实验的完整日志。
- 群聊截图和无结构会议记录。
- 大量临时导出的中间图片。

**V1 是否必须支持**

必须支持“素材层”能力，但不要求 V1 直接输出 PPTX。V1 的边界是图表、表格、Markdown 摘要和复现信息。

**验收标准**

- `figures` 生成的 PNG 和 SVG 能直接用于报告或 PPT。
- `report` 至少输出一个摘要片段和一份展示用 bullet 列表。
- `artifacts` 能明确列出哪些文件适合写报告、哪些适合做汇报。
- 不生成 PPTX 也能完成课程项目汇报素材准备。
