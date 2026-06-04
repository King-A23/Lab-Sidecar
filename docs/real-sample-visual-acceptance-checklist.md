# 真实样例视觉验收清单

本清单用于 Phase 4.1 静态 PPTX 收敛后的保守验收，也作为 Phase 6 真实产品效果检验的一部分。目标是确认真实或高仿真样例生成的报告素材和 PPT 草稿已经达到“可打开、可阅读、可修改、可追溯”的产品可用状态。

本清单不是新功能需求，不要求像素级自动化断言，也不要求引入 Web UI、AI 润色、动画、视频或 MCP。

## 1. 验收样例

至少选择 3 个样例，其中 `examples/project-presentation-pack/` 必须包含在内：

| 样例类型 | 建议来源 | 必须覆盖的风险 |
| --- | --- | --- |
| 课程项目汇报 | `examples/project-presentation-pack/` 或真实课程项目 | 中文标题、长路径、表格、关键对比、PPT 页数 |
| 成功训练实验 | `examples/simple-success/` 或真实训练输出 | 指标摘要、训练曲线、复现信息 |
| 多结果对比 | `examples/csv-comparison/` 或真实多 run 结果 | 多 CSV 合并、图例、表格列选择 |
| 失败诊断 | `examples/simple-failure/` 或真实失败日志 | stderr 截断、失败原因呈现、不可误写成成功 |

如果真实样例包含敏感路径、姓名、课程信息或数据集名称，验收记录中应脱敏，但本地 artifact 不应被静默修改。

## 2. 验收前置条件

- 工作区为用户明确指定的项目目录。
- 运行前记录 `git status --short`，确认不会覆盖无关改动。
- 使用当前 CLI 命令，不额外引入临时脚本作为产品路径的一部分。
- 清楚记录临时输出目录，避免污染用户源目录。
- 如需渲染 PPTX，优先使用本机已有 LibreOffice / PowerPoint / Poppler；工具缺失时记录为环境限制，而不是修改产品代码绕过。

## 3. 推荐验收命令

按样例实际情况调整命令，但最终应覆盖 `run -> collect -> figures -> report -> slides`：

```powershell
py -3 -m pytest
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-success/train.py --output metrics.csv"
py -3 -m lab_sidecar.cli.app collect <task_id>
py -3 -m lab_sidecar.cli.app figures <task_id>
py -3 -m lab_sidecar.cli.app report <task_id>
py -3 -m lab_sidecar.cli.app slides <task_id> --template zh-project
```

每个样例至少保留：

- `task_id`
- 原始命令
- task 目录
- `manifest.json`
- `metrics/collection-summary.json`，如存在
- `figures/figure-summary.json`，如存在
- `reports/report-fragment.md`，如存在
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

## 4. PPT 结构检查

对每个生成的 PPTX 检查：

- 文件可以被 PowerPoint、LibreOffice 或兼容工具打开。
- 文件可以另存或编辑，不是只读损坏文件。
- 页数符合模板目标：普通摘要 5-8 页，`zh-project` 7-9 页。
- 每页都有可读标题。
- 不存在明显空白页，除非该页是明确的诊断占位。
- 页脚、页码、caption、图表、表格不互相遮挡。
- 标题、正文、表格和图例没有明显溢出页面边界。
- 中文内容不乱码，英文字体和数字可读。
- 长命令、长路径、长 stderr、长 caption 已截断，完整内容可在 summary 中追溯。

## 5. 表格与图表检查

对包含 metrics 或 figures 的样例检查：

- 指标摘要中的数值和 `metrics` artifact 一致。
- 表格优先展示重要列，隐藏列记录在 `hidden_columns`。
- 数值列右对齐，文本/路径列不会挤压到不可读。
- 被截断的单元格在 `truncated_cells_count` 或相关字段中有记录。
- 图表标题、坐标轴、图例可读。
- 图表没有被拉伸变形、裁掉关键文字或遮住 caption。
- 多图页每页最多展示当前模板允许的图数，图与图之间有足够间距。
- caption 能说明图表来源；缺失字段显示 `未自动推断` 或等价占位，不虚构信息。

## 6. 关键对比与结论检查

对 `zh-project` 或项目汇报样例检查：

- 关键对比页只使用 metrics 中真实存在的 `variant`、`model`、`method`、`algorithm`、`source_file` 等字段。
- higher-is-better / lower-is-better 推断符合指标名称；无法确认时不强行下结论。
- baseline 无法识别时显示 `未自动推断`，不编造 delta。
- 结论页能回溯到 report、metrics、figures 或 manifest。
- 不出现 AI 式泛化结论、夸大结论或 artifact 中不存在的数值。

## 7. 失败与异常样例检查

对失败或取消任务检查：

- PPT 明确展示 failed / cancelled 状态。
- exit code、stderr 摘要、stdout/stderr tail 可读。
- 长日志被截断，完整日志仍保存在 task 目录。
- 失败任务不会生成成功口吻的结果总结。
- 缺失 metrics、figures 或 report 时，错误提示能说明缺什么、下一步做什么。

## 8. Summary 与 QA 检查

检查 `slides-summary.json`：

- `slide_count` 与 PPT 实际页数一致。
- `template`、`slides`、`source_artifacts`、`included_figures`、`included_metrics` 字段存在且合理。
- `qa_checks.slide_count.passed` 为 true。
- `qa_checks.empty_slide_check.passed` 为 true。
- `qa_checks.title_check.passed` 为 true。
- `qa_checks.artifact_duplicate_check.passed` 为 true。
- 对表格样例，`qa_checks.table_overflow_guard.passed` 为 true。
- 对长 caption 样例，`qa_checks.caption_overflow_guard.passed` 为 true。
- 重复运行 `slides` 后，manifest 中 `slides_presentation_draft_pptx` 和 `slides_summary_json` 不重复。

## 9. 人工视觉记录模板

每次验收用下面模板记录，建议保存到临时验收日志或后续专门的 Phase 6 记录文件：

```markdown
## 样例名称

- 日期：
- 验收人：
- 输入目录：
- task_id：
- 模板：
- 命令：
- PPTX：
- slides-summary.json：
- 渲染方式：PowerPoint / LibreOffice / PDF+JPG / 仅打开检查

### 自动检查

- pytest：
- CLI smoke：
- slides-summary qa_checks：

### 视觉检查

- 页数：
- 空白页：
- 标题可读：
- 中文字体：
- 表格溢出：
- 图表裁切：
- caption 溢出：
- footer/页码重叠：
- 关键对比是否可信：
- 结论是否可追溯：

### 问题分级

- blocking：
- follow-up：
- out-of-scope：

### 结论

- 通过 / 不通过：
- 备注：
```

## 10. 通过标准

一个样例只有同时满足以下条件，才算通过：

- CLI 链路无未解释失败。
- PPTX 可打开、可编辑、页数合理。
- 没有明显文字、表格、图表、caption、footer 重叠或越界。
- 所有数值和结论都能追溯到 artifact。
- `slides-summary.json` 的 QA checks 与人工观察一致。
- blocking 问题为 0。

全部真实样例验收通过后，Phase 4.1 静态 PPTX 才能视为完成产品级收敛；Phase 6 仍需继续覆盖端到端安全可用性。
