# 开源后产品迭代路线图

Date: 2026-06-17

## 1. 目标

Lab-Sidecar 已经完成 public alpha。下一阶段的重点不再是“把功能做出来”，而是让陌生用户在真实实验目录里更快地：

- 找到任务
- 看懂差异
- 打包交付
- 在 Agent 场景里安全委派
- 保持结果可追溯

一句话目标：

> 把 Lab-Sidecar 从“能跑的本地实验 sidecar”推进成“能交付的本地 artifact 编译层”。

## 2. 不变的边界

后续迭代继续坚持：

- local-first
- file-first
- CLI-first
- artifact-first
- AI optional
- bounded delegation

明确不做：

- Web UI
- FastAPI hosted service
- remote runner
- cloud sync
- 通用多 Agent 框架
- 默认 AI 分析
- 把日志/数据整包上传云端

## 3. 阶段总览

| 阶段 | 主题 | 主要产出 | 完成标准 | 建议周期 |
| --- | --- | --- | --- | --- |
| Stage 1 | 任务导航与对比 | `list` / `open` / `status` / `logs` / `summarize` 的输出增强，跨任务筛选与 `compare` | 用户能在一个忙碌 workspace 里快速定位、比较任务，而不需要先翻 raw logs | 1-2 周 |
| Stage 2 | 可交付结果包 | `package` / `bundle` / `export` 类能力，稳定的交付目录或 zip | 另一个人拿到包后，不看上下文也能理解实验结论和复现入口 | 2-3 周 |
| Stage 3 | 混乱结果集适配 | 加深 explicit collect config，更多 CSV/JSON/log 变体，seed/model/method 聚合 | 三种真实或半真实结果目录可以稳定归一化，且错误信息可行动 | 3-4 周 |
| Stage 4 | Agent-native 委派 | bounded preview、更稳的 worker/audit/cancel、插件体验 | 主 Agent 可把长任务交给 Lab-Sidecar，而不被原始日志污染 | 2-4 周 |
| Stage 5 | 溯源与可信度 | git/dependency/hash provenance，claim tracing，report/slides traceability | 任一关键数值都能追溯到来源 artifact 或 source file | 1-2 周 |

每个阶段都要独立验收，避免“顺手改一堆但不知道产品是否变好”。阶段开始前记录：

```bash
git status --short
git diff --stat
python -m pytest -q
```

阶段结束时至少记录：

- 改动文件
- 命令行验收流程
- task id 和临时 workspace
- 生成 artifacts
- 测试结果
- blocking / follow-up / out-of-scope
- 下一阶段建议

建议每个阶段都新增一份 acceptance 文档，例如：

```text
docs/post-open-source-stage-1-acceptance.md
docs/post-open-source-stage-2-acceptance.md
```

Stage-specific implementation plans:

- `docs/post-open-source-stage-1-plan.md`
- `docs/post-open-source-stage-2-plan.md`
- `docs/post-open-source-stage-3-plan.md`
- `docs/post-open-source-stage-4-plan.md`

## 4. Stage 1: 任务导航与对比

### 目标

让 workspace 从“很多 task 记录”变成“可以直接扫读的任务面板”。

这一阶段最直接改善日常使用体验。用户不应该为了找一个任务先手动进 `.lab-sidecar/tasks/` 里翻目录。

### 交付物

- `list` 支持过滤、排序、状态查看、最近任务优先
- `open` 继续保持轻量，但输出更清楚的 artifact 目录和后续命令
- `status`、`logs`、`artifacts` 的输出更像导航页，而不是纯状态打印
- 新增 `compare <task_id...>` 或等价对比命令
- 新增 `summarize <task_id>` 或等价任务摘要命令

### 建议切片

1. 增强 `list`
   - 支持 `--status`
   - 支持 `--limit`
   - 显示 name、status、created/finished、artifact count
   - 最近任务稳定排序
2. 增强 `status`
   - 显示关键 artifact 路径
   - 显示下一步命令
   - 对 failed / cancelled 给出诊断入口
