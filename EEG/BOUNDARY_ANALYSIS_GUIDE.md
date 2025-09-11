# Motor Imagery EEG Assessment Classifier - Boundary Analysis Guide

## Overview

The Assessment Classifier provides three different approaches for analyzing ERD (Event-Related Desynchronization) data with different boundary thresholds:

1. **Static Boundary (DEFAULT)** - Uses boundary=0
2. **REST Boundary Context** - Shows REST baseline but uses boundary=0  
3. **Comparative Analysis** - Side-by-side comparison of both methods

## Boundary Methods Explained

### 1. Static Boundary (DEFAULT)
- **Threshold**: boundary = 0
- **Logic**: 
  - NT/ST trials: Valid if ERD < 0 (desynchronization)
  - REST trials: Valid if ERD > 0 (synchronization)
- **When to use**: Standard analysis, comparing against theoretical baseline

### 2. Dynamic REST Boundary
- **Threshold**: boundary = REST_average (for NT/ST trials)
- **Logic**:
  - NT/ST trials: Valid if ERD < REST_average (more desynchronized than participant's rest)
  - REST trials: Valid if ERD > 0 (synchronization, always compared to 0)
- **When to use**: When you want to compare motor imagery against participant's actual rest state

### 3. Comparative Analysis
- **Shows both**: Static boundary=0 AND REST boundary results
- **Comparison**: Displays difference in valid trial counts between methods
- **When to use**: Research purposes, understanding impact of boundary choice

## Usage Examples

### Basic Analysis (DEFAULT)
```bash
python assessment_classifier.py --participant randy
```
**Output**: Shows both static and REST boundary results for all methods

### Single Method Analysis
```bash
python assessment_classifier.py -p randy --method moving_average
```
**Output**: Shows both static and REST boundary results for moving_average method only

### REST Context Mode
```bash
python assessment_classifier.py -p randy --method moving_average --use_rest_boundary
```
**Output**: 
- Uses boundary=0 for classification
- Shows REST boundary for reference
- Note explaining the difference

### Comparative Analysis
```bash
python assessment_classifier.py -p randy --method compare
```
**Output**: 
- Side-by-side comparison
- Static boundary results
- REST boundary results  
- Summary showing difference in trial counts

### All Methods Analysis
```bash
python assessment_classifier.py -p randy --method all
```
**Output**: Runs all ERD methods (bandpass, welch, db_correction, moving_average) with both boundaries

## Command Line Arguments

| Argument | Options | Default | Description |
|----------|---------|---------|-------------|
| `-p, --participant` | string | **Required** | Participant identifier (e.g., "randy") |
| `-d, --data_dir` | path | `./data/rawdata/` | Base directory for participant data |
| `-m, --method` | `bandpass`, `welch`, `db_correction`, `moving_average`, `all`, `compare` | `all` | ERD calculation method |
| `--window_size` | integer | `75` | Window size for moving average (samples) |
| `--use_rest_boundary` | flag | `False` | Show REST context but use boundary=0 |

## Understanding the Output

### Example Output Structure:
```
=== Analysis Results ===

--- Static Boundary Analysis (boundary=0) ---
Category    Mean  Std Dev          Count
      NT -49.333   22.806 39/45 (86.67%)
      ST -47.961   19.499 42/45 (93.33%)
    Rest 396.178 1065.657 29/45 (64.44%)

Dynamic REST boundary calculated: -0.911 (from 28 REST trials)

--- Dynamic REST Boundary Analysis (boundary=-0.911) ---
Category    Mean  Std Dev          Count
      NT -49.333   22.806 39/45 (86.67%)
      ST -47.961   19.499 42/45 (93.33%)
    Rest 396.178 1065.657 29/45 (64.44%)
```

### Interpreting Results:

- **NT**: Normal Touch (fingers 1-5: thumb, index, middle, ring, pinky)
- **ST**: Sixth finger Touch (supernumerary finger)
- **Rest**: REST condition trials
- **Count**: Valid trials / Total trials (Percentage)
- **Mean/Std Dev**: ERD statistics for valid trials only

### REST Boundary Calculation:
1. Filters REST trials (stimulus=7)
2. Removes outliers (ERD values outside -100 to 100 range)
3. Calculates mean ERD value from valid REST trials
4. Uses this mean as the REST boundary threshold

## When to Use Each Method

### Use Static Boundary (DEFAULT) when:
- Standard research protocol
- Comparing across studies
- Theoretical baseline comparison needed
- Publication/standardization requirements

### Use REST Context when:
- Want to understand individual differences
- Need participant-specific baseline reference
- Still want standard classification (boundary=0)
- Exploring individual variability

### Use Comparative Analysis when:
- Research on boundary method impact
- Method validation studies
- Understanding classification sensitivity
- Exploring optimal thresholds

## Quick Reference Commands

```bash
# Most common usage - comprehensive analysis
python assessment_classifier.py --participant PARTICIPANT_NAME

# Quick single method
python assessment_classifier.py -p PARTICIPANT_NAME --method moving_average

# With REST context
python assessment_classifier.py -p PARTICIPANT_NAME --method moving_average --use_rest_boundary

# Compare boundaries
python assessment_classifier.py -p PARTICIPANT_NAME --method compare

# Custom data location
python assessment_classifier.py -p PARTICIPANT_NAME --data_dir /path/to/data/
```

## File Structure Expected

```
data_dir/
└── PARTICIPANT_NAME/
    ├── PARTICIPANT_NAME.vhdr
    ├── PARTICIPANT_NAME.vmrk  
    └── PARTICIPANT_NAME.eeg
```

## Default Configuration

- **Focus Channels**: C3, C1, CP3, CP1 (motor cortex)
- **Bad Channels**: FT9, TP9, FT10, TP10 (excluded)
- **Epoch Window**: 2s before to 2s after stimulus
- **Frequency Band**: 8-30 Hz (alpha/beta)
- **Moving Average Window**: 75 samples
- **Outlier Range**: -100 to 100 ERD values
