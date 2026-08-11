# Thesis: SZZ Label Noise in Just-In-Time Defect Prediction

This repository contains the codebase for the thesis exploring SZZ label noise in Just-In-Time Software Defect Prediction (JIT-SDP).

## Environment Setup

To continue work on a different machine, follow these steps to set up the environment exactly as it was:

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd thesis-later
```

### 2. Set Up the Virtual Environment
Ensure you have Python 3 installed. Create a new virtual environment:

```bash
python3 -m venv venv
```

### 3. Activate the Virtual Environment
Activate the virtual environment. 

On **Linux / macOS**:
```bash
source venv/bin/activate
```

On **Windows**:
```cmd
venv\Scripts\activate
```

### 4. Install Dependencies
Install all required packages from `requirements.txt` to ensure there is no version mismatch:
```bash
pip install -r requirements.txt
```

---

## Project Structure & Documentation

- `01_Learning_Guide.md`: Theoretical concepts and learning guide for the thesis.
- `02_Thesis_Outline.md`: Structure of the thesis.
- `03_Execution_and_Supervisor_Plan.md`: Phase-wise plan and meeting checklists.
- `codebase/`: Core code (e.g., `szz/base.py`).
- `experiments/`: Scripts to run experiments (e.g., `python -m experiments.run_phase1 ...`).

## Running the Code
*(Refer to `03_Execution_and_Supervisor_Plan.md` for detailed steps for each phase.)*

Example command to run phase 1:
```bash
python -m experiments.run_phase1 --data <path-to-data>
```
