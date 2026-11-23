#!/usr/bin/env python3
"""Check required and forbidden regular expressions in a Factorio log."""
import argparse
import re
import sys


def parse_patterns(value):
    patterns = []
    for expression in value.splitlines():
        if not expression.strip():
            continue
        try:
            patterns.append((expression, re.compile(expression)))
        except re.error as error:
            sys.stderr.write("error: bad pattern %s: %s\n" % (expression, error))
            raise SystemExit(2)
    return patterns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, help="Factorio log file")
    parser.add_argument("--required", default="", help="Regular expressions that must match the log")
    parser.add_argument("--forbidden", default="", help="Regular expressions that must not match the log")
    args = parser.parse_args()

    required = parse_patterns(args.required)
    forbidden = parse_patterns(args.forbidden)
    try:
        with open(args.log, encoding="utf-8", errors="replace") as log_file:
            lines = list(log_file)
    except OSError as error:
        sys.stderr.write("error: cannot read log %s: %s\n" % (args.log, error))
        return 2

    failed = False
    for expression, pattern in required:
        if not any(pattern.search(line) for line in lines):
            print("missing in the log: %s" % expression)
            failed = True

    for expression, pattern in forbidden:
        for line in lines:
            if pattern.search(line):
                print("forbidden in the log: %s: %s" % (expression, line.rstrip("\r\n")[:300]))
                failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
