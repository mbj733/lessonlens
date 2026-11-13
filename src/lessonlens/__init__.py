"""LessonLens: slide deck -> grounded 3D scene.

The single source of truth between pipeline stages is ``scene.json``:
web renderer, USDZ exporter and the evaluator all read it and nothing else.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
