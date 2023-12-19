class RateLimitException(Exception):
    pass


class RedirectException(Exception):
    response_url: str

    def __init__(self, message: str, response_url: str) -> None:
        super().__init__(message)
        self.response_url = response_url
