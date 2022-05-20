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

from importlib.metadata import metadata
import json
import logging
import os
import shlex
import subprocess
import sys
import warnings
from dataclasses import dataclass


from urlextract import URLExtract

import pkg_resources

from pathlib import Path
from .templates import FORMULA_TEMPLATE, RESOURCE_TEMPLATE
from .version import __version__

try:
    # Python 2.x
    from urllib2 import urlopen
except ImportError:
    # Python 3.x
    from urllib.request import urlopen

# Show warnings and greater by default
logging.basicConfig(level=int(os.environ.get("POET_DEBUG", 30)))


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


class PipSourceMetadataException(Exception):
    pass

@dataclass
class PackageMetadata:
    name: str
    homepage: str
    url: str
    checksum: str
    checksum_type: str

def get_download_url_from_pip_source_file(module: str, pip_source_file: Path, output_dir=os.getenv("PIP_SOURCE_DIR")) -> str:
    """
    Returns the download URL for the pip source distribution.
    This method will download the pip package from the source distribution. 

    The standard out of this command contains an obfuscated URL and a regular URL that points to a .tar.gz file.

    Args:
        module (str): The name of the module to download.
        output_dir (str): The directory to download the module to.

    Returns:
        str: The download URL for the pip source distribution.
    """
    try:
        output = subprocess.run(shlex.split(f"pip download --dest {output_dir} --no-binary :all: --no-deps {module}"), capture_output=True, text=True)
    except subprocess.CalledProcessError as cpe:
        raise PipSourceMetadataException(f"Could not download {module} from pip source file: {cpe.stderr}")
    
    try:
        extractor = URLExtract()
        urls = extractor.find_urls(output.stdout)
        return [url for url in urls if pip_source_file.name in url][0]
    except Exception as e:
        raise PipSourceMetadataException(f"Could not get download URL from pip source file: {e}") from e

def get_checksum_from_pip_source_file(pip_source_file: Path) -> str:
    """Given the path to a pip source file, return the files checksum.

    Args:
        pip_source_file (Path): The path to a .tar.gz file containing a pip source distribution.

    Returns:
        str: The checksum of the pip source file.
    """
    if not pip_source_file.exists():
        raise PipSourceMetadataException("File does not exist: %s" % pip_source_file)
    
    return sha256(pip_source_file.read_bytes()).hexdigest()


def get_metadata_from_pip_source(package_name: str, pip_source_file: Path) -> PackageMetadata:
    """Given the path to a pip source file, return a PackageMetadata object.

    Args:
        pip_source_file (Path): The path to a .tar.gz file containing a pip source distribution.

    Returns:
        PackageMetadata: A dictionary of metadata about the package required for the resource stanza.
    """
    if not pip_source_file.exists():
        raise PipSourceMetadataException("File does not exist: %s" % pip_source_file)
    
    try:
        metadata_object = metadata(pip_source_file)
    except Exception as e:
        raise PipSourceMetadataException("Could not get metadata from pip source file: %s" % e)

    return PackageMetadata(
        name=metadata_object.get("Name"),
        homepage=metadata_object.get("Home-page"),
        url=get_download_url_from_pip_source_file(package_name, pip_source_file),
        checksum=get_checksum_from_pip_source_file(pip_source_file),
        checksum_type="sha256"
    )

def research_package(name: str, version=None) -> PackageMetadata:
    """
    Return metadata about a package.
    Given a package name, return a dictionary of metadata about that package.

    Args:
        name (str): The name of the package to look up.
        version (str): The version of the package to look up.
    
    Returns:
        PackageMetadata: A dictionary of metadata about the package.  
    """
    pip_source_dir = os.getenv("PIP_SOURCE_DIR")
    if pip_source_dir:
        if not os.path.exists(pip_source_dir):
            raise PipSourceMetadataException("PIP_SOURCE_DIR does not exist: {}".format(pip_source_dir))
        pip_source_file = Path(pip_source_dir)/"{}.tar.gz".format(name.lower())    
        return get_metadata_from_pip_source(name, pip_source_file)

    with closing(urlopen("https://pypi.io/pypi/{}/json".format(name))) as f:
        reader = codecs.getreader("utf-8")
        pkg_data = json.load(reader(f))

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

    if artefact:
        d['url'] = artefact['url']
        if 'digests' in artefact and 'sha256' in artefact['digests']:
            logging.debug("Using provided checksum for %s", name)
            d['checksum'] = artefact['digests']['sha256']
        else:
            logging.debug("Fetching sdist to compute checksum for %s", name)
            with closing(urlopen(artefact['url'])) as f:
                d['checksum'] = sha256(f.read()).hexdigest()
            logging.debug("Done fetching %s", name)
    else:  # no sdist found
        d['url'] = ''
        d['checksum'] = ''
        warnings.warn("No sdist found for %s" % name)
    d['checksum_type'] = 'sha256'
    return d


def make_graph(pkg):
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
        package_data = research_package(package, dependencies[package]['version'])
        dependencies[package].update(package_data)

    return OrderedDict(
        [(package, dependencies[package]) for package in sorted(dependencies.keys())]
    )


def formula_for(package, also=None):
    also = also or []

    req = pkg_resources.Requirement.parse(package)
    package_name = req.project_name

    nodes = merge_graphs(make_graph(p) for p in [package] + also)
    resources = [value for key, value in nodes.items()
                 if key.lower() != package_name.lower()]

    if package_name in nodes:
        root = nodes[package_name]
    elif package_name.lower() in nodes:
        root = nodes[package_name.lower()]
    else:
        raise Exception("Could not find package {} in nodes {}".format(package, nodes.keys()))

    python = "python" if sys.version_info.major == 2 else "python3"
    return FORMULA_TEMPLATE.render(package=root,
                                   resources=resources,
                                   python=python,
                                   ResourceTemplate=RESOURCE_TEMPLATE)


def resources_for(packages):
    nodes = merge_graphs(make_graph(p) for p in packages)
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
        print(formula_for(args.formula, args.also))
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
        print(resources_for([package] + args.also))
    return 0


if __name__ == '__main__':
    sys.exit(main())

