#!/usr/bin/env python3
"""Check a Factorio changelog.txt against the format the game parses.

Factorio drops a changelog it cannot parse without a word in the log, and the in-game
"Changelog" button just stays grey. The rules are from
https://lua-api.factorio.com/latest/auxiliary/changelog-format.html

  lua/check-changelog.py [changelog.txt]    default: changelog.txt in the current directory

Prints file:line: level: message and exits 1 on any problem. "error" breaks parsing (a missing separator before the
first version and a repeated version are confirmed in game: the button stays grey); "style" is what the format page
asks to avoid (tabs, trailing spaces), which many released mods have.
"""
import re
import sys
from pathlib import Path

SEPARATOR = "-" * 99
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def check(text):
    problems = []

    def problem(number, message, level="error"):
        problems.append((number, level, message))

    if text.startswith("﻿"):
        problem(1, "byte order mark at the start of the file", "style")
        text = text[1:]
    # CRLF files load in game, so only the line content is checked
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    versions = set()
    version = category = None
    entries = set()
    expect = "separator"  # what the next non-empty line has to be
    previous = None  # kind of the previous line

    for number, line in enumerate(lines, 1):
        if "\t" in line:
            problem(number, "tab character", "style")
        if line != line.rstrip(" "):
            problem(number, "trailing whitespace" if line.strip() else "line of only spaces", "style")

        if line == "":
            if previous == "version":
                problem(number, "empty line right after the Version line")
            previous = "empty"
            continue

        if line == SEPARATOR:
            expect = "version"
            previous = "separator"
            continue
        if set(line) == {"-"}:
            problem(number, f"separator of {len(line)} dashes, must be exactly 99")
            expect = "version"
            previous = "separator"
            continue

        if expect == "version":
            if not line.startswith("Version: "):
                problem(number, "a separator must be followed by a 'Version: ' line")
            else:
                value = line[len("Version: "):]
                match = VERSION.match(value)
                if not match:
                    problem(number, f"version {value!r} is not major.minor.sub")
                elif any(int(part) > 65535 for part in match.groups()):
                    problem(number, f"version {value} has a number above 65535")
                elif value == "0.0.0":
                    problem(number, "version 0.0.0 is not allowed")
                elif value in versions:
                    problem(number, f"version {value} appears twice")
                versions.add(value)
                version, category = value, None
            expect = "body"
            previous = "version"
            continue

        if line.startswith("Version: "):
            problem(number, "Version line without a separator line right before it")
            expect = "body"
            previous = "version"
            continue
        if expect == "separator":
            problem(number, "the file must start with a separator line of 99 dashes")
            expect = "body"

        if line.startswith("Date: "):
            if previous != "version":
                problem(number, "Date line must come right after the Version line")
            previous = "date"
        elif re.match(r"^  [^ ]", line):
            if not line.endswith(":"):
                problem(number, "category line must end with a colon")
            category = line.strip()
            previous = "category"
        elif line.startswith("    - "):
            if category is None:
                problem(number, "entry outside a category")
            key = (version, category, line[len("    - "):])
            if key in entries:
                problem(number, "same entry twice in one category")
            entries.add(key)
            previous = "entry"
        elif re.match(r"^      [^ ]", line) and previous in ("entry", "continuation"):
            previous = "continuation"
        else:
            problem(number, f"not a category (2 spaces), entry (4 spaces and '- ') or continuation "
                            f"(6 spaces): {line.strip()[:40]!r}")
            previous = "other"

    if not versions:
        problem(1, "no version section")
    return problems


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "changelog.txt")
    problems = check(path.read_bytes().decode("utf-8"))
    for number, level, message in problems:
        print(f"{path}:{number}: {level}: {message}")
    errors = sum(1 for _, level, _ in problems if level == "error")
    print(f"changelog: {errors} error(s), {len(problems) - errors} style problem(s) in {path.name}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
