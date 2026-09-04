# Week 3 Completion Recap — OpenDSS Distribution-System Analysis

## Completion Status

Week 3 is complete.

The project now connects the Week 1–2 microgrid optimizer to an OpenDSS distribution-system model. Optimized dispatch schedules can be replayed through a three-phase feeder and evaluated for voltage, current, convergence, power balance, and electrical losses.

Final validation:

- 51 automated tests passed.
- All 192 optimized QSTS intervals converged.
- All 192 no-battery QSTS intervals converged.
- Python package imports were standardized.
- Command-line module execution was validated.
- VS Code module launch configurations were validated.

## Session 1 — OpenDSS Fundamentals

Session 1 introduced the core OpenDSS circuit model:

- Circuit and voltage source
- Electrical buses
- Three-phase conductors
- Feeder line
- Balanced three-phase load
- Per-unit voltage
- Power-flow convergence

The initial circuit contains:

- `source_bus`
- `load_bus`
- `Line.Feeder`
- `Load.Building`

The base 500 kW demonstration produced balanced load-bus voltages of approximately 0.9988 pu.

## Session 2 — Feeder Electrical Metrics

Session 2 added reusable electrical measurements:

- Phase-current magnitude
- Real power in kW
- Reactive power in kvar
- Apparent power in kVA
- Power factor
- Real feeder loss
- Reactive-power absorption
- Percentage feeder loss

The OpenDSS feeder loss was independently checked using:

$$
P_{\text{loss}}
=
\sum I_{\text{phase}}^2R
$$

The manual calculation and OpenDSS result differed by only approximately 0.0423 W.

Reusable results are stored in immutable dataclasses to prevent accidental modification after a simulation.

## Session 3 — Engineering Limit Assessments

Session 3 added engineering-limit evaluation:

- Normal current rating
- Emergency current rating
- Maximum phase-current loading
- Normal, emergency, and above-emergency classifications
- Minimum and maximum bus voltage
- Voltage-limit compliance

Enums provide explicit loading states, and parameterized tests verify classification boundaries.

The demonstration feeder uses:

- Normal rating: 100 A
- Emergency rating: 125 A
- Normal voltage limits: 0.95–1.05 pu

## Session 4 — QSTS Dispatch Replay

Session 4 connected the optimized dispatch schedule to OpenDSS.

The replay model includes:

- 30 kW PV system
- 20 kWh battery
- 5 kW battery inverter
- 10–90% permitted SOC range
- 95% charging efficiency
- 95% discharging efficiency
- External battery dispatch control

The optimizer and OpenDSS use the same battery power convention:

- Positive battery net injection means discharging.
- Negative battery net injection means charging.
- Values near zero are treated as idling to suppress numerical noise.

PV output is reproduced using:

$$
\text{irradiance}
=
\frac{P_{\text{PV}}}{P_{\text{PV,rated}}}
$$

The optimizer's grid-power balance was verified against the OpenDSS feeder:

$$
P_{\text{source}}
-
P_{\text{feeder loss}}
\approx
P_{\text{scheduled grid}}
$$

The largest observed power-balance error was approximately 0.000002552 kW, or 0.0026 W.

## Why QSTS Is Used

Quasi-static time-series simulation repeatedly solves steady-state power flow as load, PV, and battery conditions change.

The present experiment contains 192 intervals:

$$
2\text{ days}
\times
24\text{ hours/day}
\times
4\text{ intervals/hour}
=
192\text{ intervals}
$$

QSTS is appropriate because the optimizer schedules resources every 15 minutes, while most fast electrical transients settle much sooner. It captures slow operating changes without requiring a millisecond-scale simulation of every interval.

QSTS evaluates:

- Voltage variation
- Feeder loading
- Power-flow convergence
- Real and reactive power
- Feeder losses
- Reverse power flow
- Dispatch feasibility

QSTS does not evaluate:

- Switching transients
- Detailed inverter-control dynamics
- Fault current and protection coordination
- Harmonics
- Electromagnetic transients

Those studies require OpenDSS dynamics features or a dedicated transient simulation tool with much smaller timesteps.

## Session 5 — QSTS Scenario Analytics

Session 5 compared two scenarios using the same circuit and load/PV conditions:

1. Optimized battery dispatch
2. No-battery counterfactual

### Scenario Results

