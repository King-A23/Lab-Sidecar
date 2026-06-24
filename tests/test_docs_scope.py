from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_current_scope_doc_exists_and_states_non_goals() -> None:
    path = PROJECT_ROOT / "docs" / "current-scope.md"

    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "CLI-first" in text
    assert "file-first" in text
    assert "local-first" in text
    assert "run / ingest -> collect -> figures -> report -> slides" in text
    assert "compare --save" in text

    for phrase in [
        "Web UI",
        "FastAPI",
        "hosted service",
        "remote runner",
        "general multi-agent framework",
        "Statistical significance",
        "model superiority",
    ]:
        assert phrase in text


def test_readme_keeps_scope_non_goals_visible() -> None:
    text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "CLI-first" in text
    assert "file-first" in text
    assert "local-first" in text
    for phrase in [
        "Web UI",
        "FastAPI",
        "hosted service",
        "remote runner",
        "general multi-agent framework",
        "statistical significance",
        "model superiority",
    ]:
        assert phrase in text


def test_agents_points_to_current_scope() -> None:
    text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "docs/current-scope.md" in text
    assert "current development boundary" in text


def test_release_hardening_docs_name_current_commands() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = (PROJECT_ROOT / "docs" / "public-alpha-quickstart.md").read_text(encoding="utf-8")
    checklist = (PROJECT_ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
    figure_specs = (PROJECT_ROOT / "docs" / "figure-specs.md").read_text(encoding="utf-8")
    artifact_protocol = (PROJECT_ROOT / "docs" / "artifact-protocol.md").read_text(encoding="utf-8")
    comparison_artifacts = (PROJECT_ROOT / "docs" / "comparison-artifacts.md").read_text(encoding="utf-8")

    combined = "\n".join([readme, quickstart, checklist, figure_specs, artifact_protocol, comparison_artifacts])
    for phrase in [
        "validate <task_id>",
        "validate-comparison",
        "package-comparison",
        "compare --save",
        "package-verify <package_dir>",
        "scripts/cli_full_smoke.py",
        "scripts/wheel_smoke.py",
        "artifact-index.sha256",
        "figures:",
    ]:
        assert phrase in combined
    assert "verify-package" not in combined
