# Phase 4.1 真实样例视觉验收记录

日期：2026-06-04 11:18:09 +08:00

验收范围：Phase 4.1 静态 PPTX。按 `docs/real-sample-visual-acceptance-checklist.md` 保守验收真实或高仿真样例，不引入 Web UI、FastAPI、MCP、AI 润色、动画、视频或大范围重构。

临时验收工作区：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance`

## 仓库状态

验收前 `git status --short`：

```text
 M PRODUCT_ITERATION_PLAN.md
 M README.md
 M lab_sidecar/cli/app.py
 M lab_sidecar/slides/service.py
 M tests/test_cli_smoke.py
?? docs/real-sample-visual-acceptance-checklist.md
```

说明：上述改动为本轮验收前已存在的 Phase 4.1 slides 收敛相关改动和新增 checklist。本轮不回退、不覆盖这些改动；除本记录和状态文档外，不主动修改实现。

## 执行命令

```powershell
py -3 -m pytest

# 临时工作区初始化与样例复制
py -3 -m lab_sidecar.cli.app init

# run -> collect -> figures -> report -> slides 链路验证
py -3 -m lab_sidecar.cli.app run "<wrapper calling examples/simple-success/train.py and writing metrics.csv into current task dir>" --name "simple success run-chain acceptance"
py -3 -m lab_sidecar.cli.app collect task_20260604_110751_857021
py -3 -m lab_sidecar.cli.app figures task_20260604_110751_857021
py -3 -m lab_sidecar.cli.app report task_20260604_110751_857021
py -3 -m lab_sidecar.cli.app slides task_20260604_110751_857021

# 课程项目汇报 zh-project 验收样例
py -3 -m lab_sidecar.cli.app ingest examples/project-presentation-pack --name "project presentation pack acceptance"
py -3 -m lab_sidecar.cli.app collect task_20260604_110453_87c786
py -3 -m lab_sidecar.cli.app figures task_20260604_110453_87c786
py -3 -m lab_sidecar.cli.app report task_20260604_110453_87c786
py -3 -m lab_sidecar.cli.app slides task_20260604_110453_87c786 --template zh-project

# 多结果对比样例
py -3 -m lab_sidecar.cli.app ingest examples/csv-comparison --name "csv comparison acceptance"
py -3 -m lab_sidecar.cli.app collect task_20260604_111250_0a84c0
py -3 -m lab_sidecar.cli.app figures task_20260604_111250_0a84c0
py -3 -m lab_sidecar.cli.app report task_20260604_111250_0a84c0
py -3 -m lab_sidecar.cli.app slides task_20260604_111250_0a84c0

