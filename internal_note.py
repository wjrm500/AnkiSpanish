from anki.storage import Collection as AnkiCollection
from anki.notes import Note as AnkiNote
from anki.models import NotetypeDict as AnkiModel

"""
A class that internally represents an existing Anki note, allowing us to more easily access and
manipulate the note's fields to help create a new note.
"""
class InternalNote:
    coll: AnkiCollection
    model: AnkiModel

    rank: str
    word: str
    part_of_speech: str
    definition: str
    spanish: str
    english: str
    freq: str

    def __init__(self, coll: AnkiCollection, model: AnkiModel, original_note: AnkiNote) -> None:
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
    
    """
    Creates a new Anki note object using the fields of the InternalNote object.
    """
    def create(self) -> AnkiNote:
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