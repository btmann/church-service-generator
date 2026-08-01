"""Shared fixtures and helpers for the church-service-generator test suite."""
import ast
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def extract_functions(source_path, names, extra_globals=None):
    """Pull specific top-level function defs out of a script and exec them
    in an isolated namespace.

    ui.py and pages/2_Song_Processing.py are Streamlit *scripts*: they call
    st.* at module scope, so `import ui` runs the whole page (and fails
    outside a live Streamlit session). This extracts just the named
    functions' source and execs it standalone, so their pure logic can be
    unit tested without booting Streamlit.
    """
    tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    wanted = set(names)
    available = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    missing = wanted - available
    if missing:
        raise ValueError(f"Function(s) not found in {source_path}: {missing}")

    namespace = dict(extra_globals or {})
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            module = ast.Module(body=[node], type_ignores=[])
            code = compile(module, filename=str(source_path), mode="exec")
            exec(code, namespace)
    return {name: namespace[name] for name in names}


class FakeSessionState(dict):
    """Minimal stand-in for st.session_state supporting both dict and attr access."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value


def make_fake_streamlit(session_state=None):
    fake_st = MagicMock(name="streamlit")
    fake_st.session_state = session_state if session_state is not None else FakeSessionState()
    return fake_st


@pytest.fixture
def fake_streamlit():
    return make_fake_streamlit()


@pytest.fixture
def sample_service_spec():
    return json.loads((ROOT / "worship" / "sample.json").read_text(encoding="utf-8"))
