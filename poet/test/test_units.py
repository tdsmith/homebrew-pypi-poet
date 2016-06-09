from __future__ import absolute_import, print_function

import mock

import poet
from poet_fixtures import old_style_pypi_json
from testfixtures import LogCapture


class TestPoet(object):
    def test_research_non_canonical_version(self):
        poet.research_package("functools32", "3.2.3.post2")

    @mock.patch('codecs.getreader')
    def test_research_downloads_if_necessary(self, mock_getreader):
        mock_getreader.return_value = mock.mock_open(read_data=old_style_pypi_json)
        with LogCapture() as l:
            poet.research_package("eleven")
            assert "Fetching sdist" in str(l)
