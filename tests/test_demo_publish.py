import pytest

from qq.explorer.publish import publish_demo


def test_publish_demo_refuses_existing_target_without_overwrite(tmp_path):
    target = tmp_path / "site"
    target.mkdir()
    (target / "old.txt").write_text("old")

    with pytest.raises(FileExistsError, match=str(target.resolve())):
        publish_demo(target, skip_export=True)

    assert (target / "old.txt").read_text() == "old"


def test_publish_demo_overwrites_existing_target_when_allowed(tmp_path):
    target = tmp_path / "site"
    target.mkdir()
    (target / "old.txt").write_text("old")

    result = publish_demo(target, skip_export=True, overwrite=True)

    assert result == target.resolve()
    assert (target / "index.html").exists()
    assert not (target / "old.txt").exists()
