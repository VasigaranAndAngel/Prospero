# fmt: off
LENGTH = {  # base: meter
    "m": 1, "meter": 1, "meters": 1, "metre": 1, "metres": 1,
    "km": 1000, "kilometer": 1000, "kilometers": 1000, "kilometre": 1000, "kilometres": 1000,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01, "centimetre": 0.01, "centimetres": 0.01,
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001, "millimetre": 0.001, "millimetres": 0.001,
    "mile": 1609.344, "miles": 1609.344, "mi": 1609.344,
    "yard": 0.9144, "yards": 0.9144, "yd": 0.9144, "yds": 0.9144,
    "foot": 0.3048, "feet": 0.3048, "ft": 0.3048,
    "inch": 0.0254, "inches": 0.0254,
    "nauticalmile": 1852, "nauticalmiles": 1852, "nmi": 1852,
}

MASS = {  # base: gram
    "g": 1, "gram": 1, "grams": 1, "gramme": 1, "grammes": 1,
    "kg": 1000, "kilogram": 1000, "kilograms": 1000, "kilo": 1000, "kilos": 1000,
    "mg": 0.001, "milligram": 0.001, "milligrams": 0.001,
    "lb": 453.59237, "lbs": 453.59237, "pound": 453.59237, "pounds": 453.59237,
    "oz": 28.349523125, "ounce": 28.349523125, "ounces": 28.349523125,
    "ton": 907184.74, "tons": 907184.74, "shortton": 907184.74,
    "tonne": 1_000_000, "tonnes": 1_000_000, "metricton": 1_000_000,
    "stone": 6350.29318, "stones": 6350.29318, "st": 6350.29318,
}

VOLUME = {  # base: liter
    "l": 1, "liter": 1, "liters": 1, "litre": 1, "litres": 1,
    "ml": 0.001, "milliliter": 0.001, "milliliters": 0.001, "millilitre": 0.001, "millilitres": 0.001,
    "gallon": 3.785411784, "gallons": 3.785411784, "gal": 3.785411784,
    "quart": 0.946352946, "quarts": 0.946352946, "qt": 0.946352946,
    "pint": 0.473176473, "pints": 0.473176473, "pt": 0.473176473,
    "cup": 0.2365882365, "cups": 0.2365882365,
    "flounce": 0.0295735296, "flounces": 0.0295735296, "floz": 0.0295735296,
    "tbsp": 0.0147867648, "tablespoon": 0.0147867648, "tablespoons": 0.0147867648,
    "tsp": 0.00492892159, "teaspoon": 0.00492892159, "teaspoons": 0.00492892159,
}

DATA = {  # base: byte
    "b": 1, "byte": 1, "bytes": 1,
    "bit": 0.125, "bits": 0.125,
    "kb": 1000, "kilobyte": 1000, "kilobytes": 1000,
    "mb": 1_000_000, "megabyte": 1_000_000, "megabytes": 1_000_000,
    "gb": 1_000_000_000, "gigabyte": 1_000_000_000, "gigabytes": 1_000_000_000,
    "tb": 1_000_000_000_000, "terabyte": 1_000_000_000_000, "terabytes": 1_000_000_000_000,
    "pb": 1_000_000_000_000_000, "petabyte": 1_000_000_000_000_000, "petabytes": 1_000_000_000_000_000,
    "kib": 1024, "kibibyte": 1024, "kibibytes": 1024,
    "mib": 1024 ** 2, "mebibyte": 1024 ** 2, "mebibytes": 1024 ** 2,
    "gib": 1024 ** 3, "gibibyte": 1024 ** 3, "gibibytes": 1024 ** 3,
    "tib": 1024 ** 4, "tebibyte": 1024 ** 4, "tebibytes": 1024 ** 4,
}

TIME = {  # base: second
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "day": 86400, "days": 86400,
    "week": 604800, "weeks": 604800,
    "month": 2_629_800, "months": 2_629_800,     # avg (365.25/12 days)
    "year": 31_557_600, "years": 31_557_600,     # avg (365.25 days)
}

TEMPERATURE_UNITS = {
    "c", "celsius", "centigrade",
    "f", "fahrenheit",
    "k", "kelvin",
}
# fmt: on

DIMENSIONS = {
    "length": LENGTH,
    "mass": MASS,
    "volume": VOLUME,
    "data": DATA,
    "time": TIME,
}

UNITS = {unit: factor for dim in DIMENSIONS.values() for unit, factor in dim.items()}
UNITS.update({k: 0 for k in TEMPERATURE_UNITS})


def dimension_of_unit(unit: str) -> str:
    if unit in TEMPERATURE_UNITS:
        return "temperature"
    for dim, units in DIMENSIONS.items():
        if unit in units.keys():
            return dim
    raise ValueError(f"Unit named: '{unit}' not found.")


def convertible(unit1: str, unit2: str) -> bool:
    if unit1 in TEMPERATURE_UNITS and unit2 in TEMPERATURE_UNITS:
        return True
    unit1_dim = dimension_of_unit(unit1)
    return unit2 in DIMENSIONS[unit1_dim].keys()
