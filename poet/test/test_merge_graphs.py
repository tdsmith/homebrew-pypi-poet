from __future__ import absolute_import, print_function

import warnings
from collections import OrderedDict

import pytest

import poet


@pytest.mark.parametrize('version', ['1.0', None])
def test_merge_conflicting_graphs_keeps_first_dependency(version):
    first = {'name': 'Shared', 'version': version, 'url': 'first.tar.gz'}
    second = {'name': 'Shared', 'version': '2.0', 'url': 'second.tar.gz'}
    with pytest.warns(poet.ConflictingDependencyWarning) as recorded:
        result = poet.merge_graphs([
            {'shared': first, 'zulu': {'name': 'Zulu'}},
            {'shared': second, 'alpha': {'name': 'Alpha'}},
        ])
    assert str(recorded[0].message) == (
        'Merge conflict: Shared {} and Shared 2.0; using the former.'.format(version)
    )
    assert result == OrderedDict([
        ('alpha', {'name': 'Alpha'}),
        ('shared', first),
        ('zulu', {'name': 'Zulu'}),
    ])


def test_merge_identical_graphs_does_not_warn():
    node = {'name': 'Shared', 'version': '1.0'}
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter('always')
        result = poet.merge_graphs([{'shared': node}, {'shared': dict(node)}])
    assert not recorded
    assert result == {'shared': node}


def test_resources_render_after_dependency_conflict(monkeypatch):
    def make_graph(package):
        return {'shared': {
            'name': 'Shared',
            'version': package,
            'url': '{}.tar.gz'.format(package),
            'checksum_type': 'sha256',
            'checksum': 'checksum-{}'.format(package),
        }}

    monkeypatch.setattr('poet.poet.make_graph', make_graph)
    with pytest.warns(poet.ConflictingDependencyWarning):
        output = poet.resources_for(['first', 'second'])
    assert 'url "first.tar.gz"' in output
    assert 'sha256 "checksum-first"' in output
    assert 'second.tar.gz' not in output
