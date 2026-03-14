from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    params: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    results: List[Dict[str, Any]]
