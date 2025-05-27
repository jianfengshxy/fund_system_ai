from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

@dataclass
class ApiResponse(Generic[T]):
    Success: bool
    ErrorCode: int
    Data: T
    FirstError: Optional[str]
    DebugError: Optional[str]