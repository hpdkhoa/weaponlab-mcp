import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def demo(tmp_path, monkeypatch):
    """A fresh copy of the demo project, in use."""
    dst = tmp_path / "demo"
    shutil.copytree(ROOT / "examples" / "demo", dst, ignore=shutil.ignore_patterns("work"))
    cfg = json.loads((dst / "weaponlab.json").read_text())
    cfg["probe"]["command"] = [sys.executable, str(dst / "probe" / "demo_probe.py"), "{job}"]
    (dst / "weaponlab.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("WEAPONLAB_PROJECT", str(dst))
    from weaponlab import config
    config.reset()
    yield dst
    config.reset()


def trust(*providers):
    from weaponlab import gate as G
    for p in providers:
        G.record_eval(p, {"suite": "test", "caught": 1, "faults": 1, "passed_good": 1, "good": 1})
