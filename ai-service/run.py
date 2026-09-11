"""Convenience runner for Nagar Nayan AI Video Intelligence Service."""

from __future__ import annotations

import os
import sys

# Ensure ai-service root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from app.main import main

if __name__ == "__main__":
    main()
