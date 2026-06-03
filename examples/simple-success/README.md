# simple-success

最小成功样例，用于验证 Phase 1 的 `run/status/logs/artifacts`，以及后续 Phase 2 的 `collect/figures/report`。

## 文件说明

- `train.py`：一个无外部依赖的伪训练脚本，会打印训练日志并输出 `metrics.csv`
- `metrics.csv`：脚本的确定性输出样例，便于不运行脚本时直接测试收集逻辑

## 建议测试方式

```bash
python train.py --output metrics.csv
```

未来在 Lab-Sidecar 中的预期流程：

```bash
labsidecar run "python train.py --output metrics.csv"
labsidecar collect <task_id>
labsidecar figures <task_id>
labsidecar report <task_id>
```
