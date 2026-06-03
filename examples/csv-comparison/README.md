# csv-comparison

多实验 CSV 对比样例，用于验证：

- 多文件导入
- 指标字段规范化
- 多实验对比曲线
- 最终指标柱状图

## 文件说明

- `baseline.csv`
- `model_a.csv`
- `model_b.csv`

三个文件结构一致，包含 `epoch`、`model`、`seed`、`val_accuracy`、`val_loss`。

## 预期用途

未来在 Lab-Sidecar 中可执行：

```bash
labsidecar ingest ./examples/csv-comparison
labsidecar collect <task_id>
labsidecar figures <task_id>
```

推荐至少生成：

- 一张 `val_accuracy` 多实验对比曲线
- 一张最终 `val_accuracy` 柱状图
