from typing import List

class ReadableFields:
    rank: str
    word: str
    part_of_speech: str
    definition: str
    spanish: str
    english: str
    freq: str

    def __init__(self, fields: List) -> None:
        self.rank = fields[0]
        self.word = fields[1]
        self.part_of_speech = fields[2]
        self.definition = fields[3]
        self.spanish = fields[4]
        self.english = fields[5]
        self.freq = fields[6]
    
    def retrieve(self) -> List:
        return [
            self.rank,
            self.word,
            self.part_of_speech,
            self.definition,
            self.spanish,
            self.english,
            self.freq
        ]