"""
Time signature enumeration supported by PAMG.
"""

from enum import Enum


class TimeSignature(Enum):
    """
    Standard time signature values supported by PAMG.
    """
    FOUR_FOUR = "4/4"
    THREE_FOUR = "3/4"
    SIX_EIGHT = "6/8"
    SIX_FOUR = "6/4"
