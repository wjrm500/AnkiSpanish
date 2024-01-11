from enum import Enum


class Language(Enum):
    ENGLISH = ("english", "en")
    FRENCH = ("french", "fr")
    GERMAN = ("german", "de")
    ITALIAN = ("italian", "it")
    PORTUGUESE = ("portuguese", "pt")
    SPANISH = ("spanish", "es")

    def __init__(self, language_name: str, iso_code: str) -> None:
        self.language_name = language_name  # The "name" attribute is already taken by Enum
        self.iso_code = iso_code

    @staticmethod
    def options() -> list[str]:
        return [v.language_name for v in Language.__members__.values()]

    @staticmethod
    def from_language_name(language_name: str) -> "Language":
        return Language.__members__[language_name.upper()]
