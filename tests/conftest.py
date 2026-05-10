import os
import sys
from unittest.mock import MagicMock

# Prevent main.py from failing to import the GCP runtime decorator
sys.modules.setdefault("functions_framework", MagicMock())

# Allow `from main import ...` in test_main.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "functions", "membership_sync"))
