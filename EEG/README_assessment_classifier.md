# Motor Imagery EEG Assessment Classifier

A comprehensive Python tool for analyzing motor imagery EEG data, providing automated Event-Related Desynchronization (ERD) analysis with multiple calculation methods and statistical summaries.

## 🎯 Overview

This classifier automates the complete EEG analysis pipeline from the `analysis.ipynb` notebook, transforming raw EEG recordings into meaningful motor imagery performance metrics. It processes BrainVision format EEG data and generates statistical summaries comparing different finger imagery conditions.

## 📁 Input Files Required

### File Structure
```
./data/rawdata/
└── {participant_name}/
    ├── {participant_name}.vhdr    # BrainVision header file
    ├── {participant_name}.vmrk    # BrainVision marker file  
    └── {participant_name}.eeg     # BrainVision binary data file
```

### File Contents
- **`.vhdr`**: Contains metadata (sampling rate, channel names, filters)
- **`.vmrk`**: Contains event markers/triggers (stimulus onsets, trial types)
- **`.eeg`**: Contains raw EEG signal data (voltage measurements over time)

### Expected Triggers/Markers
The analysis expects these trigger codes in the marker file:
- **1-5**: Normal fingers (thumb, index, middle, ring, pinky)
- **6**: Sixth finger (supernumerary finger imagery)
- **7**: Rest/blank condition

## 🔄 Processing Pipeline: From Input to Summary

### Step 1: Data Loading & Validation
```python
# Load BrainVision files
raw_data = mne.io.read_raw_brainvision("participant.vhdr")
events, event_id = mne.events_from_annotations(raw_data)
```
- Reads EEG signals and extracts trigger events
- Validates file integrity and sampling parameters
- Reports basic data characteristics (sampling rate, channels, etc.)

### Step 2: Data Preprocessing
```python
# Remove bad channels and prepare for analysis
clean_channels = [ch for ch in channels if ch not in BAD_CHANNELS]
focus_indices = [clean_channels.index(ch) for ch in FOCUS_CHANNELS]
```
- **Bad Channel Removal**: Excludes problematic channels (FT9, TP9, FT10, TP10)
- **Focus Channel Selection**: Identifies motor cortex channels (C3, C1, CP3, CP1)
- **Data Format Conversion**: Transforms to DataFrame for epoch extraction

### Step 3: Epoch Extraction
```python
# Extract 4-second epochs around each stimulus
epoch_start = marker_onset - 2s_samples  # 2s before stimulus
epoch_end = marker_onset + 2s_samples    # 2s after stimulus
epoch_data = data[epoch_start:epoch_end]  # Shape: (channels, samples)
```
- **Epoching Window**: 4 seconds total (2s pre + 2s post stimulus)
- **Baseline Period**: First 2 seconds (pre-stimulus)
- **Analysis Period**: Last 2 seconds (post-stimulus)

### Step 4: Signal Processing & ERD Calculation

#### 4.1 Preprocessing (Applied to Each Epoch)
```python
# 1. Bandpass filtering (8-30 Hz - Alpha/Beta bands)
filtered_data = filtfilt(butterworth_filter, epoch_data)

# 2. Common Average Reference (CAR)
car_data = filtered_data - mean(filtered_data, axis=channels)
```

#### 4.2 ERD Calculation Methods

**Method 1: Bandpass ERD** (Simple Power)
```python
# Square filtered signal to get power
power = filtered_data ** 2
pre_power = mean(power[:, baseline_period])
post_power = mean(power[:, analysis_period])
ERD% = ((post_power - pre_power) / pre_power) × 100
```

**Method 2: Welch ERD** (Spectral Power)
```python
# Use Welch's method for power spectral density
f, psd_pre = welch(baseline_data, fs=sampling_rate)
f, psd_post = welch(analysis_data, fs=sampling_rate)
# Extract power in 8-30 Hz band
ERD% = ((band_power_post - band_power_pre) / band_power_pre) × 100
```

**Method 3: dB Correction ERD** (Logarithmic)
```python
ERD_dB = 10 × log₁₀(post_power / pre_power)
```

**Method 4: Moving Average ERD** ⭐ (Temporal Dynamics)
```python
# Sliding window analysis across the epoch
for window in sliding_windows(epoch_data, window_size=75_samples):
    window_power = mean(window ** 2)
    window_erd = ((window_power - baseline_power) / baseline_power) × 100
ERD_timeline = [window_erd_values...]
final_ERD = mean(ERD_timeline)
```

#### 4.3 Channel Averaging
```python
# Average ERD across motor cortex channels
focus_channels = [C3, C1, CP3, CP1]  # Motor cortex
final_ERD = mean([ERD[ch] for ch in focus_channels])
```

### Step 5: Statistical Summary Generation

#### 5.1 Categorization
```python
CATEGORIES = {
    'NT': [1,2,3,4,5],  # Normal Touch (fingers 1-5)
    'ST': [6],          # Sixth finger Touch  
    'Rest': [7]         # Rest condition
}
```

