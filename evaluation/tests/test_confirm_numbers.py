import pathlib

from confirm_numbers import build_index, collect


def test_collect_lists_files_in_sorted_order_whatever_order_the_directory_gives(tmp_path, monkeypatch):
    for name in ("b/run.txt", "a/run.txt", "c.csv", "a/early.txt"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("accuracy 0.8125\n")
    listed = sorted(tmp_path.rglob("*"))
    monkeypatch.setattr(pathlib.Path, "rglob", lambda self, pattern: iter(reversed(listed)))

    groups = collect(tmp_path)

    assert groups["data"] == sorted(groups["data"])
    assert [path.relative_to(tmp_path).as_posix() for path in groups["data"]] == [
        "a/early.txt", "a/run.txt", "b/run.txt", "c.csv"]


def test_a_value_in_two_files_is_reported_in_the_first_by_path(tmp_path, monkeypatch):
    for name in ("results/log.txt", "code/dump/log.txt"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("f1 0.8125\n")
    listed = sorted(tmp_path.rglob("*"))
    monkeypatch.setattr(pathlib.Path, "rglob", lambda self, pattern: iter(reversed(listed)))

    groups = collect(tmp_path)
    index, _ = build_index(groups["data"], tmp_path)

    assert index["0.8125"][0].endswith("code/dump/log.txt")
