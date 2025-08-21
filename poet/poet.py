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
import json
import logging
import os
import sys
import warnings

import pkg_resources
import pypi_simple
from packaging.version import parse as parse_version, InvalidVersion

from .templates import FORMULA_TEMPLATE, RESOURCE_TEMPLATE, template_from_file
from .util import compute_sha256_sum, extract_credentials_from_url, transform_url
from .version import __version__


# Show warnings and greater by default
logging.basicConfig(level=int(os.environ.get("POET_DEBUG", 30)))


DEFAULT_INDEX_URL = "https://pypi.io/pypi"


class PackageNotInstalledWarning(UserWarning):
    pass


class PackageVersionNotFoundWarning(UserWarning):
    pass


class ConflictingDependencyWarning(UserWarning):
    pass


def recursive_dependencies(package):
    if not isinstance(package, pkg_resources.Requirement):
        raise TypeError("Expected a Requirement; got a %s" % type(package))

    discovered = {package.project_name.lower()}
    visited = set()

    def walk(package):
        if not isinstance(package, pkg_resources.Requirement):
            raise TypeError("Expected a Requirement; got a %s" % type(package))
        if package in visited:
            return
        visited.add(package)
        extras = package.extras
        if package == "requests":
            extras += ("security",)
        try:
            reqs = pkg_resources.get_distribution(package).requires(extras)
        except pkg_resources.DistributionNotFound:
            return
        discovered.update(req.project_name.lower() for req in reqs)
        for req in reqs:
            walk(req)

    walk(package)
    return sorted(discovered)


def research_package(index_url, name, version=None):
    package = {
        "name": name,
        "url": "",
        "checksum": "",
        "checksum_type": "sha256",
    }

    pypi_client = _get_pypi_client(index_url)

    distributions = pypi_client.get_project_files(name)
    source_distributions = [
        dist for dist in distributions if dist.package_type == 'sdist'
    ]
    if not source_distributions:
        warnings.warn("No sdist found for %s" % name)
        return package

    matching_distribution = None

    if version:
        matching_distribution = _find_exact_version(version, source_distributions)

        if matching_distribution is None:
            warnings.warn(
                "Could not find an exact version match for {} version {}; using newest "
                "instead".format(name, version),
                PackageVersionNotFoundWarning,
            )

    if matching_distribution is None:
        matching_distribution = _find_latest_version(source_distributions)

    # Strip fragment with hash information
    package["url"] = transform_url(matching_distribution.url, fragment="")

    digests = matching_distribution.get_digests()
    try:
        sha256_sum = digests["sha256"]
    except KeyError:
        logging.debug("Fetching sdist to compute checksum for %s", name)
        sha256_sum = compute_sha256_sum(matching_distribution.url)
        logging.debug("Done fetching %s", name)

    package["checksum"] = sha256_sum

    return package


def _get_pypi_client(index_url):
    index_url_without_creds, username, password = extract_credentials_from_url(
        index_url
    )

    return pypi_simple.PyPISimple(
        endpoint=index_url_without_creds,
        auth=(username, password),
    )


def _find_latest_version(distributions):
    valid_distributions = []
    for dist in distributions:
        try:
            parse_version(dist.version)
            valid_distributions.append(dist)
        except InvalidVersion:
            continue

    if not valid_distributions:
        return None

    return max(
        valid_distributions,
        key=(lambda dist: parse_version(dist.version)),
    )


def _find_exact_version(version, distributions):
    try:
        parsed_version = parse_version(version)
    except InvalidVersion:
        return None

    for dist in distributions:
        try:
            dist_version = parse_version(dist.version)
            if dist_version == parsed_version:
                return dist
        except InvalidVersion:
            # Skip distributions with invalid version strings
            continue

    return None


def make_graph(index_url, pkg):
    """Returns a dictionary of information about pkg & its recursive deps.

    Given a string, which can be parsed as a requirement specifier, return a
    dictionary where each key is the name of pkg or one of its recursive
    dependencies, and each value is a dictionary returned by research_package.
    (No, it's not really a graph.)
    """
    ignore = ['argparse', 'pip', 'setuptools', 'wsgiref']
    pkg_deps = recursive_dependencies(pkg_resources.Requirement.parse(pkg))

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
        package_data = research_package(index_url, package, dependencies[package]['version'])
        dependencies[package].update(package_data)

    return OrderedDict(
        [(package, dependencies[package]) for package in sorted(dependencies.keys())]
    )


