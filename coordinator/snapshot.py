from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EdgeState:
    edge_id: str
    occupancy: float
    mean_speed_ms: float
    halting_count: int
    vehicle_count: int

    @property
    def speed_kmh(self) -> float:
        return self.mean_speed_ms * 3.6

    @property
    def congested(self) -> bool:
        return self.occupancy > 0.7 or self.halting_count > 10


@dataclass
class NetworkSnapshot:
    sim_time: float
    edges: list
    av_waiting: int
    avg_wait_s: float
    incident: Optional[str] = None


@dataclass
class PassengerPersona:
    agent_id: str
    origin: str
    destination: str
    agent_type: str
    value_of_time: float
    local_info: dict = field(default_factory=dict)
    memory: list = field(default_factory=list)
