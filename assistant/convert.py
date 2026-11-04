"""Unit and currency conversion: 'convert 10 km to miles', 'how many cm in 2 inches', '100 dollars to rupees'."""
from __future__ import annotations

import json
import re
from typing import Callable, Optional, Tuple
from urllib.request import Request, urlopen

from .calc import _number_words

# unit -> (category, size in the base unit of that category)
_UNITS = {}


def _add(category: str, base_size: float, *names: str) -> None:
    for name in names:
        _UNITS[name] = (category, base_size, names[0])


# length (base: metre)
_add("length", 1, "meter", "meters", "metre", "metres", "m")
_add("length", 1000, "kilometer", "kilometers", "kilometre", "kilometres", "km")
_add("length", 0.01, "centimeter", "centimeters", "centimetre", "centimetres", "cm")
_add("length", 0.001, "millimeter", "millimeters", "millimetre", "millimetres", "mm")
_add("length", 1609.344, "mile", "miles", "mi")
_add("length", 0.9144, "yard", "yards", "yd")
_add("length", 0.3048, "foot", "feet", "ft")
_add("length", 0.0254, "inch", "inches", "in")
# mass (base: kilogram)
_add("mass", 1, "kilogram", "kilograms", "kilo", "kilos", "kg")
_add("mass", 0.001, "gram", "grams", "g")
_add("mass", 0.000001, "milligram", "milligrams", "mg")
_add("mass", 0.45359237, "pound", "pounds", "lb", "lbs")
_add("mass", 0.028349523, "ounce", "ounces", "oz")
_add("mass", 1000, "ton", "tons", "tonne", "tonnes")
# volume (base: litre)
_add("volume", 1, "liter", "liters", "litre", "litres", "l")
_add("volume", 0.001, "milliliter", "milliliters", "millilitre", "millilitres", "ml")
_add("volume", 3.785411784, "gallon", "gallons", "gal")
_add("volume", 0.2365882365, "cup", "cups")
# speed (base: metre per second)
_add("speed", 1, "meters per second", "m/s")
_add("speed", 0.2777777778, "kilometers per hour", "kilometres per hour", "kmh", "km/h", "kph")
_add("speed", 0.44704, "miles per hour", "mph")
# data (base: byte)
_add("data", 1, "byte", "bytes")
_add("data", 1024, "kilobyte", "kilobytes", "kb")
_add("data", 1024 ** 2, "megabyte", "megabytes", "mb")
_add("data", 1024 ** 3, "gigabyte", "gigabytes", "gb")
_add("data", 1024 ** 4, "terabyte", "terabytes", "tb")
# time (base: second)
_add("time", 1, "second", "seconds", "sec", "secs")
_add("time", 60, "minute", "minutes", "min", "mins")
_add("time", 3600, "hour", "hours", "hr", "hrs")
_add("time", 86400, "day", "days")
_add("time", 604800, "week", "weeks")
# temperature is special (not just a multiplier)
_TEMPERATURE = {"celsius": "c", "centigrade": "c", "c": "c", "fahrenheit": "f", "f": "f", "kelvin": "k", "k": "k"}
_TEMP_NAMES = {"c": "degrees Celsius", "f": "degrees Fahrenheit", "k": "kelvin"}

CURRENCIES = {
    "usd": "USD", "dollar": "USD", "dollars": "USD", "us dollar": "USD", "us dollars": "USD",
    "pkr": "PKR", "rupee": "PKR", "rupees": "PKR", "pakistani rupee": "PKR", "pakistani rupees": "PKR", "rs": "PKR",
    "inr": "INR", "indian rupee": "INR", "indian rupees": "INR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "gbp": "GBP", "pound": "GBP", "pounds": "GBP", "sterling": "GBP", "aed": "AED", "dirham": "AED", "dirhams": "AED",
    "sar": "SAR", "riyal": "SAR", "riyals": "SAR", "cad": "CAD", "aud": "AUD", "cny": "CNY", "yuan": "CNY",
    "jpy": "JPY", "yen": "JPY", "try": "TRY", "lira": "TRY", "qar": "QAR", "kwd": "KWD", "dinar": "KWD",
    "bdt": "BDT", "taka": "BDT", "myr": "MYR", "ringgit": "MYR",
}
RATES_API = "https://open.er-api.com/v6/latest/{}"

_NUMBER = r"-?\d+(?:\.\d+)?"
_UNIT_TEXT = r"[a-z/ ]+?"
FORWARD = re.compile(rf"^(?:convert |what(?:'s| is) )?({_NUMBER})\s*({_UNIT_TEXT})\s+(?:to|in|into|equals? in|is how many)\s+([a-z/ ]+)$")
HOW_MANY = re.compile(rf"^how (?:many|much) ([a-z/ ]+?) (?:are |is |do i get )?(?:in|from) ({_NUMBER})\s*([a-z/ ]+)$")


def parse_conversion(command: str) -> Optional[Tuple[float, str, str]]:
    """'convert 10 km to miles' / 'how many miles in 10 km' -> (10.0, 'km', 'miles'). None if it is not one."""
    text = _number_words(command.lower().replace(",", ""))
    match = FORWARD.match(text)
    if match:
        return float(match.group(1)), match.group(2).strip(), match.group(3).strip()
    match = HOW_MANY.match(text)
    if match:
        return float(match.group(2)), match.group(3).strip(), match.group(1).strip()
    return None


def convert_units(amount: float, src: str, dst: str) -> Optional[Tuple[float, str, str]]:
    """Returns (result, source label, target label) or None if a unit is unknown or they don't match."""
    if src in _TEMPERATURE and dst in _TEMPERATURE:
        a, b = _TEMPERATURE[src], _TEMPERATURE[dst]
        celsius = {"c": amount, "f": (amount - 32) * 5 / 9, "k": amount - 273.15}[a]
        value = {"c": celsius, "f": celsius * 9 / 5 + 32, "k": celsius + 273.15}[b]
        return value, _TEMP_NAMES[a], _TEMP_NAMES[b]
    s, d = _UNITS.get(src), _UNITS.get(dst)
    if not s or not d or s[0] != d[0]:
        return None
    return amount * s[1] / d[1], src, dst


def currency_code(name: str) -> Optional[str]:
    return CURRENCIES.get(name.strip().lower())


def fetch_rate(src: str, dst: str, fetch: Callable = urlopen, timeout: float = 5.0) -> Optional[float]:
    """Live exchange rate src -> dst from open.er-api.com (free, no key). None if offline."""
    try:
        request = Request(RATES_API.format(src), headers={"User-Agent": "voice-assistant/2.0"})
        with fetch(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return float(data["rates"][dst]) if data.get("result") == "success" else None
    except Exception:  # offline, bad JSON, unknown currency
        return None
