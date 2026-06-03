# project-presentation-pack

课程项目汇报素材样例，用于验证已有结果目录导入后，能生成统一风格的报告和 PPT 素材。

## 文件说明

- `weekly_metrics.csv`：每周模型指标，适合生成趋势图
- `final_metrics.csv`：最终模型对比指标，适合生成最终结果表和柱状图
- `ablation.json`：消融实验结果，适合生成消融表格和汇报 bullet
- `project_goal.md`：项目目标和汇报背景

## 预期用途

未来在 Lab-Sidecar 中可执行：

```bash
labsidecar ingest ./examples/project-presentation-pack
labsidecar collect <task_id>
labsidecar figures <task_id>
labsidecar report <task_id>
labsidecar artifacts <task_id>
```

推荐至少生成：

- 一张 `val_accuracy` 周趋势图
- 一张最终模型指标对比图
- 一个消融实验表格图
- `reports/project-summary.md`
- `reports/presentation-bullets.md`

## 预期结论

在该样例中：

- `transformer_small_aug` 的最终准确率最高
- 数据增强带来的收益大于学习率调度
- 量化模型牺牲少量准确率，但显著降低推理延迟
