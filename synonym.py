import argparse
from typing import List, Set

from nltk.corpus import wordnet
from nltk.corpus.reader.wordnet import Lemma, Synset


class SynonymChecker:
    """A class with various methods related to checking if words are synonyms."""

    @staticmethod
    def get_synonyms(word: str, pos: str = "n") -> Set[str]:
        """Returns a set of synonyms for the given word."""
        synonyms = set()
        for synset in wordnet.synsets(word, pos=pos):
            assert isinstance(synset, Synset)
            for lemma in synset.lemmas():
                assert isinstance(lemma, Lemma)
                synonyms.add(lemma.name())
        return synonyms

    @staticmethod
    def are_synonymous(word1: str, word2: str, pos: str = "n") -> bool:
        """Returns True if the two words are synonyms, False otherwise."""
        synonyms_word1 = SynonymChecker.get_synonyms(word1, pos=pos)
        synonyms_word2 = SynonymChecker.get_synonyms(word2, pos=pos)
        return bool(synonyms_word1 & synonyms_word2)

    @staticmethod
    def mark_synonymous_words(words: List[str], pos: str = "n") -> List[int]:
        """
        Returns a list of marks, where a mark of 1 indicates that the corresponding word is
        synonymous with an earlier word in the list.
        """
        marks = [0] * len(words)
        synonym_groups = [SynonymChecker.get_synonyms(word, pos) for word in words]
        for i in range(len(synonym_groups)):
            comparator = synonym_groups[i]
            for j in range(len(synonym_groups))[i + 1:]:
                comparand = synonym_groups[j]
                if comparator & comparand:
                    marks[j] = 1
        return marks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check if words are synonyms")
    parser.add_argument("--words", nargs=2, dest="words", help="Words to check")
    parser.add_argument("--pos", dest="pos", help="Part of speech", default="n")
    args = parser.parse_args()
    word1 = args.words[0] if args.words else input("Enter first word: ")
    word2 = args.words[1] if args.words else input("Enter second word: ")
    print(SynonymChecker.are_synonymous(word1, word2, args.pos))
