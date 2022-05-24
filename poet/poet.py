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

import boto3
import botocore.exceptions
import json
import logging
import os
import sys
from urllib.parse import urlparse, urlunparse
import warnings
from dataclasses import dataclass, field
from typing import Optional

from packaging.version import Version, parse, InvalidVersion


import pkg_resources

from .templates import FORMULA_TEMPLATE, RESOURCE_TEMPLATE, PRIVATE_RESOURCE_TEMPLATE
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

class PackageNotFoundWarning(UserWarning):
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
    homepage: Optional[str] = None
    url: Optional[str] = None
    checksum: Optional[str] = None
    checksum_type: str = field(default="sha256")
    version: Optional[Version] = None
    package_name: Optional[str] = None

    def __post_init__(self):
        self.package_name = self.name.replace(".", "-")

    def asdict(self):
        exclude_keys = ["version"]
        return {k: v for k, v in self.__dict__.items() if k not in exclude_keys}

@dataclass
class CodeArtifactMetadata(PackageMetadata):
    repository: Optional[str] = os.getenv("AWS_CODEARTIFACT_REPOSITORY", None)
    domain: Optional[str] = os.getenv("AWS_CODEARTIFACT_DOMAIN", None)
    owner: Optional[str] = os.getenv("AWS_CODEARTIFACT_DOMAIN_OWNER", None)
    client: Optional[boto3.session.Session.client] = None

    def __post_init__(self):
        # If the version is not specified, get the latest version
        super().__post_init__()
        self.client = boto3.client("codeartifact")
        if self.version is None:
            self.version = self.get_latest_version()
        self.homepage = self.get_metadata("homePage")
        self.base_url = self.get_base_url()
        self.checksum = self.get_checksum()
        self.url = self.get_download_url()

    def get_base_url(self) -> str:
        """
        Get the base URL for the pip source distribution.

        Returns:
            str: The base URL for the pip source distribution.
        """
        try:
            response = self.client.get_repository_endpoint(
                domain=self.domain,
                domainOwner=self.owner,
                repository=self.repository,
                format="pypi",
            )
        except botocore.exceptions.ClientError as client_error:
            if client_error.response["Error"]["Code"] == "RepositoryNotFound":
                raise PackageVersionNotFoundWarning(
                    f"Package version {self.version} not found for {self.name}"
                )
            raise client_error
        try:
            return response["repositoryEndpoint"]
        except KeyError as e:
            logging.warning("Could not find key {} in response".format(e))
            return None

    def get_download_url(self) -> str:
        """Get the download URL for the pip source distribution.

        Returns:
            str: The download URL for the pip source distribution.
        """
        base_url = urlparse(f"{self.get_base_url()}simple/{self.package_name}/{self.version}/{self.name}-{self.version}.tar.gz")
        return urlunparse(base_url)

    def get_checksum(self) -> str:
        """
        Get the checksum for the pip source distribution.

        Returns:
            str: The checksum for the pip source distribution.
        """
        try:
            response = self.client.list_package_version_assets(
                domain=self.domain,
                domainOwner=self.owner,
                repository=self.repository,
                format="pypi",
                package=self.package_name,
                packageVersion=self.version,
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "PackageVersionNotFound":
                raise PackageVersionNotFoundWarning(
                    f"Package version {self.version} not found for {self.name}"
                )
            raise e
        
        try:
            tar_ball = [
                asset for asset in response["assets"] if ".tar.gz" in asset["name"]
            ][0]
            return tar_ball["hashes"]["SHA-256"]
        except KeyError as key_error:
            raise PipSourceMetadataException(
                f"Could not find checksum for {self.name} version {self.version}"
            ) from key_error

    def get_metadata(self, key: str) -> str:
        """Get a metadata value from the pip source distribution.

        Args:
            key (str): The key to get from metadata

        Returns:
            str: The value of the key.
        """
        try:
            response = self.client.describe_package_version(
                domain=self.domain,
                domainOwner=self.owner,
                repository=self.repository,
                format="pypi",
                package=self.package_name,
                packageVersion=self.version,
            )
        except botocore.exceptions.ClientError as client_error:
            if client_error.response["Error"]["Code"] == "PackageVersionNotFound":
                raise PackageVersionNotFoundWarning(
                    f"Package version {self.version} not found for {self.name}"
                )
            raise client_error
        
        try:
            return response["packageVersion"][key]
        except KeyError as key_error:
            logging.warning("Could not find key {} in response: {}".format(key, key_error))
            return None

    def get_latest_version(self) -> str:
        """Get the latest version of the package.

        Returns:
            version (str) : The latest version of the package.
        """
        try:
            response = self.client.list_package_versions(
                domain=self.domain,
                domainOwner=self.owner,
                repository=self.repository,
                format="pypi",
                package=self.package_name,
                status="Published",
                sortBy="PUBLISHED_TIME",
            )
        except botocore.exceptions.ClientError as client_error:
            if client_error.response["Error"]["Code"] == "PackageNotFound":
                raise PackageNotFoundWarning(f"Package {self.name} not found")
            raise client_error
        
        try:
            return response["versions"][0]["version"]
        except KeyError as key_error:
            logging.warning("Could not find latest version for {}. Error: {}".format(self.name, key_error))
            return None

    
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
    try:
        parse(version)
    except TypeError as type_error:
        logging.warning(f"Could not parse version {version}: {type_error}")
        version = None
    except InvalidVersion as invalid_version:
        logging.warn("Invalid version: %s", invalid_version)
        version = None

    code_artifact_repo = os.getenv("AWS_CODEARTIFACT_REPOSITORY", None)

    if code_artifact_repo is not None:
        logging.warning("Using AWS CodeArtifact repository {} to get package metadata for {}".format(code_artifact_repo, name))
        package_metadata = CodeArtifactMetadata(name=name, version=version)
        return package_metadata.asdict()
    else:
        with closing(urlopen("https://pypi.io/pypi/{}/json".format(name))) as f:
            reader = codecs.getreader("utf-8")
            pkg_data = json.load(reader(f))

        d = {}
        d["name"] = pkg_data["info"]["name"]
        d["homepage"] = pkg_data["info"].get("home_page", "")
        artefact = None
        if version:
            for pypi_version in pkg_data["releases"]:
                if pkg_resources.safe_version(pypi_version) == version:
                    for version_artefact in pkg_data["releases"][pypi_version]:
                        if version_artefact["packagetype"] == "sdist":
                            artefact = version_artefact
                            break
            if artefact is None:
                warnings.warn(
                    "Could not find an exact version match for "
                    "{} version {}; using newest instead".format(name, version),
                    PackageVersionNotFoundWarning,
                )

        if artefact is None:  # no version given or exact match not found
            for url in pkg_data["urls"]:
                if url["packagetype"] == "sdist":
                    artefact = url
                    break

        if artefact:
            d["url"] = artefact["url"]
            if "digests" in artefact and "sha256" in artefact["digests"]:
                logging.debug("Using provided checksum for %s", name)
                d["checksum"] = artefact["digests"]["sha256"]
            else:
                logging.debug("Fetching sdist to compute checksum for %s", name)
                with closing(urlopen(artefact["url"])) as f:
                    d["checksum"] = sha256(f.read()).hexdigest()
                logging.debug("Done fetching %s", name)
        else:  # no sdist found
            d["url"] = ""
            d["checksum"] = ""
            warnings.warn("No sdist found for %s" % name)
        d["checksum_type"] = "sha256"
        return d


def make_graph(pkg):
    """Returns a dictionary of information about pkg & its recursive deps.

    Given a string, which can be parsed as a requirement specifier, return a
    dictionary where each key is the name of pkg or one of its recursive
    dependencies, and each value is a dictionary returned by research_package.
    (No, it's not really a graph.)
    """
    ignore = ["argparse", "pip", "setuptools", "wsgiref"]
    pkg_deps = recursive_dependencies(pkg_resources.Requirement.parse(pkg))

    dependencies = {key: {} for key in pkg_deps if key not in ignore}
    installed_packages = pkg_resources.working_set
    versions = {package.key: package.version for package in installed_packages}
    for package in dependencies:
        try:
            dependencies[package]["version"] = versions[package]
        except KeyError:
            warnings.warn(
                "{} is not installed so we cannot compute "
                "resources for its dependencies.".format(package),
                PackageNotInstalledWarning,
            )
            dependencies[package]["version"] = None

    for package in dependencies:
        package_data = research_package(package, dependencies[package]["version"])
        dependencies[package].update(package_data)

    return OrderedDict(
        [(package, dependencies[package]) for package in sorted(dependencies.keys())]
    )


def formula_for(package, also=None):
    also = also or []

    req = pkg_resources.Requirement.parse(package)
    package_name = req.project_name

    nodes = merge_graphs(make_graph(p) for p in [package] + also)
    resources = [
        value for key, value in nodes.items() if key.lower() != package_name.lower()
    ]

    if package_name in nodes:
        root = nodes[package_name]
    elif package_name.lower() in nodes:
        root = nodes[package_name.lower()]
    else:
        raise Exception(
            "Could not find package {} in nodes {}".format(package, nodes.keys())
        )

    python = "python" if sys.version_info.major == 2 else "python3"
    return FORMULA_TEMPLATE.render(
        package=root,
        resources=resources,
        python=python,
        ResourceTemplate=RESOURCE_TEMPLATE,
    )


def resources_for(packages, using=False):
    nodes = merge_graphs(make_graph(p) for p in packages)
    return (
        "\n\n".join(
            [RESOURCE_TEMPLATE.render(resource=node) for node in nodes.values()]
        )
        if not using
        else "\n\n".join(
            [PRIVATE_RESOURCE_TEMPLATE.render(resource=node, using=using) for node in nodes.values()]
        )
    )


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
                    "{r.name} {r.version}; using the former.".format(
                        l=result[key], r=g[key]
                    ),
                    ConflictingDependencyWarning,
                )
    return OrderedDict([k, result[k]] for k in sorted(result.keys()))


