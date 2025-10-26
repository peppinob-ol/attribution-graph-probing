from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Activation:
    id: str
    tokens: List[str]
    index: str
    layer: str
    modelId: str
    maxValue: float
    maxValueTokenIndex: int
    minValue: float
    values: List[float]
    creatorId: str
    dataSource: Optional[str] = None
    dataIndex: Optional[str] = None
    dfaValues: List[float] = field(default_factory=list)
    dfaTargetIndex: Optional[int] = None
    dfaMaxValue: Optional[float] = None
    createdAt: datetime = field(default_factory=datetime.now)
    lossValues: List[float] = field(default_factory=list)
    logitContributions: Optional[str] = None
    binMin: Optional[float] = None
    binMax: Optional[float] = None
    binContains: Optional[float] = None
    qualifyingTokenIndex: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)
