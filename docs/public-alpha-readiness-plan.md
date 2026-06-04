# Public Alpha Readiness Plan

## 目标

把当前“功能跑通”的 Lab-Sidecar 收敛成“别人可以稳定试用”的 public alpha。

本计划不继续扩功能面，不做 Web UI、FastAPI、AI 润色、动画、远程 runner 或大范围重构。优先低范围扩张、低依赖、低风险，先硬化已经打通的本地产品链路。

## 优先级 1：整理发布基线

目标：把当前 dirty worktree 整理成可审查、可回退、可发布的提交基线。

工作项：

- 将当前 dirty worktree 拆成清晰提交。
- 建议提交粒度：Phase 4.1、Phase 4.2、Phase 5、Phase 6。
- 补充 release notes 或 changelog 草稿。
- 确认 README 不夸大 MCP、CLI 安全或 Phase 6 验收范围。

验收：

- `git status` 清晰。
- `py -3 -m pytest` 通过。
- 每个提交的范围和验收记录能对应起来。

## 优先级 2：MCP SDK 真实验证

目标：把当前 MCP-facing tool adapter 从本地等价 smoke 推进到真实 stdio MCP client 验证。

工作项：

- 增加 `.[mcp]` optional extra。
- pin MCP SDK 版本。
- 跑真实 stdio MCP client smoke。
- 写 host 配置示例。
- 保持 MCP 是薄接入层，不重写 runner、collector、figures、reports 或 slides 逻辑。

验收：

- 真实 MCP client 能调用 5 个工具：
  - `run_experiment`
  - `inspect_results`
  - `make_figures`
  - `generate_report_fragment`
  - `generate_slides`
- 默认不返回完整 stdout、stderr、metrics rows、report body 或 PPT 内容。
- 长任务返回 `task_id`，主 Agent 只需要摘要和 artifact 列表即可说明结果。

## 优先级 3：安全模型澄清

目标：让用户和开发者清楚理解 CLI 与 MCP-facing 工具的不同安全边界。

工作项：

- 明确 CLI `run` 是用户显式本地命令执行路径。
- 明确 MCP-facing `run_experiment` 有 workspace 与危险命令安全闸门。
- README 和 docs 不夸大“全局安全阻断”。
- 可选后续：为 CLI 增加危险命令提示或确认策略。

验收：

- README、Phase 5/6 验收记录和后续 release notes 都明确区分 CLI trust model 与 MCP-facing safety gate。
- MCP-facing destructive command、workspace 外 cwd、workspace 外敏感输出路径仍有测试覆盖。
- 不声称 CLI `run` 自动阻断所有高风险命令。

## 优先级 4：Artifact 协议对齐

目标：让文档协议与当前实现一致，并为未来媒体 artifact 留出清晰但未实现的边界。

工作项：

- 将 `presentation` artifact 类型写入 `docs/artifact-protocol.md`。
- 为未来 `media` / `animation` 先设计协议。
- 不在本阶段实现动画、GIF、MP4、Manim、Remotion 或 PowerPoint 原生动画。
- 明确 MCP 响应只返回 artifact 路径和摘要，不返回 artifact body。

验收：

- `docs/artifact-protocol.md` 包含当前已实现的 presentation artifact 约定。
- 未来 media/animation 被标为设计预留或 deferred，不被写成已实现能力。
- artifact provenance 能从 manifest、summary 和 task 目录追溯。

## 优先级 5：坏输入与真实样例硬化

目标：提高 public alpha 在真实用户试用时的错误可理解性和恢复能力。

工作项：

- 增加坏 CSV、坏 JSON、空 CSV、缺列、缺字体、PPT 渲染失败样例。
- 增加 1 个更真实的课程项目 fixture。
- 覆盖失败诊断、重复运行、manifest 不重复登记、artifact 可追溯性。
- 不自动删除、覆盖或移动用户源文件。

验收：

- 错误提示可理解。
- 失败任务保留 stderr、exit code、运行命令和诊断摘要。
- 重复运行不会破坏已有 manifest 或重复 artifact。
- 新增 fixture 能跑通 `run/ingest -> collect -> figures -> report -> slides` 中适用的路径。

## 测试计划

文档创建后运行：

```powershell
py -3 -m pytest
git status --short
```

检查项：

- `docs/public-alpha-readiness-plan.md` 存在。
- 文档不声称已完成真实 MCP client 验收。
- 文档明确 CLI 与 MCP 安全边界区别。
- 本次只新增计划文档，不执行计划内容。

## 假设

- 默认文件名为 `docs/public-alpha-readiness-plan.md`。
- 本次只新增计划文档，不修改 README。
- 本次不修改实现代码。
- “节能型规划”理解为：低范围扩张、低依赖、低风险、优先硬化已有能力。
