from qq import Database, IdType


def test_packaged_database_includes_joshi_ratings():
    db = Database.load()

    assert db.get("nl").joshi_rating == 4
    assert db.get("en").joshi_rating == 5
    assert db.get("cmn").joshi_rating == 5
    assert db.get("ell", IdType.ISO_639_3).joshi_rating == 3
    assert db.get("gree1276", IdType.GLOTTOCODE).joshi_rating is None
    assert db.get("bel", IdType.ISO_639_3).joshi_rating == 3
