from typing import TypeVar, Type
from .core import Structure


StructureT = TypeVar("StructureT", bound=Structure)
AggreStructureT = TypeVar("AggreStructureT", bound=Structure)
