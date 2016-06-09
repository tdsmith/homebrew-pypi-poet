#!/usr/bin/env python

""" homebrew-pypi-poet

Invoked like "poet foo" for some package foo **which is presently
installed in sys.path**, determines which packages foo and its dependents
depend on, downloads them from pypi and computes their checksums, and
spits out Homebrew resource stanzas.
"""

from __future__ import print_function
import argparse
import codecs
from collections import OrderedDict
from contextlib import closing
from hashlib import sha256
import json
import logging
import os
import sys
from textwrap import dedent
import warnings

from jinja2 import Template
import pkg_resources
import tl.eggdeps.graph

from .version import __version__

try:
    # Python 2.x
    from urllib2 import urlopen
except ImportError:
    # Python 3.x
    from urllib.request import urlopen

# Show warnings and greater by default
logging.basicConfig(level=int(os.environ.get("POET_DEBUG", 30)))

FORMULA_TEMPLATE = Template(dedent("""\
    {% macro site_packages(python, prefix='') %}
    {% if python == "python3" %}
    libexec/"{{ prefix }}lib/python#{xy}/site-packages"
    {%- else %}
    libexec/"{{ prefix }}lib/python2.7/site-packages"
    {%- endif %}{% endmacro %}
    class {{ package.name|capitalize }} < Formula
      homepage "{{ package.homepage }}"
      url "{{ package.url }}"
      sha256 "{{ package.checksum }}"

    {% if python == "python" %}
      depends_on :python if MacOS.version <= :snow_leopard
    {% else %}
      depends_on :python3
    {% endif %}

    {% if resources %}
    {%   for resource in resources %}
    {%     include ResourceTemplate %}


    {%   endfor %}
    {% endif %}
      def install
    {% if python == "python3" %}
        xy = Language::Python.major_minor_version "python3"
    {% endif %}
    {% if resources %}
        ENV.prepend_create_path "PYTHONPATH", {{ site_packages(python, "vendor/") }}
        %w[{{ resources|map(attribute='name')|join(' ') }}].each do |r|
          resource(r).stage do
            system "{{ python }}", *Language::Python.setup_install_args(libexec/"vendor")
          end
        end

    {% endif %}
        ENV.prepend_create_path "PYTHONPATH", {{ site_packages(python) }}
        system "{{ python }}", *Language::Python.setup_install_args(libexec)

        bin.install Dir[libexec/"bin/*"]
        bin.env_script_all_files(libexec/"bin", :PYTHONPATH => ENV["PYTHONPATH"])
      end
    end
    """), trim_blocks=True)

RESOURCE_TEMPLATE = Template(dedent("""\
    resource "{{ resource.name }}" do
         url "{{ resource.url }}"
         {{ resource.checksum_type }} "{{ resource.checksum }}"
    end
    """))


class PackageNotInstalledWarning(UserWarning):
    pass


class PackageVersionNotFoundWarning(UserWarning):
    pass


def research_package(name, version=None):
    f = urlopen("https://pypi.io/pypi/{}/json".format(name))
    reader = codecs.getreader("utf-8")
    pkg_data = json.load(reader(f))
    f.close()
    d = {}
    d['name'] = pkg_data['info']['name']
    d['homepage'] = pkg_data['info'].get('home_page', '')
    artefact = None
    if version:
        for pypi_version in pkg_data['releases']:
            if pkg_resources.safe_version(pypi_version) == version:
                for version_artefact in pkg_data['releases'][pypi_version]:
                    if version_artefact['packagetype'] == 'sdist':
                        artefact = version_artefact
                        break
        if artefact is None:
            warnings.warn("Could not find an exact version match for "
                          "{} version {}; using newest instead".
                          format(name, version), PackageVersionNotFoundWarning)

    if artefact is None:  # no version given or exact match not found
        for url in pkg_data['urls']:
            if url['packagetype'] == 'sdist':
                artefact = url
                break

    d['url'] = artefact['url']
    if 'digests' in artefact and 'sha256' in artefact['digests']:
        logging.debug("Using provided checksum for %s", name)
        d['checksum'] = artefact['digests']['sha256']
    else:
        logging.debug("Fetching sdist to compute checksum for %s", name)
        with closing(urlopen(artefact['url'])) as f:
            d['checksum'] = sha256(f.read()).hexdigest()
        logging.debug("Done fetching %s", name)
    d['checksum_type'] = 'sha256'
    f.close()
    return d


def make_graph(pkg):
    egg_graph = tl.eggdeps.graph.Graph()
    egg_graph.from_specifications(pkg)
    ignore = ['argparse', 'pip', 'setuptools', 'wsgiref']

    dependencies = {key: {} for key in egg_graph.keys() if key not in ignore}
    installed_packages = pkg_resources.working_set
    versions = {package.key: package.version for package in installed_packages}
    for package in dependencies:
        try:
            dependencies[package]['version'] = versions[package]
        except KeyError:
            warnings.warn("{} is not installed so we cannot compute "
                          "resources for its dependencies.".format(package),
                          PackageNotInstalledWarning)
            dependencies[package]['version'] = None

    for package in dependencies:
        package_data = research_package(package, dependencies[package]['version'])
        dependencies[package].update(package_data)

    return OrderedDict(
        [(package, dependencies[package]) for package in sorted(dependencies.keys())]
    )


def formula_for(package):
    nodes = make_graph(package)
    resources = [value for key, value in nodes.items()
                 if key.lower() != package.lower()]

    if package in nodes:
        root = nodes[package]
    elif package.lower() in nodes:
        root = nodes[package.lower()]
    else:
        raise "Could not find package {} in nodes {}".format(package, nodes.keys())

    python = "python" if sys.version_info.major == 2 else "python3"
    return FORMULA_TEMPLATE.render(package=root,
                                   resources=resources,
                                   python=python,
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
    parser.add_argument(
        '-V', '--version', action='version',
        version='homebrew-pypi-poet {}'.format(__version__))
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
