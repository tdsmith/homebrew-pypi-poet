import argparse
import re
import sys

from .version import __version__

REGEXP = r"""([ ]+resource "(.+?)".+?end)"""


def lint(buf):
    matches = re.findall(REGEXP, buf, re.MULTILINE | re.DOTALL)
    matches = {key: value for value, key in matches}
    output = []
    for i in sorted(matches.keys()):
        output.append(matches[i])
    return '\n\n'.join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Alphabetize and tidy Homebrew resource stanzas.")
    parser.add_argument("-V", "--version", action="version",
                        version='homebrew-pypi-poet {}'.format(__version__))
    parser.add_argument("file", help="File containing resource stanzas, "
                        "or - for standard input.")
    args = parser.parse_args()
    if args.file == "-":
        buf = sys.stdin.read()
    else:
        with open(args.file, "r") as f:
            buf = f.read()
    print(lint(buf))
