"""Punto de entrada del binario empaquetado con PyInstaller."""

import sys

from themevault.ui.app import main

if __name__ == "__main__":
    sys.exit(main())
