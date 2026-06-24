from __future__ import annotations

import argparse
import ast
from email.parser import Parser
import hashlib
import re
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path


class ReleaseCheckError(RuntimeError):
    def __init__(self, failures: list[str]) -> None:
        self.failures = failures
        super().__init__("\n".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Check local Lab-Sidecar release metadata and distribution artifacts. "
            "This script never tags, uploads, publishes, or creates a release."
        )
    )
    parser.add_argument("--version", required=True, help="Expected package version, for example 0.1.5.")
    parser.add_argument("--tag", help="Optional expected tag name, for example v0.1.5.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root. Defaults to the current directory.")
    parser.add_argument("--dist-dir", type=Path, help="Distribution directory. Defaults to <repo>/dist.")
    parser.add_argument(
        "--require-clean-git",
        action="store_true",
        help="Also require git status --porcelain to be empty before a maintainer tags or publishes.",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    dist_dir = args.dist_dir.resolve() if args.dist_dir is not None else repo / "dist"
    try:
        messages = run_release_check(
            repo=repo,
            version=args.version,
            tag=args.tag,
            dist_dir=dist_dir,
            require_clean_git=args.require_clean_git,
        )
    except ReleaseCheckError as exc:
        print("Release check failed:", file=sys.stderr)
        for failure in exc.failures:
            print(f"- {failure}", file=sys.stderr)
        raise SystemExit(1) from exc

    for message in messages:
        print(message)


def run_release_check(
    *,
    repo: Path,
    version: str,
    tag: str | None = None,
    dist_dir: Path | None = None,
    require_clean_git: bool = False,
) -> list[str]:
    dist = dist_dir if dist_dir is not None else repo / "dist"
    failures: list[str] = []
    messages: list[str] = []

    _check_repo_root(repo, failures)
    if tag is not None:
        _check_tag(tag, version, failures, messages)
    _check_pyproject(repo / "pyproject.toml", version, failures, messages)
    _check_init_version(repo / "lab_sidecar" / "__init__.py", version, failures, messages)
    _check_changelog(repo / "CHANGELOG.md", version, failures, messages)
    _check_git_diff(repo, failures, messages)
    _check_staged_git_diff(repo, failures, messages)
    _check_head_whitespace(repo, failures, messages)
    if require_clean_git:
        _check_git_status(repo, failures, messages)
    _check_root_state_dir(repo, failures, messages)
    _check_dist(dist, version, failures, messages)

    if failures:
        raise ReleaseCheckError(failures)
    messages.append("ok: release check completed without creating tags, releases, uploads, or publishes")
    return messages


def _check_repo_root(repo: Path, failures: list[str]) -> None:
    if not (repo / "pyproject.toml").is_file():
        failures.append(f"pyproject.toml was not found under repo: {repo}")
    if not (repo / "lab_sidecar" / "__init__.py").is_file():
        failures.append(f"lab_sidecar/__init__.py was not found under repo: {repo}")
    if not (repo / "CHANGELOG.md").is_file():
        failures.append(f"CHANGELOG.md was not found under repo: {repo}")


def _check_tag(tag: str, version: str, failures: list[str], messages: list[str]) -> None:
    expected = f"v{version}"
    if tag != expected:
        failures.append(f"--tag must be {expected!r} for --version {version}, got {tag!r}")
        return
    messages.append(f"ok: tag spelling matches {expected}")


def _check_pyproject(path: Path, version: str, failures: list[str], messages: list[str]) -> None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        failures.append(f"could not read {path}: {exc}")
        return

    actual = data.get("project", {}).get("version")
    if actual != version:
        failures.append(f"pyproject.toml project.version is {actual!r}; expected {version!r}")
        return
    messages.append(f"ok: pyproject.toml project.version is {version}")


def _check_init_version(path: Path, version: str, failures: list[str], messages: list[str]) -> None:
    try:
        actual = _read_dunder_version(path)
    except (OSError, SyntaxError, ValueError) as exc:
        failures.append(f"could not read lab_sidecar/__init__.py __version__: {exc}")
        return

    if actual != version:
        failures.append(f"lab_sidecar/__init__.py __version__ is {actual!r}; expected {version!r}")
        return
    messages.append(f"ok: lab_sidecar.__version__ is {version}")


def _read_dunder_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name) and target.id == "__version__":
                value = ast.literal_eval(statement.value)
                if not isinstance(value, str):
                    raise ValueError("__version__ is not a string literal")
                return value
    raise ValueError("__version__ assignment was not found")