def formula_for(index_url, package, also=None, template_path=None, include_python_minor_version=False, extra_depends=None):
    also = also or []
    extra_depends = extra_depends or []

    req = pkg_resources.Requirement.parse(package)
    package_name = req.project_name

    nodes = merge_graphs(make_graph(index_url, p) for p in [package] + also)
    resources = []
    for key, value in nodes.items():
        if key.lower() != package_name.lower():
            resources.append(value)
            # Check for PyNaCl and automatically add libsodium dependency
            if value.get('name', '').lower() == 'pynacl':
                if 'libsodium' not in extra_depends:
                    extra_depends.append('libsodium')

    if package_name in nodes:
        root = nodes[package_name]
    elif package_name.lower() in nodes:
        root = nodes[package_name.lower()]
    else:
        raise Exception("Could not find package {} in nodes {}".format(package, nodes.keys()))

    python = "python@{}".format(sys.version_info.major)
    if include_python_minor_version:
        python += ".{}".format(sys.version_info.minor)

    template = template_from_file(template_path) if template_path else FORMULA_TEMPLATE

    return template.render(
        package=root,
        resources=resources,
        python=python,
        extra_depends=extra_depends,
        ResourceTemplate=RESOURCE_TEMPLATE,
        env=os.environ,
    )


def resources_for(index_url, packages):
    nodes = merge_graphs(make_graph(index_url, p) for p in packages)
    return '\n\n'.join([RESOURCE_TEMPLATE.render(resource=node)
                        for node in nodes.values()])


def merge_graphs(graphs):
    result = {}
    for g in graphs:
        for key in g:
            if key not in result:
                result[key] = g[key]
            elif result[key] == g[key]:
                pass
            else:
                warnings.warn(
                    "Merge conflict: {l.name} {l.version} and "
                    "{r.name} {r.version}; using the former.".
                    format(l=result[key], r=g[key]),
                    ConflictingDependencyWarning)
    return OrderedDict([k, result[k]] for k in sorted(result.keys()))


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
    parser.add_argument(
        '--also', '-a', metavar='package', action='append', default=[],
        help='Specify an additional package that should be added to the '
             'resource list with its recursive dependencies. May not be used '
             'with --single. May be specified more than once.')
    parser.add_argument('package', help=argparse.SUPPRESS, nargs='?')
    parser.add_argument(
        '-V', '--version', action='version',
        version='homebrew-pypi-poet {}'.format(__version__))
    parser.add_argument(
        '--index-url', default=DEFAULT_INDEX_URL,
        help="Base URL of Python Package Index")
    parser.add_argument(
        '--formula-template',
        help='A custom Jinja2 template file to use if generating a forumla')
    parser.add_argument(
        '--include-python-minor-version',
        action="store_true",
        help='Include the minor version in the dependency on python')
    parser.add_argument(
        '--depends-on', '-d', action='append', default=[],
        help='Additional Homebrew dependencies to add as depends_on lines. Can be repeated.')
    args = parser.parse_args()

    if (args.formula or args.resources) and args.package:
        print('--formula and --resources take a single argument.',
              file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 1

    if args.also and args.single:
        print("Can't use --also with --single",
              file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 1

    if args.formula:
        print(
            formula_for(
                args.index_url,
                args.formula,
                args.also,
                args.formula_template,
                args.include_python_minor_version,
                args.depends_on,
            )
        )
    elif args.single:
        for i, package in enumerate(args.single):
            data = research_package(args.index_url, package)
            print(RESOURCE_TEMPLATE.render(resource=data))
            if i != len(args.single)-1:
                print()
    else:
        package = args.resources or args.package
        if not package:
            parser.print_usage(sys.stderr)
            return 1
        print(resources_for(args.index_url, [package] + args.also))
    return 0


if __name__ == '__main__':
    sys.exit(main())
