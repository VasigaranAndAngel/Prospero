import re
from collections.abc import Callable

TValidator = Callable[[str], bool]


class Validators:
    @staticmethod
    def int(val: str) -> bool:
        return val.isdecimal()

    @staticmethod
    def float(val: str) -> bool:
        return bool(re.match(r"^(?=.*\d)-?\d*?\.?\d*$", val))

    @staticmethod
    def percentage(val: str) -> bool:
        if val.endswith("%"):
            val = val.removesuffix("%")
        return Validators.float(val)

    @staticmethod
    def regex(_: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def color(_: str) -> bool:
        raise NotImplementedError
