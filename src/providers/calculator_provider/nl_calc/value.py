from typing import override

from .unit_relations import UNITS, convertible


class Value:
    def __init__(self, amount: int | float, unit: str | None = None) -> None:
        if unit is not None and unit not in UNITS:
            raise ValueError(f"Unit named '{unit}' not found.")

        self.amount: int | float = amount
        self.unit: str | None = unit

    def __add__(self, other: "Value | int | float") -> "Value":
        if isinstance(other, (int, float)):
            return Value(self.amount + other, self.unit)
        else:
            if self.unit == other.unit:
                return Value(self.amount + other.amount, self.unit)
            else:
                return Value(self.amount + other.convert_unit(self.unit).amount, self.unit)

    def __sub__(self, other: "Value | int | float") -> "Value":
        if isinstance(other, (int, float)):
            return Value(self.amount - other, self.unit)
        else:
            if self.unit == other.unit:
                return Value(self.amount - other.amount, self.unit)
            else:
                return Value(self.amount - other.convert_unit(self.unit).amount, self.unit)

    def __mul__(self, other: "Value | int | float") -> "Value":
        if isinstance(other, (int, float)):
            return Value(self.amount * other, self.unit)
        else:
            if self.unit == other.unit:
                return Value(self.amount * other.amount, self.unit)
            else:
                return Value(self.amount * other.convert_unit(self.unit).amount, self.unit)

    def __truediv__(self, other: "Value | int  | float") -> "Value":
        if isinstance(other, (int, float)):
            return Value(self.amount / other, self.unit)
        else:
            if self.unit == other.unit:
                return Value(self.amount / other.amount, self.unit)
            else:
                return Value(self.amount / other.convert_unit(self.unit).amount, self.unit)

    def __mod__(self, other: "Value | int | float") -> "Value":
        if isinstance(other, (int, float)):
            return Value(self.amount % other, self.unit)
        else:
            if self.unit == other.unit:
                return Value(self.amount % other.amount, self.unit)
            else:
                return Value(self.amount % other.convert_unit(self.unit).amount, self.unit)

    def __pow__(self, other: "Value | int | float") -> "Value":
        if isinstance(other, (int, float)):
            return Value(self.amount**other, self.unit)
        else:
            if self.unit == other.unit:
                return Value(self.amount**other.amount, self.unit)
            else:
                return Value(self.amount ** other.convert_unit(self.unit).amount, self.unit)

    @override
    def __eq__(self, value: object, /) -> bool:
        if isinstance(value, (int, float)):
            return self.amount == value  # NOTE: blindly returning the comparison without unit match
        elif isinstance(value, Value):
            if self.unit == value.unit:
                return self.amount == value.amount
            else:
                return self.amount == value.convert_unit(self.unit).amount
        elif hasattr(value, "__eq__"):
            return value.__eq__(self.amount)
        return False

    @override
    def __str__(self) -> str:
        self._to_int_if_possible()
        return str(self.amount) + (self.unit or "")

    @override
    def __repr__(self) -> str:
        return self.__str__()

    def _to_int_if_possible(self) -> None:
        if int(self.amount) == self.amount:
            self.amount = int(self.amount)

    def convert_unit(self, unit: str | None) -> "Value":
        if unit is None:
            return Value(self.amount, None)
        if unit not in UNITS:
            raise ValueError(f"No unit named: {unit} found.")
        if self.unit is None:
            return Value(self.amount, unit)  # NOTE: blindly set the unit
        if convertible(self.unit, unit):
            return Value(self.amount * UNITS[self.unit] / UNITS[unit], unit)
        raise ValueError(f"Unable to convert from {self.unit} to {unit}")


class _NAValue(Value):
    def __init__(self) -> None:
        super().__init__(0, None)

    @override
    def __str__(self) -> str:
        return "NA"


NA_VALUE = _NAValue()
