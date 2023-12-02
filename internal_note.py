from anki.storage import Collection as AnkiCollection
from anki.notes import Note
from anki.models import NotetypeDict

class InternalNote:
    coll: AnkiCollection
    model: NotetypeDict

    rank: str
    word: str
    part_of_speech: str
    definition: str
    spanish: str
    english: str
    freq: str

    def __init__(self, coll: AnkiCollection, model: NotetypeDict, original_note: Note) -> None:
        self.coll = coll
        self.model = model
        fields = original_note.fields
        self.rank = fields[0]
        self.word = fields[1]
        self.part_of_speech = fields[2]
        self.definition = fields[3]
        self.spanish = fields[4]
        self.english = fields[5]
        self.freq = fields[6]
    
    def create(self) -> Note:
        new_note = self.coll.new_note(self.model)
        new_note.fields = [
            self.rank,
            self.word,
            self.part_of_speech,
            self.definition,
            self.spanish,
            self.english,
            self.freq
        ]
        return new_note