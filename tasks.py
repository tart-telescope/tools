"""
Release automation for the TART tools image: invoke tasks backed by plumbum.

    invoke --list
    invoke test                       # build the image and run every docker test
    invoke bump --dry-run             # show the next tag
    invoke release --dry-run          # show the whole plan
    invoke release --disko-version=1.5.0 --yes

The tools repo has no package version of its own: the release *is* the git
tag, and .github/workflows/docker-publish.yml builds and pushes
ghcr.io/tart-telescope/tools:<tag> for amd64 + arm64 (arm64 on a self-hosted
runner) when that tag is pushed.

`release` stages:

    1. test     `make docker` then `make test-all` — tart2ms, disko,
                spotless, the import check and the tart_tools CLIs, all run
                inside the freshly built image (this is also what proves the
                Dockerfile's pins still resolve, since the build pip
                installs them from PyPI).
    2. pin      with --disko-version=X.Y.Z, verify PyPI really has that
                version (the caller's publish must have landed) and set the
                Dockerfile's exact `disko==X.Y.Z` pin — releases must be
                reproducible, not "whatever is newest on PyPI".
    3. tag      commit (if the pin changed) + tag v<next> + push, which
                triggers the image build.
    4. wait     poll until the image tag exists on GHCR, because the next
                stage (tart_cargo) must not bump its base image to a tag
                that is still building (AGENTS.md: never bump ahead of a
                pushed image tag).

This file is also invoked from disko's release chain:
`invoke -r <this repo> release --level=patch --yes --disko-version=<new>`.
It needs invoke + plumbum on the interpreter running it (both are installed
globally, and disko's dev group carries them for the chain).
"""

from __future__ import annotations

import json
import re
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

from invoke import Exit, task
from plumbum import colors, local

ROOT = Path(__file__).resolve().parent
DOCKERFILE = ROOT / "Dockerfile"
IMAGE = "ghcr.io/tart-telescope/tools"

UV_OR_MAKE = local["make"]
GIT = local["git"]

_LEVELS = ("patch", "minor", "major")
_DISKO_PIN = re.compile(r'"disko[^"]*"')


# ---------------------------------------------------------------- helpers

def _run(cmd, **kwargs):
    print(_paint(colors.light_blue, f"+ {cmd}"), flush=True)
    kwargs.setdefault("cwd", str(ROOT))  # the chain may be invoked from anywhere
    return cmd.run(**kwargs)


def _capture(cmd):
    return cmd.run(retcode=None, cwd=str(ROOT))


def _paint(style, text: str) -> str:
    """plumbum 2 applies styles with `text | style` (plain text off a tty)."""
    return text | style


def _green(text):
    return _paint(colors.green, text)


def _yellow(text):
    return _paint(colors.yellow, text)


def _banner(text):
    print(_paint(colors.bold, f"\n=== {text}"), flush=True)


def _git(*args):
    rc, out, err = local["git"][list(args)].run(retcode=None, cwd=str(ROOT))
    if rc != 0:
        raise Exit(f"git {' '.join(args)} failed: {err.strip()}")
    return out.strip()


def _confirm(message: str, assume_yes: bool) -> None:
    if assume_yes:
        print(_yellow(f"{message} (--yes: proceeding)"))
        return
    if input(f"{message} [y/N] ").strip().lower() not in ("y", "yes"):
        raise Exit("aborted")


def latest_tag() -> str:
    rc, out, _ = _capture(GIT["describe", "--tags", "--abbrev=0"])
    if rc != 0:
        raise Exit("no git tag found — the image version lives in tags")
    return out.strip()


def next_tag(level: str) -> str:
    if level not in _LEVELS:
        raise Exit(f"--level must be one of {_LEVELS}, got {level!r}")
    major, minor, patch = (int(part) for part in latest_tag().lstrip("v").split("."))
    if level == "major":
        return f"v{major + 1}.0.0"
    if level == "minor":
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def _assert_clean() -> None:
    """Untracked scratch is fine; modified tracked files are not."""
    modified, untracked = [], []
    for line in _git("status", "--porcelain").splitlines():
        if not line.strip():
            continue
        (untracked if line.startswith("??") else modified).append(line)
    if untracked:
        print(_yellow(f"  ignoring {len(untracked)} untracked path(s)"))
    if modified:
        raise Exit("working tree has modified files; commit or stash them:\n  " + "\n  ".join(modified))


# --------------------------------------------------------------- external

def _pypi_has(package: str, version: str) -> bool:
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.status == 200
    except urllib.error.HTTPError:
        return False
    except urllib.error.URLError as exc:
        raise Exit(f"cannot reach PyPI ({exc})") from exc


def _wait_for_pypi(package: str, version: str, timeout_s: int = 900, poll_s: int = 15) -> None:
    print(_paint(colors.light_blue, f"  waiting for {package} {version} on PyPI ..."))
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _pypi_has(package, version):
            print(_green(f"  PyPI has {package} {version}"))
            return
        time.sleep(poll_s)
    raise Exit(f"timed out after {timeout_s}s waiting for {package} {version} on PyPI")


