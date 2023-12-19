from app.synonym import SynonymChecker


def test_get_synonyms():
    synonyms = SynonymChecker.get_synonyms("huge", pos="a")
    assert "immense" in synonyms
    assert "vast" in synonyms

    synonyms = SynonymChecker.get_synonyms("qwerty", pos="n")
    assert len(synonyms) == 0


def test_are_synonymous():
    assert SynonymChecker.are_synonymous("huge", "immense", pos="a")
    assert not SynonymChecker.are_synonymous("happy", "sad", pos="a")


def test_mark_synonymous_words():
    words = ["huge", "immense", "vast", "small", "little"]
    marks = SynonymChecker.mark_synonymous_words(words, pos="a")
    expected_marks = [0, 1, 1, 0, 1]  # 1 means synonymous with an earlier word
    assert marks == expected_marks
