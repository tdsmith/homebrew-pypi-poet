# Integration tests for poet

import subprocess
import sys
import os
import shutil

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path  # python 2 backport

import pytest


def poet(*args):
    return subprocess.check_output(["poet"] + list(args), stderr=subprocess.STDOUT)


def test_version():
    assert b"homebrew-pypi-poet" in poet("-V")


def test_single():
    result = poet("-s", "nose", "six")
    assert b'resource "nose"' in result
    assert b'resource "six"' in result


def test_formula():
    result = poet("-f", "pytest")
    assert b'resource "py" do' in result
    print(result)
    assert (
        'depends_on "python@{}.{}'.format(
            sys.version_info.major, sys.version_info.minor
        ).encode("utf-8")
        in result
    )


def test_case_sensitivity():
    poet("-f", "FoBiS.py")


def test_resources():
    result = poet("pytest")
    assert b'resource "py" do' in result
    result = poet("py.test")
    assert b"PackageNotInstalledWarning" in result


def test_uses_sha256_from_json(monkeypatch):
    monkeypatch.setenv("POET_DEBUG", "10")
    result = poet("pytest")
    assert b"Using provided checksum for py\n" in result


@pytest.mark.skipif(sys.version_info.major < 3, reason="Python@2 no longer supported in brew")
def test_audit():
    """https://github.com/Homebrew/discussions/discussions/2531"""
    env = os.environ.get("TOX_ENV_NAME", "poet-test")
    repository = (
        subprocess.check_output(
            [
                "brew",
                "--repository",
                "homebrew-poet/{}".format(env),
            ]
        )
        .decode("utf-8")
        .strip()
    )
    repository_path = Path(repository, "Formula")
    repository_path.mkdir(exist_ok=True, parents=True)
    try:
        with open(str(Path(repository_path, "pytest.rb")), "wb") as f:
            subprocess.check_call(["poet", "-f", "pytest"], stdout=f)
        subprocess.check_call(["brew", "audit", "--strict", "pytest"])
    finally:
        shutil.rmtree(repository)


def test_lint(tmpdir):
    home = tmpdir.chdir()
    try:
        with open("pytest.rb", "wb") as f:
            subprocess.check_call(["poet", "-f", "pytest"], stdout=f)
        subprocess.check_call(["poet_lint", "pytest.rb"])
    finally:
        tmpdir.join("pytest.rb").remove(ignore_errors=True)
        home.chdir()


def test_camel_case():
    result = poet("-f", "magic-wormhole")
    assert b"class MagicWormhole < Formula" in result
