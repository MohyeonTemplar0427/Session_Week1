## P_grid + P_PV + P_Discharge = P_load + P_charge
## Rearranged as P_grid = P_load + P_charge - P_PV - P_Discharge

def calculate_grid_power(load_kw: float, pv_kw: float, charge_kw: float, discharge_kw: float) -> float:
    if load_kw < 0:
        raise ValueError("Load power cannot be negative.")

    if pv_kw < 0:
        raise ValueError("PV power cannot be negative.")

    if charge_kw < 0:
        raise ValueError("Charge power cannot be negative.")

    if discharge_kw < 0:
        raise ValueError("Discharge power cannot be negative.")

    if charge_kw > 0 and discharge_kw > 0:
        raise ValueError("Cannot charge and discharge simultaneously.")

    grid_kw = load_kw + charge_kw - pv_kw - discharge_kw
    print(f"Grid power: {grid_kw} kW")
    return grid_kw


