# homebrew-pypi-poet

Invoked like `poet foo` for some package foo **which is presently
installed in sys.path**, determines which packages foo and its dependents
depend on, downloads them from pypi and computes their checksums, and
spits out Homebrew resource stanzas.

`poet -f foo` will give you a complete Homebrew formula.

`poet` will use the versions of the packages that you presently have installed.
The most correct way to use `poet` is to create a virtualenv, use pip or setuptools to install the target package in the virtualenv, and then `pip install homebrew-pypi-poet` and run `poet` inside the virtualenv.
