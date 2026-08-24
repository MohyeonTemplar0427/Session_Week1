from dataclasses import dataclass

@dataclass
class Battery:
    capacity_kWh: float = 50

    SOC_min: float = 0.2
    minimum_energy_kWh = capacity_kWh * SOC_min

    SOC_max: float = 0.8
    maximum_energy_kWh = capacity_kWh * SOC_max

    SOC_range: float = SOC_max - SOC_min
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    max_charge_kw: float = 20
    max_discharge_kw: float = 20
    energy_kWh: float = 0

    def __post_init__(self) -> None:
        if self.capacity_kWh <= 0:
            raise ValueError("Capacity must be positive.")
        
        if self.minimum_energy_kWh <= 0:
            raise ValueError("Minimumenergy must be positive.")
        
        if self.maximum_energy_kWh <= 0:
            raise ValueError("Maximumenergy must be positive.")
        
        if not self.minimum_energy_kWh <= self.energy_kWh <= self.maximum_energy_kWh:
            raise ValueError("Energy must be between minimum and maximum energy.")

        if self.max_charge_kw <= 0:
            raise ValueError("Maximum charge power must be positive.")
        
        if self.max_discharge_kw <= 0:
            raise ValueError("Maximum discharge power must be positive.")
        
        if not 0 < self.charge_efficiency <= 1:
            raise ValueError("Charge efficiency must be between 0 and 1.")
        
        if not 0 <= self.discharge_efficiency <= 1:
            raise ValueError("Discharge efficiency must be between 0 and 1.")


    def SOC_percentage(self) -> float: 
        return (self.energy_kWh / self.capacity_kWh) * 100


    def update_energy(
        self,
        charge_kw: float,
        discharge_kw: float,
        dt_hours: float = 0.25,
    ) -> float:
        self._validate_power_command(
            charge_kw = charge_kw,
            discharge_kw = discharge_kw,
            dt_hours = dt_hours,
        )

        next_energy_kWh = self.energy_kWh + (charge_kw * self.charge_efficiency - discharge_kw / self.discharge_efficiency) * dt_hours
        
        if next_energy_kWh > self.maximum_energy_kWh:
            raise ValueError("Energy must be less than maximum energy.")
        
        if next_energy_kWh < self.minimum_energy_kWh:
            raise ValueError("Energy must be greater than minimum energy.")
        
        self.energy_kWh = next_energy_kWh
        
        return self.energy_kWh


        if charge_kw < 0:
            raise ValueError("Charge power must be non-negative.")
        if discharge_kw < 0:
            raise ValueError("Discharge power must be non-negative.")
        if charge_kw > self.self.max_charge_kw:
            raise ValueError("Charge power must be less than maximum charge power.")
        if discharge_kw > self.max_discharge_kw:
            raise ValueError("Discharge power must be less than maximum discharge power.")
        if dt_hours <= 0:
            raise ValueError("Timestep must be positive")