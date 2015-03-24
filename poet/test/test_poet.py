# Integration tests for poet

import subprocess
import sys

def poet(*args):
    return subprocess.check_output(
            ["poet"] + list(args),
            stderr=subprocess.STDOUT)

def test_version():
    assert b"homebrew-pypi-poet" in poet("-V")

def test_single():
    result = poet("-s", "nose", "six")
    assert b'resource "nose"' in result
    assert b'resource "six"' in result

def test_formula():
    result = poet("-f", "pytest")
    assert b'resource "py" do' in result
    if sys.version_info.major == 2:
        assert b'depends_on :python if' in result
    else:
        assert b'depends_on :python3' in result

def test_resources():
    result = poet("pytest")
    assert b'resource "py" do' in result
    result = poet("py.test")
    assert b'PackageNotInstalledWarning' in result
