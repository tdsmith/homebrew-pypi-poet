from __future__ import absolute_import, print_function

import poet


class TestPoet(object):
    def test_research_non_canonical_version(self):
        poet.research_package("functools32", "3.2.3.post2")
