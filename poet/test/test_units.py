from __future__ import absolute_import, print_function
import mock
import json
import poet
from poet_fixtures import old_style_pypi_json, pipfile_lock, pipfile_lock_stanzas
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

    def test_generate_from_pipfile_dot_lock(self):
        output = poet.from_lock(json.loads(pipfile_lock))
        assert output.strip() == pipfile_lock_stanzas.strip()


class TestUtils(object):
    def test_dash_to_studly(self):
        assert poet.util.dash_to_studly("magic-worm-hole") == "MagicWormHole"
        assert poet.util.dash_to_studly("some_package-name") == "SomePackageName"


unlinted = """
  resource "homebrew-pypi-poet" do
    url "https://files.pythonhosted.org/packages/18/6d/c6d1543d2272696f22893eff382eb4b7d2594c983f87e7786abf6ad3ec9e/homebrew-pypi-poet-0.7.1.tar.gz"
    sha256 "8b3bba0b5f49ca76453464a2aa5c7cc19a8e85df141c86c98e1998796bedeafc"
  end

  resource "Jinja2" do
    url "https://files.pythonhosted.org/packages/f2/2f/0b98b06a345a761bec91a079ccae392d282690c2d8272e708f4d10829e22/Jinja2-2.8.tar.gz"
    sha256 "bc1ff2ff88dbfacefde4ddde471d1417d3b304e8df103a7a9437d47269201bf4"
  end

  resource "MarkupSafe" do
    url "https://files.pythonhosted.org/packages/c0/41/bae1254e0396c0cc8cf1751cb7d9afc90a602353695af5952530482c963f/MarkupSafe-0.23.tar.gz"
    sha256 "a4ec1aff59b95a14b45eb2e23761a0179e98319da5a7eb76b56ea8cdc7b871c3"
  end

  resource "tl.eggdeps" do
    url "https://files.pythonhosted.org/packages/72/55/c6774bd47e749e1de2b4bbff0002fa1567b7c9d41ee317dc603d13d1d467/tl.eggdeps-0.4.tar.gz"
    sha256 "a99de5e4652865224daab09b2e2574a4f7c1d0d9a267048f9836aa914a2caf3a"
  end
"""  # noqa


class TestLint(object):
    def test_lint(self):
        linted = poet.lint(unlinted)
        jinja_index = linted.index("Jinja2")
        poet_index = linted.index("homebrew-pypi-poet")
        assert poet_index > jinja_index
