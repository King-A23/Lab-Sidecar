# algorithm-benchmark

算法性能对比样例，覆盖多算法、多输入规模、多 seed 的 JSON 结果。

## 文件说明

- `results.json`：排序算法 benchmark 结果

## 适合验证的能力

- `ingest` 导入已有结果目录
- `collect` 规范化 `algorithm`、`input_size`、`seed`、`runtime_ms`
- `figures` 生成运行时间对比图
- `report` 输出简短 benchmark 摘要

## 预期结论

在该样例中：

- `quick_sort` 是最快算法
- `merge_sort` 次之
- `heap_sort` 最慢但内存占用更稳定
