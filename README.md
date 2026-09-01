# Session_Week1
Repo for creating knowledge framework for energy engineer. 


## Week 2: Real-data consolidation

Week 2 completed strict time-series validation, one-to-one signal alignment, real CAISO price and Electricity Maps carbon scenarios, degradation-aware common-baseline comparisons, and a validated OpenDSS handoff.

Run the deterministic tests:

```bash
pytest -q
```

Run the real-data experiment:

```bash
python3 src/market_data_integration.py
```

Generated artifacts:

- `results/week2_market_signal_scenario_comparison.csv`
- `results/week2_opendss_handoff_combined_real_15min.csv`
- `results/week2_opendss_handoff_combined_real_15min_metadata.json`

See [`Week_2_Completion_Recap.md`](Week_2_Completion_Recap.md) for results, validation rules, units, sign conventions, limitations, and Week 3 readiness.