def _check_changelog(path: Path, version: str, failures: list[str], messages: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        failures.append(f"could not read CHANGELOG.md: {exc}")
        return

    heading = re.compile(rf"^## \[{re.escape(version)}\](?:\s+-\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$", re.MULTILINE)
    if not heading.search(text):
        failures.append(f"CHANGELOG.md does not contain a heading for [{version}]")
        return
    messages.append(f"ok: CHANGELOG.md contains a [{version}] entry")


def _check_git_diff(repo: Path, failures: list[str], messages: list[str]) -> None:
    result = subprocess.run(
        ["git", "diff", "--check"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        failures.append(f"git diff --check failed; fix whitespace errors before release\n{detail}")
        return
    messages.append("ok: git diff --check passed")


def _check_staged_git_diff(repo: Path, failures: list[str], messages: list[str]) -> None:
    result = subprocess.run(
        ["git", "diff", "--cached", "--check"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        failures.append(f"git diff --cached --check failed; fix staged whitespace errors before release\n{detail}")
        return
    messages.append("ok: staged git diff --check passed")


def _check_head_whitespace(repo: Path, failures: list[str], messages: list[str]) -> None:
    result = subprocess.run(
        ["git", "diff-tree", "--check", "--root", "--no-commit-id", "-r", "HEAD"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        failures.append(f"git diff-tree --check HEAD failed; fix committed whitespace errors before release\n{detail}")
        return
    messages.append("ok: committed HEAD whitespace check passed")


def _check_git_status(repo: Path, failures: list[str], messages: list[str]) -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        failures.append(f"git status --porcelain failed; run from a git checkout before release\n{detail}")
        return
    if result.stdout.strip():
        failures.append(
            "git working tree is not clean; commit, remove, or intentionally ignore files before tagging\n"
            + result.stdout.strip()
        )
        return
    messages.append("ok: git working tree is clean")


def _check_root_state_dir(repo: Path, failures: list[str], messages: list[str]) -> None:
    state_dir = repo / ".lab-sidecar"
    if state_dir.exists():
        failures.append("repository root contains .lab-sidecar; remove generated local task state before release")
        return
    messages.append("ok: repository root does not contain .lab-sidecar")


def _check_dist(dist_dir: Path, version: str, failures: list[str], messages: list[str]) -> None:
    expected_names = {
        f"lab_sidecar-{version}-py3-none-any.whl",
        f"lab_sidecar-{version}.tar.gz",
    }
    if not dist_dir.is_dir():
        failures.append(f"dist directory was not found: {dist_dir}; run python -m build first")
        return

    files = sorted(path for path in dist_dir.iterdir() if path.is_file())
    names = {path.name for path in files}
    missing = sorted(expected_names - names)
    if missing:
        failures.append(f"dist is missing target artifact(s): {', '.join(missing)}")

    unexpected = sorted(names - expected_names)
    if unexpected:
        stale = [name for name in unexpected if name.startswith("lab_sidecar-")]
        if stale:
            failures.append(
                "dist contains stale or wrong-version Lab-Sidecar artifact(s): "
                + ", ".join(stale)
                + "; clean dist and rebuild for the target version"
            )
        else:
            failures.append(
                "dist contains unexpected file(s): "
                + ", ".join(unexpected)
                + "; keep release dist limited to the target wheel and sdist"
            )

    if missing or unexpected:
        return

    for path in files:
        _check_dist_metadata(path, version, failures, messages)
    if failures:
        return

    for path in files:
        digest = _sha256(path)
        messages.append(f"sha256 {path.name} {digest}")
    messages.append(f"ok: dist artifacts match version {version}")


def _check_dist_metadata(path: Path, version: str, failures: list[str], messages: list[str]) -> None:
    try:
        metadata = _read_distribution_metadata(path)
    except (OSError, RuntimeError, tarfile.TarError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        failures.append(f"could not inspect distribution metadata for {path.name}: {exc}")
        return

    name = metadata.get("Name")
    actual_version = metadata.get("Version")
    if name != "lab-sidecar":
        failures.append(f"{path.name} metadata Name is {name!r}; expected 'lab-sidecar'")
    if actual_version != version:
        failures.append(f"{path.name} metadata Version is {actual_version!r}; expected {version!r}")
    if name == "lab-sidecar" and actual_version == version:
        messages.append(f"ok: {path.name} metadata declares lab-sidecar {version}")


def _read_distribution_metadata(path: Path) -> dict[str, str]:
    if path.suffix == ".whl":
        text = _read_wheel_metadata(path)
    elif path.name.endswith(".tar.gz"):
        text = _read_sdist_metadata(path)
    else:
        raise RuntimeError("unsupported distribution artifact type")

    parsed = Parser().parsestr(text)
    return {key: value for key, value in parsed.items()}


def _read_wheel_metadata(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise RuntimeError(f"expected exactly one .dist-info/METADATA file, found {len(metadata_names)}")
        return archive.read(metadata_names[0]).decode("utf-8")


def _read_sdist_metadata(path: Path) -> str:
    with tarfile.open(path, mode="r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile() and member.name.endswith("/PKG-INFO")]
        if not members:
            raise RuntimeError("PKG-INFO was not found")
        member = sorted(members, key=lambda item: (item.name.count("/"), item.name))[0]
        extracted = archive.extractfile(member)
        if extracted is None:
            raise RuntimeError(f"could not extract {member.name}")
        return extracted.read().decode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