# 失败诊断样例
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-failure/fail.py" --name "simple failure diagnostic acceptance"
py -3 -m lab_sidecar.cli.app slides task_20260604_111308_336c55
```

渲染命令：

```powershell
& "C:\Program Files\LibreOffice\program\soffice.com" --headless --convert-to pdf --outdir <render_dir> <presentation-draft.pptx>
pdftoppm -jpeg -r 150 <presentation-draft.pdf> <render_dir>\slide
```

验证结果：

- `py -3 -m pytest`：56 passed。
- LibreOffice / Poppler：4 个 PPTX 均成功渲染为 PDF 和 JPG。LibreOffice 输出 `Could not find platform independent libraries <prefix>` 环境提示，但 PDF/JPG 已生成，未阻断验收。

## 样例验收

### project-presentation-pack

- 输入目录：`examples/project-presentation-pack`
- task_id：`task_20260604_110453_87c786`
- 模板：`zh-project`
- task 目录：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_110453_87c786`
- PPTX：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_110453_87c786\slides\presentation-draft.pptx`
- slides-summary.json：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_110453_87c786\slides\slides-summary.json`
- 渲染目录：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\rendered-project-zh`

自动检查：

- 页数：PPTX 实际 7 页，summary `slide_count=7`，符合 `zh-project` 7-9 页目标。
- `qa_checks.slide_count.passed`：true
- `qa_checks.empty_slide_check.passed`：true
- `qa_checks.title_check.passed`：true
- `qa_checks.artifact_duplicate_check.passed`：true
- `qa_checks.table_overflow_guard.passed`：true
- `qa_checks.caption_overflow_guard.passed`：true

视觉检查：

- 无空白页；每页标题可读。
- 中文内容在 LibreOffice 渲染图中未乱码。
- 表格 6x8 预览未越界，隐藏列、截断单元格在 summary 中有记录。
- 图表未裁切，caption 已截断且未溢出。
- footer/页码未与主体内容重叠。
- 关键对比使用 `variant` 和 `accuracy`，higher-is-better 推断合理；best、baseline、delta 均可追溯到 `metrics/normalized_metrics.csv`。
- 结论页来自 report、manifest、metrics，没有发现 artifact 中不存在的数值结论。

结论：通过，blocking 为 0。

### simple-success run 链路

- 输入：`examples/simple-success/train.py`
- task_id：`task_20260604_110751_857021`
- 模板：`zh-summary`
- task 目录：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_110751_857021`
- PPTX：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_110751_857021\slides\presentation-draft.pptx`
- slides-summary.json：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_110751_857021\slides\slides-summary.json`
- 渲染目录：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\rendered-simple-run-chain`

自动检查：

- 页数：PPTX 实际 7 页，summary `slide_count=7`，符合普通摘要 5-8 页目标。
- 全部 `qa_checks` 为 true。

视觉检查：

- 无空白页；标题、指标摘要、表格、图表、结果摘要和复现信息可读。
- 两张训练曲线未裁切，caption 未溢出。
- 表格未越界，长命令已截断。

备注：首次直接运行 `py -3 examples/simple-success/train.py --output metrics.csv` 后，`collect` 未扫描到工作区根目录的 `metrics.csv`；本次 run 链路用包装命令把输出写入当前 task 目录顶层，以覆盖现有产品规则下的 `run -> collect -> figures -> report -> slides`。该产品体验差异记录为 follow-up，不作为本 PPTX 视觉 blocking。

结论：通过，blocking 为 0。

### csv-comparison

- 输入目录：`examples/csv-comparison`
- task_id：`task_20260604_111250_0a84c0`
- 模板：`zh-summary`
- task 目录：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_111250_0a84c0`
- PPTX：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_111250_0a84c0\slides\presentation-draft.pptx`
- slides-summary.json：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_111250_0a84c0\slides\slides-summary.json`
- 渲染目录：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\rendered-csv-comparison`

自动检查：

- 页数：PPTX 实际 7 页，summary `slide_count=7`，符合普通摘要 5-8 页目标。
- 全部 `qa_checks` 为 true。

视觉检查：

- 无空白页；标题、指标摘要、表格、图表、结果摘要和复现信息可读。
- 多 run 对比图的图例可读，未遮挡主体曲线。
- 表格和 footer 未重叠。

结论：通过，blocking 为 0。

### simple-failure

- 输入命令：`py -3 examples/simple-failure/fail.py`
- task_id：`task_20260604_111308_336c55`
- 模板：`zh-summary` 失败诊断 deck
- task 目录：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_111308_336c55`
- PPTX：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_111308_336c55\slides\presentation-draft.pptx`
- slides-summary.json：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\.lab-sidecar\tasks\task_20260604_111308_336c55\slides\slides-summary.json`
- 渲染目录：`C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase4-acceptance\rendered-simple-failure`

自动检查：

- 页数：PPTX 实际 5 页，summary `slide_count=5`，符合普通摘要 5-8 页目标。
- 全部 `qa_checks` 为 true。

视觉检查：

- deck 明确展示 `failed` 状态和 exit code。
- 失败诊断页展示 failure summary，不误写为成功总结。
- 日志尾部页可读，stderr 信息未越界。
- 复现信息可读。

结论：通过，blocking 为 0。

## 问题分级

blocking：

- 无。

follow-up：

- `project-presentation-pack` 图表页中存在 `(missing)` 模型标签，原因是合并后的 normalized metrics 同时包含 ablation、final metrics 和 weekly metrics，不是所有行都有 `model`。后续可优先选择 `variant` 或过滤缺失分组，以提升图表解释性。
- `project-presentation-pack` 关键对比页的 best 卡片会截断 `augmentation_and_scheduler` 为短标签；当前表格保留完整值，不阻断，但后续可优化卡片文本换行或字号。
- `run "py -3 examples/simple-success/train.py --output metrics.csv"` 默认把输出写到 workspace 根目录，当前 `collect` 不扫描 run 工作目录根目录，导致首次直接链路无法收集。后续可考虑将 run 产生的声明式输出、工作目录候选文件或命令输出路径纳入安全扫描策略。
- 计划文档中 Phase 4 验收写“至少一个真实样例”，checklist 写“至少 3 个样例”。本次实际覆盖 4 个样例，但后续文档可统一口径。

out-of-scope：

- Web UI、FastAPI、MCP、AI 润色、动画、GIF、MP4、Manim、Remotion。
- PowerPoint 原生动画和复杂演示交互。
- Phase 6 的 MCP/主 Agent 调用上下文隔离验证。

## 阶段判断

本轮 Phase 4.1 静态 PPTX 真实/高仿真样例视觉验收通过。`project-presentation-pack` 的 `zh-project` deck 已完成重点验收，另补充成功训练、多结果对比和失败诊断样例；所有 PPTX 均可由 LibreOffice 渲染为 PDF/JPG，人工视觉检查无 blocking，`slides-summary.json` 的 QA checks 与观察一致。

建议：可以将 Phase 4.1 静态 PPTX 视为产品级收敛，并允许进入 Phase 4.2 的评估阶段。进入 Phase 4.2 前仍应保持保守边界：只评估下一步，不直接引入动画、视频、MCP、Web UI 或 AI-dependent workflow。