3. 新增 `summarize`
   - 不读取完整日志
   - 只输出 task summary、关键 metrics、figures、report/slides 路径
4. 新增 `compare`
   - 初版只比较 normalized metrics 中的共同字段
   - 支持 2-5 个 task
   - 输出 Markdown-friendly 表格

### 重点场景

- 课程实验同时跑了多个 seed
- benchmark 同时对比多个算法
- 一个 workspace 里堆了很多成功/失败任务

### 验收标准

- 用户可以只凭 task 列表找到目标任务
- 用户可以比较 2-5 个任务的关键指标和产物
- 用户不需要先打开完整 stdout 才知道下一步该做什么
- `compare` 对缺失 metrics 的任务给出清晰提示，而不是静默跳过

## 5. Stage 2: 可交付结果包

### 目标

让单个任务或任务组能直接交给别人，而不是只留在本机工作区里。

这是产品从“我自己能用”到“我能交付给别人”的关键一步。

### 交付物

- `package <task_id>`：生成可分享的结果包
- `bundle`：把 manifest、reproduce 信息、metrics、figures、report、slides summary 组织成固定目录
- 可选 `zip` 导出，方便传给同学、导师或另一个 Agent
- 包内保留 redaction / 脱敏标记，避免把不该外发的内容误打包

### 建议包结构

```text
lab-sidecar-package-<task_id>/
  README.md
  manifest.json
  reproduce/
  metrics/
  figures/
  reports/
  slides/
  summaries/
    artifact-index.json
    package-summary.json
    redaction-notes.md
```

初版不需要复制所有 raw inputs。默认只打包生成产物、manifest、reproduce 信息和必要 summary。完整 stdout/stderr 默认不进包，除非用户显式指定。

### 建议切片

1. `package <task_id> --output <dir>`
2. `package <task_id> --zip`
3. package summary 和 artifact index
4. redaction notes
5. 对 missing artifact / failed task 的打包策略

### 重点场景

- 课程实验提交前整理
- 论文复现实验复查
- 多文件结果交给队友接手

### 验收标准

- 结果包打开后，使用者可以看到任务是什么、命令是什么、产物在哪里
- 不需要回到原始工作区就能理解这次实验
- 结果包里没有主动泄露完整日志或无关原始文件
- 失败任务也能打包为诊断包

## 6. Stage 3: 混乱结果集适配

### 目标

让 Lab-Sidecar 适应真实实验目录，而不是只适合 demo 目录。

这一阶段是产品实用性的硬仗。重点不是“支持所有格式”，而是让常见脏输入有明确路径：能解析就解析，不能解析就告诉用户怎么配置。

### 交付物

- 加深已有 explicit collect config，覆盖更多 source 选择、字段映射、单位声明、分组规则
- 更稳的多文件 ingest
- 对 nested / variant / multi-seed 结果的归一化支持
- 简单 log 解析与失败诊断增强
- 对缺失字段、单位冲突、列名歧义给出可操作错误

### collect config 草案

```yaml
sources:
  - path: results/**/*.csv
    type: csv
fields:
  step: epoch
  metric: val_accuracy
  group: model
  seed: seed
units:
  runtime: ms
outputs:
  normalized_metrics: metrics/normalized_metrics.csv
```

### 建议切片

1. 扩展 source glob 和 include/exclude
2. 字段映射与 alias
3. 单位声明与单位冲突诊断
4. seed/model/method 聚合
5. 最小 log regex collector
6. 与 figure spec 对齐

### 重点场景

- benchmark 结果散落在多个目录
- 同一个实验有多个 seed、多个模型、多个版本
- 原始结果不是标准 CSV，或者 CSV / JSON 混在一起

### 验收标准

- 三个不同风格的真实结果目录可以被稳定归一化
- 明确错误优先于“猜测成功”
- 图表和报告仍然保持 deterministic
- config 失败时生成 `collection-summary.json`，说明失败原因和可修正字段

