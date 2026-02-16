from dataclasses import dataclass, field
from typing import List

from hummingbot.core.data_type.order_candidate import OrderCandidate


@dataclass
class OrderActionPlan:
    cancellations_ids: List[str] = field(default_factory=list)
    creations_candidates: List[OrderCandidate] = field(default_factory=list)
