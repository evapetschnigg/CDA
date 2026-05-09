# CDA - oTree Experiment Code

This repository contains the oTree code used in my master's thesis to implement a personal carbon trading experiment with a continuous double auction carbon market.

## Thesis information

- **Title:** *An Experimental Analysis of Personal Carbon Trading: The Role of Environmental Framing and Income Heterogeneity*
- **Submitted:** 15 May 2026

## Scope of this repository

The project includes:
- `preparation`: instruction pages, comprehension check, and onboarding flow.
- `Trading`: market interaction pages and payoff-relevant rounds.
- `screening`: separate screening app. (not used in final data collection)
- project-level configuration (`settings.py`) and static/template assets required to run sessions.

## Running the project locally

Requirements:
- Python 3.11
- oTree 6.0.0b4

Install and start:

```bash
pip install -U otree
otree devserver
```

Default session configuration:
- `PCT` with app sequence `preparation -> Trading`
- 6 demo participants
- market time 80 seconds per round

## Reproducibility note

This code is shared for transparency and reproducibility of the thesis results.
Experimental parameters and treatment logic are defined in the app code (mainly `Trading/__init__.py`, `preparation/__init__.py`) and in `settings.py`.

## Acknowledgement / adapted code

This project builds on and adapts components from:

Schmidt, D. (2024). *oTree: Continuous double auction* (Version 1.0.0) [Computer software]. [https://github.com/domidt/CDA](https://github.com/domidt/CDA)