#### 5.2 Filtering & Statistics
```python
# For each category, apply threshold filtering
for category in ['NT', 'ST', 'Rest']:
    if category in ['NT', 'ST']:
        # Motor imagery: expect negative ERD (desynchronization)
        valid_trials = trials[ERD < 0]
    else:  # Rest
        # Rest: expect positive ERD (synchronization) 
        valid_trials = trials[ERD > 0]
    
    # Calculate statistics
    mean_ERD = mean(valid_trials)
    std_ERD = std(valid_trials)
    count = len(valid_trials)
    total = len(all_trials_for_category)
    percentage = (count/total) × 100
```

## 📊 Summary Output Format

### Example Output
```
Category    Mean     Std Dev    Count
NT         -12.345   8.234     45/60 (75.00%)
ST         -15.678   9.876     12/15 (80.00%)
Rest        5.432    6.543     18/20 (90.00%)
Total: 75
```

### Interpretation
- **NT (Normal Touch)**: Average ERD for regular finger imagery
- **ST (Sixth finger Touch)**: Average ERD for supernumerary finger imagery  
- **Rest**: Average ERD during rest periods
- **Negative ERD**: Desynchronization (expected for motor imagery)
- **Positive ERD**: Synchronization (expected for rest)
- **Count**: Valid trials / Total trials (percentage of successful classifications)

## 🚀 Usage

### Basic Usage
```bash
python assessment_classifier.py --participant randy
```

### Advanced Options
```bash
# Custom data directory
python assessment_classifier.py -p john --data_dir ./custom/path/

# Specific ERD method only
python assessment_classifier.py -p sarah --method moving_average

# Custom parameters
python assessment_classifier.py -p mike -m moving_average --window_size 100
```

### Command Line Arguments
- **`-p, --participant`** (Required): Participant identifier
- **`-d, --data_dir`** (Optional): Base data directory (default: `./data/rawdata/`)
- **`-m, --method`** (Optional): ERD method (`all`, `bandpass`, `welch`, `db_correction`, `moving_average`)
- **`--window_size`** (Optional): Moving average window size in samples (default: 75)

## 🔧 Configuration

### Key Parameters (Modifiable in `AssessmentConfig`)
```python
FOCUS_CHANNEL_NAMES = ["C3", "C1", "CP3", "CP1"]  # Motor cortex
BAD_CHANNELS = ['FT9', 'TP9', 'FT10', 'TP10']     # Exclude these
EPOCH_PRE_STIMULUS_SECONDS = 2.0                   # Baseline period
EPOCH_POST_STIMULUS_SECONDS = 2.0                  # Analysis period  
BANDPASS_LOW = 8.0                                 # Alpha band start
BANDPASS_HIGH = 30.0                               # Beta band end
```

## 📈 ERD Method Comparison

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| **Bandpass** | Simple, fast | Basic power estimate | Quick screening |
| **Welch** | Better spectral resolution | More computationally intensive | Frequency-specific analysis |
| **dB Correction** | Logarithmic scaling | Less intuitive units | Cross-subject comparison |
| **Moving Average** ⭐ | Temporal dynamics, robust | Most complex | Detailed analysis |

## 🧠 Scientific Background

### Event-Related Desynchronization (ERD)
- **ERD**: Decrease in oscillatory power during motor imagery
- **Typical Range**: 8-30 Hz (alpha/beta bands)
- **Location**: Contralateral motor cortex (C3/C4 regions)
- **Interpretation**: More negative ERD = stronger motor imagery activation

### Motor Imagery vs Rest
- **Motor Imagery**: Expected negative ERD (desynchronization)
- **Rest**: Expected positive ERD or smaller negative ERD (synchronization)
- **Sixth Finger**: Research focus on plasticity and supernumerary limb representation

## 📋 Requirements

```bash
pip install numpy pandas mne matplotlib scipy
```

## 🔍 Troubleshooting

### Common Issues
1. **File Not Found**: Check participant name matches folder/file names exactly
2. **No Valid Epochs**: Verify trigger codes (1-7) exist in marker file
3. **Channel Errors**: Ensure focus channels exist in your EEG montage
4. **Memory Issues**: Large files may require chunked processing

### Debug Tips
```bash
# Check file structure
ls -la ./data/rawdata/participant_name/

# Verify trigger codes in data
python -c "import mne; raw=mne.io.read_raw_brainvision('file.vhdr'); print(raw.annotations)"
```

## 📊 Output Files

The classifier generates console output with statistical summaries. For saving results to files, modify the `main()` function to export DataFrames:

```python
# Add to main() function
results_df.to_csv(f'{participant}_erd_results.csv')
summary_df.to_csv(f'{participant}_summary.csv')
```

---

*This classifier automates the complete motor imagery EEG analysis pipeline, transforming raw neural signals into interpretable performance metrics for neuroscience research.*
