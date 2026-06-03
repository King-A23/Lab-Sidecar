# simple-failure

最小失败样例，用于验证 Phase 1 的失败状态保存和 stderr 诊断信息保留。

## 文件说明

- `fail.py`：一个会稳定退出码为 `1` 的脚本
- `stderr-example.log`：预期 stderr 内容，便于后续回归测试对比

## 建议测试方式

```bash
python fail.py
```

未来在 Lab-Sidecar 中的预期结果：

- 任务状态为 `failed`
- `stderr.log` 保留错误原文
- `manifest.json` 中存在 `exit_code` 和 `failure_summary`
