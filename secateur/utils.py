from enum import Enum

class ErrorCode(Enum):
    RATE_LIMITED_EXCEEDED = 88
    USER_SUSPENDED = 63
    USER_NOT_FOUND = 50

    @classmethod
    def from_exception(cls, twitter_error_exception):
        code = twitter_error_exception.message[0]["code"]
        try:
            return cls(code)
        except ValueError:
            return code
