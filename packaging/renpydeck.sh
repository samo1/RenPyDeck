#!/bin/sh
# Launcher installed at /app/bin/renpydeck inside the Flatpak sandbox.
# Makes the bundled `renpydeck` Python package importable and starts the app.
export PYTHONPATH="/app/share/renpydeck${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m renpydeck "$@"