| Metric | Optimized | No battery |
|---|---:|---:|
| Intervals | 192 | 192 |
| Converged intervals | 192 | 192 |
| Minimum voltage | 0.999922 pu | 0.999922 pu |
| Maximum voltage | 0.999975 pu | 0.999982 pu |
| Maximum feeder current | 1.473286 A | 1.473286 A |
| Peak grid import | 29.517612 kW | 29.517612 kW |
| Minimum grid power | 0.000000 kW | −4.935768 kW |
| Feeder-loss energy | 0.020824 kWh | 0.021343 kWh |

The optimized battery reduced feeder-loss energy by approximately:

$$
0.021343-0.020824
=
0.000519\text{ kWh}
$$

This represents an approximately 2.434% reduction relative to the no-battery baseline.

### Engineering Interpretation

The optimized battery:

- Eliminated approximately 4.94 kW of reverse power flow.
- Slightly reduced the maximum feeder voltage.
- Reduced cumulative feeder-loss energy.
- Did not reduce peak grid import.
- Did not reduce maximum feeder current.
- Did not improve the minimum-voltage operating point.

Peak demand, maximum current, maximum loss, and minimum voltage occurred during the same interval. At that time:

- Load was 36.75 kW.
- PV output was approximately 7.23 kW.
- Battery net injection was 0 kW.
- Grid import was approximately 29.52 kW.

The battery was optimized for operating cost and carbon emissions, not feeder peak reduction. It was therefore idle during the most demanding network interval.

## Python and Software-Engineering Skills

Week 3 introduced or reinforced:

- Python modules and package structure
- `__init__.py`
- Package-relative imports
- Module execution with `python -m`
- VS Code module launch configurations
- Immutable dataclasses
- Enums
- Tuple type annotations
- Pandas row iteration
- `idxmin()`, `idxmax()`, and `.loc[]`
- Vectorized clipping
- Counterfactual scenario creation
- Time-series aggregation
- Engineering acceptance tests
- Separation of models, calculations, analytics, and orchestration

## Project Organization

Week 3 functionality is divided into:

- `src/__init__.py` — explicit Python package definition
- `src/opendss_models.py` — result dataclasses and enums
- `src/opendss_analysis.py` — circuit construction and electrical analysis
- `src/qsts_analysis.py` — baseline generation and scenario aggregation
- `src/qsts_simulation.py` — file input/output and simulation orchestration
- `test/test_opendss_analysis.py` — OpenDSS circuit and replay tests
- `test/test_qsts_analysis.py` — QSTS transformation and aggregation tests
- `.vscode/launch.json` — module-based VS Code launch configurations

## Generated Artifacts

- `results/week3_qsts_simulation_results.csv`
- `results/week3_qsts_no_battery_results.csv`
- `results/week3_qsts_scenario_comparison.csv`

## Commands

Run the base feeder analysis:

```bash
/usr/local/bin/python3 -m src.opendss_analysis
```

Run the complete QSTS simulation and comparison:

```bash
/usr/local/bin/python3 -m src.qsts_simulation
```

Run all automated tests:

```bash
/usr/local/bin/python3 -m pytest -q
```

## Current Modeling Limitations

The present model intentionally remains simple:

- PV, battery, and load connect directly at 12.47 kV.
- No distribution transformer is modeled.
- The feeder is balanced.
- The load uses a fixed 0.95 power factor.
- PV and battery initially operate at unity power factor.
- Detailed inverter-efficiency curves are omitted.
- Battery SOC is prescribed from the optimizer at each timestamp.
- OpenDSS does not independently integrate and reconcile SOC.
- The experiment covers only two days.
- The feeder is lightly loaded and electrically stiff.

These limitations explain the very small voltage variation and feeder losses.

## Recommended Future Development

The following improvements are deferred rather than added as unnecessary Week 3 sessions:

- Add a distribution transformer and low-voltage service network.
- Model unbalanced phase loading.
- Independently integrate battery SOC in OpenDSS.
- Add inverter-efficiency and temperature curves.
- Add Volt-VAR and Volt-Watt controls.
- Include regulator and capacitor controls.
- Add feeder-aware peak and voltage constraints to the optimizer.
- Simulate longer weekly, monthly, and seasonal horizons.
- Study fault current and protection coordination.
- Evaluate harmonics and inverter interactions.
- Use dynamic or electromagnetic-transient simulation where fast response matters.

## Week 4 Readiness

The project is ready to advance beyond Week 3.

It now contains a tested workflow connecting:

$$
\text{Real market data}
\rightarrow
\text{Battery optimization}
\rightarrow
\text{OpenDSS dispatch replay}
\rightarrow
\text{Network-impact analysis}
$$

Future curriculum work can build on this workflow without repeating the Python, optimization, validation, or OpenDSS fundamentals already completed.
