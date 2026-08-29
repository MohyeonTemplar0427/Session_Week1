from battery import Battery
from dataclasses import dataclass

battery = Battery(
    capacity_kWh = 20.0,
    energy_kWh = 10.0,
    max_charge_kw=5.0,
    max_discharge_kw=5.0
)

@dataclass
class ExperimentConfig:
    start_date: str
    number_of_days: int

    carbon_weight: float = 0.20
    degradation_cost_per_kWh: float = 0.03
    timestep_hours: float = 0.25

    caiso_node: str = "TH_NP15_GEN-APND0"
    electricity_maps_zone: str = "US-CAL-CISO"

    timezone: str = "America/Los_Angeles"
    sleep_seconds: float = 0.0

def to_optimizer_parameters(
        self,
) -> dict[str, float]:

    return {
        "capacity_kWh": self.capacity_kWh,
        "initial_soc_kWh": self.energy_kWh,
        "min_soc_kWh": self.minimum_energy_kWh,
        "max_soc_kWh": self.maximum_energy_kWh,
        "max_charge_kw": self.max_charge_kw,
        "max_discharge_kw": self.max_discharge_kw,
        "charge_efficiency": self.charge_efficiency,
        "discharge_efficiency": self.discharge_efficiency
    }

