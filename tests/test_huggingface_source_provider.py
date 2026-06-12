from qq.sources.providers import HuggingFaceDatasetTagsSourceProvider


def make_provider(tmp_path):
    return HuggingFaceDatasetTagsSourceProvider(
        name="huggingface_dataset_tags",
        sources_dir=tmp_path,
        source_url="https://huggingface.co/api/datasets?limit=1000&expand=tags",
        filename="tags.json",
        license="See Hugging Face datasets themselves.",
    )


def test_huggingface_provider_counts_language_tags_across_dataset_pages(tmp_path, monkeypatch):
    provider = make_provider(tmp_path)
    pages = [
        (
            [{"tags": ["language:nl"]}, {"tags": ["language:nld", "license:mit"]}],
            '<next>; rel="next"',
            "https://example.test/a",
        ),
        ([{"tags": ["language:nl", "language:nld"]}, {"tags": ["language:nl"]}], None, "https://example.test/b"),
    ]
    calls = []

    def fake_fetch_dataset_page(url, headers):
        calls.append(url)
        return pages[len(calls) - 1]

    monkeypatch.setattr(provider, "_fetch_dataset_page", fake_fetch_dataset_page)

    data = provider._fetch_language_tag_counts()

    assert data == {
        "language": [
            {"id": "language:nl", "dataset_count": 3},
            {"id": "language:nld", "dataset_count": 2},
        ]
    }
    assert calls == ["https://huggingface.co/api/datasets?limit=1000&expand=tags", "https://example.test/next"]


def test_huggingface_provider_parses_rate_limit_header():
    assert HuggingFaceDatasetTagsSourceProvider._ratelimit_value('"api";r=12;t=240', "r") == 12
    assert HuggingFaceDatasetTagsSourceProvider._ratelimit_value('"api";r=12;t=240', "t") == 240
    assert HuggingFaceDatasetTagsSourceProvider._ratelimit_value('"api";r=12;t=240', "q") is None