## 7. Stage 4: Agent-native 委派

### 目标

让 Lab-Sidecar 成为主 Agent 的“脏活隔离层”，而不是另一个复杂平台。

这一阶段只加深 sidecar 能力，不扩大成通用多 Agent 编排。

### 交付物

- 更完整的 bounded preview
- 更稳的 worker proposal / validation / adoption 流程
- cancellation 和 recovery 更可靠
- 插件响应继续保持短、稳、可继续推理
- AI 不可用时仍然有清晰 fallback

### 建议切片

1. preview 支持 CSV rows、Markdown excerpt、figure metadata、slides summary
2. cancellation 覆盖 V1 和 V2 路径
3. worker audit 文件稳定化
4. provider policy 更明确
5. 插件 skill 文档补充委派判断标准
6. stdio MCP smoke 覆盖 V1/V2 常用路径

### 重点场景

- 主 Agent 只需要知道 task_id、摘要、产物路径和风险提示
- 长任务运行时，主对话不被 stdout/stderr 冲掉
- 需要在本地 sandbox 内探测、比较、再决定是否采用

### 验收标准

- 主 Agent 可以委派任务并保持上下文干净
- 默认返回不包含完整日志、完整表格或 artifact body
- 人类用户仍然可以在 CLI 里完整复查
- stdio MCP smoke 和本地 host integration 测试都通过

## 8. Stage 5: 溯源与可信度

### 目标

把“看起来对”变成“可以追溯为什么对”。

这是把开源 alpha 打磨成可信工具的收口阶段。

### 交付物

- git commit / status / dependency snapshot
- source file hash 和 input hash
- report / slides 的数值结论 trace back
- 更严格的 claim guard，避免无来源推断

### 建议切片

1. source refs 增加 hash
2. reproduce env 增加 Git 和关键依赖版本
3. report summary 记录数值 claim source
4. slides summary 记录每页来源 artifact
5. 增加 no-invention 回归测试

### 重点场景

- 报告里引用了某个指标值
- slides 里对比了多个实验结果
- 用户想知道某张图到底来自哪个源文件

### 验收标准

- 关键结论都能追到 source artifact 或 collected row
- 生成物可以解释“来自哪里、由什么生成、在什么环境里生成”
- 失败或不确定时，系统宁可保守也不乱补结论
- 删除 `index.sqlite` 后，核心 provenance 仍能从 task-local 文件复查

## 9. 推荐执行顺序

建议顺序是：

1. Stage 1 先做，直接提升可用性和可发现性
2. Stage 2 紧跟，增强分享和交付价值
3. Stage 3 再做，扩大真实世界适配面
4. Stage 4 在前面两层稳定后继续加深
5. Stage 5 最后收口，强化信任与复现

其中 Stage 1 和 Stage 2 的价值最高，因为它们最直接影响“用户愿不愿意继续用”。

## 10. 每阶段通用验证

除非阶段明确只改文档，每个实现阶段至少运行：

```bash
git diff --check
python -m pytest -q
python -m pytest tests/test_cli_smoke.py -q
```

如果涉及 MCP / V2 / 插件：

```bash
python -m pytest tests/test_mcp_tools.py -q
python -m pytest tests/test_v2_host_integration.py tests/test_v2_worker_invocation.py -q
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-post-open-source-mcp-smoke
```

如果涉及 package / export：

```bash
find . -path '*/.lab-sidecar/*' -print | head -n 20
```

这个检查用于确认没有把本地任务输出误提交到仓库。

## 11. 里程碑判断

这一轮迭代完成时，Lab-Sidecar 应该达到下面的状态：

- 新用户能看懂它是做什么的
- 新用户能快速找到自己的任务和产物
- 结果包可以直接交给别人
- Agent 调用时不会把主上下文搞脏
- 每个重要数字都能追溯到来源

## 12. 说明

`PRODUCT_ITERATION_PLAN.md` 保留为原始 V1 / public alpha 的历史设计背景。  
后续产品迭代以本文件为准。
