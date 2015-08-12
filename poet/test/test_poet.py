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

def test_case_sensitivity():
    result = poet("-f", "FoBiS.py")

def test_resources():
    result = poet("pytest")
    assert b'resource "py" do' in result
    result = poet("py.test")
    assert b'PackageNotInstalledWarning' in result

def test_audit(tmpdir):
    home = tmpdir.chdir()
    try:
        with open("pytest.rb", "wb") as f:
            subprocess.check_call(["poet", "-f", "pytest"], stdout=f)
        subprocess.check_call(["brew", "audit", "./pytest.rb"])
    finally:
        tmpdir.join("pytest.rb").remove(ignore_errors=True)
        home.chdir()