def _image_tag_exists(tag: str) -> bool:
    image = f"{IMAGE}:{tag}"
    # local.which() raises when missing and returns a path when present, so
    # detect with shutil.which and build the command with local[...].
    if shutil.which("docker"):
        rc, _, _ = _capture(local["docker"]["manifest", "inspect", image])
        if rc == 0:
            return True
    # Fall back to the registry's tag list (the image is public).
    token_url = "https://ghcr.io/token?scope=repository:tart-telescope/tools:pull&service=ghcr.io"
    try:
        with urllib.request.urlopen(token_url, timeout=20) as response:
            token = json.load(response).get("token", "")
        request = urllib.request.Request(
            "https://ghcr.io/v2/tart-telescope/tools/tags/list",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return tag in (json.load(response).get("tags") or [])
    except (urllib.error.URLError, json.JSONDecodeError):
        return False


def _wait_for_image(tag: str, timeout_s: int = 3600, poll_s: int = 30) -> None:
    """docker-publish.yml builds amd64 + arm64 (the latter on a self-hosted
    runner), so this can take a while — but tart_cargo may not bump its base
    image to this tag until it exists."""
    print(_paint(colors.light_blue, f"  waiting for {IMAGE}:{tag} on GHCR ..."))
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _image_tag_exists(tag):
            print(_green(f"  GHCR has {IMAGE}:{tag}"))
            return
        time.sleep(poll_s)
    raise Exit(f"timed out after {timeout_s}s waiting for {IMAGE}:{tag} (check docker-publish.yml)")


# ------------------------------------------------------------------- tasks

@task(help={"quick": "build is already done; only run the container tests"})
def test(c, quick=False):
    """Build the image and run every docker test target (make test-all)."""
    _banner("test: tools image")
    if not quick:
        _run(UV_OR_MAKE["docker"])
    _run(UV_OR_MAKE["test-all"])
    print(_green("\ntest: OK"))


@task(help={"level": "patch | minor | major (default: patch)", "dry_run": "show, don't write"})
def bump(c, level="patch", dry_run=False):
    """Show (or compute) the next image tag — the image version lives in tags."""
    _banner("bump")
    current, new = latest_tag(), next_tag(level)
    print(f"  image tag {current} -> {new} ({level})")
    if dry_run:
        print(_yellow("  dry run: no tag created"))
    return new


def _set_disko_pin(version: str) -> bool:
    """Pin `disko==version` exactly: releases must be reproducible."""
    text = DOCKERFILE.read_text()
    matches = _DISKO_PIN.findall(text)
    if len(matches) != 1:
        raise Exit(f"expected exactly one disko pin in the Dockerfile, found {len(matches)}")
    new_pin = f'"disko=={version}"'
    if matches[0] == new_pin:
        print(f"  Dockerfile already pinned {new_pin}")
        return False
    DOCKERFILE.write_text(_DISKO_PIN.sub(new_pin, text, count=1))
    print(_green(f"  Dockerfile pin {matches[0]} -> {new_pin}"))
    return True


@task(
    help={
        "level": "patch | minor | major for the image tag (default: patch)",
        "yes": "skip the confirmation prompt",
        "disko_version": "pin the Dockerfile to exactly this disko release",
        "wait": "wait for the GHCR image to exist (default)",
        "skip_tests": "skip make test-all (not for routine use)",
        "dry_run": "print the plan and exit",
    }
)
def release(
    c,
    level="patch",
    yes=False,
    disko_version=None,
    wait=True,
    skip_tests=False,
    dry_run=False,
):
    """test -> pin -> tag -> CI builds the image -> wait for GHCR."""
    planned = next_tag(level)

    if dry_run:
        _banner("tools release plan (dry run)")
        print("  1. test       make docker + make test-all")
        if disko_version:
            print(f"  2. pin        Dockerfile: disko=={disko_version} (verified on PyPI first)")
        print(f"  3. tag        {latest_tag()} -> {planned}, push -> docker-publish.yml -> GHCR")
        if wait:
            print(f"  4. wait       poll until {IMAGE}:{planned} exists")
        print(_yellow("  dry run: nothing executed"))
        return

    _banner("tools release")
    _assert_clean()

    if disko_version:
        # The caller's disko publish may only just have landed.
        _wait_for_pypi("disko", disko_version)

    if not skip_tests:
        test(c)
    elif disko_version:
        # Still prove the new pin resolves: the image build *is* that test.
        print(_yellow("  --skip-tests: building the image only, to validate the pin"))
        _run(UV_OR_MAKE["docker"])

    if disko_version:
        _set_disko_pin(disko_version)

    _confirm(f"Tag {planned} and push (CI builds and pushes the image)?", yes)

    _run(GIT["add", str(DOCKERFILE)])
    if _capture(GIT["diff", "--cached", "--quiet"])[0] != 0:
        _run(GIT["commit", "-m", f"Release {planned}" + (f": pin disko=={disko_version}" if disko_version else "")])
    else:
        print("  nothing to commit; tagging the current commit")
    _run(GIT["tag", "-a", planned, "-m", f"Release {planned}"])
    _run(GIT["push", "--follow-tags", "origin", "HEAD"])

    if wait:
        _wait_for_image(planned)
    else:
        print(_yellow("  not waiting for GHCR; tart_cargo must not bump to this tag yet"))

    print(_green(f"\ntools release {planned} complete"))
