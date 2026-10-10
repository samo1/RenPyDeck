#!/usr/bin/env python3
"""Set RenPyDeck's version for a release.

Usage: packaging/set-version.py VERSION [DATE]

Writes VERSION into the two places that carry it:

* ``__version__`` in ``src/renpydeck/__init__.py``;
* a ``<release>`` entry in the AppStream metainfo — the version a software
  store shows, and what tells it that an update is newer. A new entry is added
  at the top of ``<releases>`` dated DATE (default: today, UTC). An entry for
  VERSION that is already there — written by hand, with release notes — is
  kept as it is.

VERSION must be ``MAJOR.MINOR.PATCH`` and newer than every release already in
the metainfo, so a release can never go backwards. The files are edited as
text, leaving their comments and layout alone.
"""

import datetime
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INIT = PROJECT_ROOT / "src" / "renpydeck" / "__init__.py"
METAINFO = PROJECT_ROOT / "packaging" / "sk.meluzina.RenPyDeck.metainfo.xml"

VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")


def parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def set_init_version(version: str) -> None:
    text = INIT.read_text(encoding="utf-8")
    text, count = re.subn(
        r'^__version__ = "[^"]*"$', f'__version__ = "{version}"', text, flags=re.M
    )
    if count != 1:
        sys.exit(f"{INIT}: no __version__ line to update")
    INIT.write_text(text, encoding="utf-8")


def add_metainfo_release(version: str, date: str) -> None:
    text = METAINFO.read_text(encoding="utf-8")
    released = re.findall(r'<release\s+version="([^"]+)"', text)
    if version in released:
        return  # written by hand, notes and all
    newer = [other for other in released if parse(other) >= parse(version)]
    if newer:
        sys.exit(
            f"{version} is not newer than the release(s) {', '.join(newer)} "
            f"already in {METAINFO.name}"
        )

    match = re.search(r"^(\s*)<releases>\n", text, flags=re.M)
    if match is None:
        sys.exit(f"{METAINFO}: no <releases> element")
    indent = match.group(1) + "  "
    entry = f'{indent}<release version="{version}" date="{date}" />\n'
    METAINFO.write_text(text[: match.end()] + entry + text[match.end() :], encoding="utf-8")


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__.split("\n\n")[1])
    version = sys.argv[1]
    if not VERSION_PATTERN.fullmatch(version):
        sys.exit(f"Version {version!r} is not of the form MAJOR.MINOR.PATCH")
    if len(sys.argv) == 3:
        date = sys.argv[2]
    else:
        date = datetime.datetime.now(datetime.UTC).date().isoformat()

    add_metainfo_release(version, date)
    set_init_version(version)


if __name__ == "__main__":
    main()
