import pytest


@pytest.fixture
def demo_assets(tmp_path, monkeypatch):
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    for name in ("index.html", "app.css", "app.js"):
        (demo_dir / name).write_text(name)

    data_dir = demo_dir / "data"
    data_dir.mkdir()
    (data_dir / "index.js").write_text("const demo = true;")

    monkeypatch.setattr("qq.explorer.publish.DEMO_DIR", demo_dir)
    return demo_dir
