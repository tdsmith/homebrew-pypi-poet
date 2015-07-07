homebrew-pypi-poet
==================

|Build Status| |Code Health| |PyPI page| |MIT license|

Invoked like ``poet foo`` for some package foo **which is presently
installed in sys.path**, determines which packages foo and its
dependents depend on, downloads them from pypi and computes their
checksums, and spits out Homebrew resource stanzas.

``poet -f foo`` will give you a complete Homebrew formula.

``poet -s foo`` will write a resource stanza for a single package
``foo``, which does not need to be installed, without considering its
dependencies.

``poet`` will use the versions of the packages that you presently have
installed. If a package it wants to reference is not installed, the
latest version on pypi will be downloaded and checksummed and its
dependencies will **not** be considered.

The easiest way to use ``poet`` is to create a virtualenv, use pip or
setuptools to install the target package and its dependencies in the
virtualenv, and then ``pip install homebrew-pypi-poet`` and run ``poet``
inside the virtualenv.

Usage is like:

::

    usage: poet [-h] [--single package [package ...] | --formula package |
                      --resources package]

    Generate Homebrew resource stanzas for pypi packages and their dependencies.

    optional arguments:
      -h, --help            show this help message and exit
      --single package [package ...], -s package [package ...]
                            Generate a resource stanza for one or more packages,
                            without considering dependencies.
      --formula package, -f package
                            Generate a complete formula for a pypi package with
                            its recursive pypi dependencies as resources.
      --resources package, -r package
                            Generate resource stanzas for a package and its
                            recursive dependencies (default).

License
-------

homebrew-pypi-poet is offered under the MIT license.

Contributors
------------

homebrew-pypi-poet is maintained by Tim D. Smith. Robson Peixoto,
Alessio Bogon, and Julien Maupetit are thanked for their helpful contributions!

.. |Build Status| image:: https://travis-ci.org/tdsmith/homebrew-pypi-poet.svg?branch=master
   :target: https://travis-ci.org/tdsmith/homebrew-pypi-poet
.. |Code Health| image:: https://landscape.io/github/tdsmith/homebrew-pypi-poet/master/landscape.svg?style=flat
   :target: https://landscape.io/github/tdsmith/homebrew-pypi-poet/master
.. |PyPI page| image:: https://img.shields.io/pypi/dm/homebrew-pypi-poet.svg
   :target: https://pypi.python.org/pypi/homebrew-pypi-poet
.. |MIT license| image:: https://img.shields.io/pypi/l/homebrew-pypi-poet.svg
   :target: https://github.com/tdsmith/homebrew-pypi-poet/blob/master/LICENSE
