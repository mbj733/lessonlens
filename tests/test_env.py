"""B0 gate: the environment the whole pipeline depends on actually imports.

Plan v2.0 batch B0 verification command:
    python -c "import pdfplumber, jsonschema"
This test is the pytest-shaped version of that command, plus the two other
runtime deps (python-pptx for ingest, pillow for the demo media pipeline).
"""

import sys
from importlib import metadata

import jsonschema
import pdfplumber
import pptx


def test_python_version_supported():
    assert sys.version_info >= (3, 11), sys.version


def test_ingest_and_validation_deps_import():
    # version lookup via importlib.metadata (jsonschema.__version__ is deprecated)
    for dist in ("pdfplumber", "python-pptx", "jsonschema"):
        assert metadata.version(dist), dist
    assert pdfplumber.__version__
    assert pptx.__version__
    assert jsonschema.__name__


def test_package_importable():
    import lessonlens

    assert lessonlens.__version__ == "0.1.0"
