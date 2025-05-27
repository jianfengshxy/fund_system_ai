from typing import List, Optional, TypeVar, Generic
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class PageInfo(Generic[T]):
    pageIndex: int
    pageSize: int
    currPageSize: int
    totalPage: int
    totalSize: int
    data: List[T]
    extraData: Optional[dict]