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
from urllib.parse import urldefrag
import warnings

from jinja2 import Template
import pip
import pkg_resources

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
    class {{ package.name|capitalize }} < Formula
      include Language::Python::Virtualenv

      desc "Shiny new formula"
      homepage ""
      url "{{ package.url }}"
      sha256 "{{ package.checksum }}"

      depends_on :{{ python }}

    {% if resources %}
    {%   for resource in resources %}
    {%     include ResourceTemplate %}


    {%   endfor %}
    {% endif %}
      def install
    {% if python == "python3" %}
        virtualenv_create(libexec, "python3")
    {% endif %}
        virtualenv_install_with_resources
      end

      test do
        false
      end
    end
    """), trim_blocks=True)

RESOURCE_TEMPLATE = Template("""\
  resource "{{ resource.name }}" do
    url "{{ resource.url }}"
    {{ resource.checksum_type }} "{{ resource.checksum }}"
  end
""")


class PackageNotInstalledWarning(UserWarning):
    pass


class PackageVersionNotFoundWarning(UserWarning):
    pass


def recursive_dependencies(package):
    discovered = {package}
    visited = set()

    def walk(package):
        if package in visited:
            return
        visited.add(package)
        extras = ("security",) if package == "requests" else ()
        try:
            reqs = pkg_resources.get_distribution(package).requires(extras)
        except pkg_resources.DistributionNotFound:
            return
        discovered.update(req.project_name.lower() for req in reqs)
        for req in reqs:
            walk(req)

    walk(package)
    return sorted(discovered)


def research_package(name, version=None):
    finder = pip.index.PackageFinder(
        find_links=[],
        index_urls=['https://pypi.io/simple'],
        session=pip.download.PipSession(),
        format_control=pip.index.FormatControl({':all:'}, set()),  # no binary
    )
    link = None
    if version:
        req = pip.req.InstallRequirement.from_line('%s==%s' % (name, version), None)
        try:
            link = finder.find_requirement(req, False)
        except pip.exceptions.DistributionNotFound:
            warnings.warn("Could not find an exact version match for "
                          "{} version {}; using newest instead".
                          format(name, version), PackageVersionNotFoundWarning)
    if link is None:  # no version given or exact match not found
        req = pip.req.InstallRequirement.from_line(name, None)
        link = finder.find_requirement(req, False)

    url = urldefrag(link.url)[0]  # strip the fragment (containing the hash)
    if link.hash_name == 'sha256':
        logging.debug("Using provided checksum for %s", name)
        sha256 = link.hash
    else:
        logging.debug("Fetching sdist to compute checksum for %s", name)
        with closing(urlopen(url)) as f:
            sha256 = sha256(f.read()).hexdigest()

    return {
        'name': name,
        'url': url,
        'checksum_type': 'sha256',
        'checksum': sha256,
    }


def make_graph(pkg):
    ignore = ['argparse', 'pip', 'setuptools', 'wsgiref']
    pkg_deps = recursive_dependencies(pkg)

    dependencies = {key: {} for key in pkg_deps if key not in ignore}
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
        raise Exception("Could not find package {} in nodes {}".format(package, nodes.keys()))

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
