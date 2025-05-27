from typing import TypeVar, Generic, Optional
from dataclasses import dataclass

# 定义泛型类型变量
T = TypeVar('T')

@dataclass
class ApiResponse(Generic[T]):
    Success: bool
    ErrorCode: int
    Data: T
    FirstError: Optional[str]
    DebugError: Optional[str]