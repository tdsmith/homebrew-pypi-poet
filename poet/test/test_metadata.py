import pytest
from unittest import mock

from poet import get_checksum_from_pip_source_file



def test_get_checksum_from_pip_source_file(mocker):
    mocker.patch("poet.sha256.hexdigest(", return_value="sha256:1234567")
    assert get_checksum_from_pip_source_file("/path/to/pytest.py") == "sha256:1234567"



