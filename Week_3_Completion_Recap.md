# Week 3 Completion Recap — OpenDSS Distribution-System Analysis

## Completion Status

Week 3 is complete.

The project now connects the Week 1–2 microgrid optimizer to an OpenDSS distribution-system model. Optimized dispatch schedules can be replayed through a three-phase feeder and evaluated for voltage, current, convergence, power balance, and electrical losses.

Final validation:

- 51 automated tests passed.
- All 192 optimized QSTS intervals converged.
- All 192 no-battery QSTS intervals converged.
- Python package imports and VS Code module launch configurations were validated.

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

The OpenDSS feeder loss was independently checked with:

\[
P_{\text{loss}} = \sum I_{\text{phase}}^2R
\]

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

Enums provide explicit loading states, and parameterized tests verify boundary behavior.

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
- 10–90% permitted
