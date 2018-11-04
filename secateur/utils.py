from enum import Enum

class ErrorCode(Enum):
    RATE_LIMITED_EXCEEDED = 88
    USER_SUSPENDED = 63
    USER_NOT_FOUND = 50
    NOT_MUTING_SPECIFIED_USER = 272
    PAGE_DOES_NOT_EXIST = 34

    @classmethod
    def from_exception(cls, twitter_error_exception):
        code = twitter_error_exception.message[0]["code"]
        try:
            return cls(code)
        except ValueError:
            return code
