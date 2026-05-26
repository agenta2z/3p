"""
Pytest configuration for SciencePythonUtils tests.

This file ensures that the src directory is added to the Python path
so that test modules can import from python_utils.
"""
import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))