def main():
    parser = argparse.ArgumentParser(
        description="Generate Homebrew resource stanzas for pypi packages "
        "and their dependencies."
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--single",
        "-s",
        metavar="package",
        nargs="+",
        help="Generate a resource stanza for one or more packages, "
        "without considering dependencies.",
    )
    actions.add_argument(
        "--formula",
        "-f",
        metavar="package",
        help="Generate a complete formula for a pypi package with its "
        "recursive pypi dependencies as resources.",
    )
    actions.add_argument(
        "--resources",
        "-r",
        metavar="package",
        help="Generate resource stanzas for a package and its recursive "
        "dependencies (default).",
    )
    parser.add_argument("--using", "-u", metavar="using", help="Add a CurlDownloadStrategy to the private resources.")
    parser.add_argument(
        "--also",
        "-a",
        metavar="package",
        action="append",
        default=[],
        help="Specify an additional package that should be added to the "
        "resource list with its recursive dependencies. May not be used "
        "with --single. May be specified more than once.",
    )
    parser.add_argument("package", help=argparse.SUPPRESS, nargs="?")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="homebrew-pypi-poet {}".format(__version__),
    )
    args = parser.parse_args()

    if (args.formula or args.resources) and args.package:
        print("--formula and --resources take a single argument.", file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 1

    if args.also and args.single:
        print("Can't use --also with --single", file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 1

    if args.formula:
        print(formula_for(args.formula, args.also))
    elif args.single:
        for i, package in enumerate(args.single):
            data = research_package(package)
            print(RESOURCE_TEMPLATE.render(resource=data))
            if i != len(args.single) - 1:
                print()
    else:
        package = args.resources or args.package
        if not package:
            parser.print_usage(sys.stderr)
            return 1

        if args.using:
            logging.warning("Using private repo urls: {}".format(args.using))
            print(resources_for([package] + args.also, using=args.using))
        else:
            print(resources_for([package] + args.also))
    return 0


if __name__ == "__main__":
    sys.exit(main())
