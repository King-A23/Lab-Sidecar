# Figure Specs

Lab-Sidecar figure specs are optional YAML inputs for:

```bash
labsidecar figures <task_id> --spec figure.yaml
```

The deterministic renderer supports only static `line`, `bar`, and `box`
charts. Fallback is off by default. Unsupported explicit chart types are
recorded in `figures/figure-summary.json`; they do not create official figure
artifacts unless the user explicitly runs `--fallback bounded` and the bounded
validator accepts the fallback output.

## Legacy Single-Spec YAML

The original shape is one YAML object:

```yaml
figure_id: accuracy_line
chart_type: line
title: Accuracy over Epoch
x: epoch
y: accuracy
group_by: method
```

Required fields are `figure_id`, `chart_type`, `title`, `x`, and `y`.
`group_by` is optional. If `output` is omitted, Lab-Sidecar writes
`figures/<figure_id>.png` and `figures/<figure_id>.svg` inside the current task
directory.

## Multi-Figure YAML

The current public-alpha shape can contain multiple specs under `figures:`:

```yaml
figures:
  - figure_id: accuracy_line
    chart_type: line
    title: Accuracy over Epoch
    x: epoch
    y: accuracy
    group_by: method
  - figure_id: runtime_bar
    chart_type: bar
    title: Runtime by Method
    x: method
    y: runtime_ms
  - figure_id: accuracy_box
    chart_type: box
    title: Accuracy Distribution by Method
    x: method
    y: accuracy
```

Partial failures are allowed: supported valid specs can still render while
invalid, missing-field, or unsupported specs are recorded in
`figures/figure-summary.json` under `errors`, `skipped_candidates`, or
`unsupported_chart_diagnostics`.

## Output Paths

An optional `output` field may provide one PNG and one SVG path, either as an
object or list:

```yaml
figure_id: accuracy_line
chart_type: line
title: Accuracy over Epoch
x: epoch
y: accuracy
output:
  png: figures/custom-accuracy.png
  svg: figures/custom-accuracy.svg
```

Output paths must be relative, must stay inside the task's `figures/`
directory, and must end in `.png` and `.svg`.

## Current Limits

- Supported deterministic `chart_type` values are `line`, `bar`, and `box`.
- `line` charts need a numeric or datetime-like x field and a numeric y field.
- `bar` and `box` charts use categorical x fields and numeric y fields.
- High-cardinality categories or groups are refused and recorded as skipped
  candidates.
- Lab-Sidecar does not claim statistical significance, automatic chart
  interpretation, animation, video, or interactive figures.
