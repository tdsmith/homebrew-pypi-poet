#!/usr/bin/env python

""" homebrew-pypi-poet

Invoked like "poet foo" for some package foo **which is presently
installed in sys.path**, determines which packages foo and its dependents
depend on, downloads them from pypi and computes their checksums, and
spits out Homebrew resource stanzas.
"""

from __future__ import print_function
import argparse
from collections import OrderedDict
from hashlib import sha256
import json
import sys
from six.moves.urllib.request import urlopen
import warnings
import codecs

from jinja2 import Template
import networkx
import pip
import tl.eggdeps.graph

FORMULA_TEMPLATE = Template(
"""class {{ package.name|capitalize }} < Formula
  homepage "{{ package.homepage }}"
  url "{{ package.url }}"
  sha256 "{{ package.checksum }}"

{% if resources %}
{%   for resource in resources %}
{%     include ResourceTemplate %}


{%   endfor %}
{% endif %}
  def install
{% if resources %}
    ENV.prepend_create_path "PYTHONPATH", libexec/"vendor/lib/python{{ py_version }}/site-packages"
    %w[{{ resources|map(attribute='name')|join(' ') }}].each do |r|
      resource(r).stage do
        system "python", *Language::Python.setup_install_args(libexec/"vendor")
      end
    end

{% endif %}
    ENV.prepend_create_path "PYTHONPATH", libexec/"lib/python{{ py_version }}/site-packages"
    system "python", *Language::Python.setup_install_args(libexec)

    bin.install Dir[libexec/"bin/*"]
    bin.env_script_all_files(libexec/"bin", :PYTHONPATH => ENV["PYTHONPATH"])
  end
end
""", trim_blocks=True)

RESOURCE_TEMPLATE = Template(
"""  resource "{{ resource.name }}" do
    url "{{ resource.url }}"
    {{ resource.checksum_type }} "{{ resource.checksum }}"
  end
""")


class PackageNotInstalledWarning(UserWarning):
    pass


def research_package(name, version=None):
    f = urlopen("https://pypi.python.org/pypi/{}/{}/json".
                        format(name, version or ''))
    reader = codecs.getreader("utf-8")
    pkg_data = json.load(reader(f))
    f.close()
    d = {}
    d['name'] = pkg_data['info']['name']
    d['homepage'] = pkg_data['info'].get('home_page', '')
    for url in pkg_data['urls']:
        if url['packagetype'] == 'sdist':
            d['url'] = url['url']
            f = urlopen(url['url'])
            d['checksum'] = sha256(f.read()).hexdigest()
            d['checksum_type'] = 'sha256'
            f.close()
            break
    return d


def make_graph(pkg):
    egg_graph = tl.eggdeps.graph.Graph()
    egg_graph.from_specifications(pkg)

    # create graph
    ignore = ['argparse', 'pip', 'setuptools', 'wsgiref']
    G = networkx.DiGraph()
    keys = [key for key in egg_graph.keys() if key not in ignore]
    G.add_nodes_from(keys)
    G.add_edges_from([(k, v) for k in keys for v in egg_graph[k].keys()
                      if v not in ignore])

    # add version attribute
    installed_packages = pip.get_installed_distributions()
    versions = {package.key: package.version for package in installed_packages}
    for package in G.nodes():
        try:
            G.node[package]['version'] = versions[package]
        except KeyError:
            warnings.warn("{} is not installed so we cannot compute "
                          "resources for its dependencies.".format(package),
                          PackageNotInstalledWarning)
            G.node[package]['version'] = None

    for package in G.nodes():
        package_data = research_package(package, G.node[package]['version'])
        G.node[package].update(package_data)

    # get the dependency resolution order
    deps = networkx.algorithms.dag.topological_sort(G)
    deps.reverse()

    return OrderedDict([(dep, G.node[dep]) for dep in deps])


def formula_for(package):
    nodes = make_graph(package)
    resources = [value for key, value in nodes.items()
                 if key.lower() != package.lower()]
    root = nodes[package]
    return FORMULA_TEMPLATE.render(package=root,
                                   resources=resources,
                                   py_version="2.7",
                                   ResourceTemplate=RESOURCE_TEMPLATE)


def resources_for(package):
    nodes = make_graph(package)
    return '\n\n'.join([RESOURCE_TEMPLATE.render(resource=node)
                        for node in nodes.values()])


def main():
    parser = argparse.ArgumentParser(
        description='Generate Homebrew resource stanzas for pypi packages '
                    'and their dependencies.')
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        '--single', '-s', metavar='package', nargs='+',
        help='Generate a resource stanza for one or more packages, '
             'without considering dependencies.')
    actions.add_argument(
        '--formula', '-f', metavar='package',
        help='Generate a complete formula for a pypi package with its '
             'recursive pypi dependencies as resources.')
    actions.add_argument(
        '--resources', '-r', metavar='package',
        help='Generate resource stanzas for a package and its recursive '
             'dependencies (default).')
    parser.add_argument('package', help=argparse.SUPPRESS, nargs='?')
    args = parser.parse_args()

    if (args.formula or args.resources) and args.package:
        print('--formula and --resources take a single argument.',
              file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 1

    if args.formula:
        print(formula_for(args.formula))
    elif args.single:
        for i, package in enumerate(args.single):
            data = research_package(package)
            print(RESOURCE_TEMPLATE.render(resource=data))
            if i != len(args.single)-1:
                print()
    else:
        package = args.resources or args.package
        if not package:
            parser.print_usage(sys.stderr)
            return 1
        print(resources_for(package))
    return 0


if __name__ == '__main__':
    sys.exit(main())
