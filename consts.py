import enum

class PrintColour(enum.Enum):
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    LIGHT_GRAY = "\033[37m"
    END = "\033[0m"

    def __str__(self):
        return self.value