"""Allow running the package with ``python -m renpydeck``."""

from .app import main

if __name__ == "__main__":
    raise SystemExit(main())
