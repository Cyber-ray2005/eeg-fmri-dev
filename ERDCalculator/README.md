# `ERDCalculator` Class Documentation

## Overview

`ERDCalculator` is a Python class designed to compute **Event-Related Desynchronization (ERD)** from EEG (electroencephalogram) data. It supports multiple calculation techniques including:

* Bandpass power estimation
* Welch’s method
* Decibel (dB) baseline correction
* Moving average window analysis
* Trial-averaged ERD computation across stimuli

This modular and refactored class is optimized for code reusability, clarity, and integration into EEG signal processing pipelines.

---

## Initialization

```python
ERDCalculator(
    sampling_freq,
    epoch_pre_stimulus_seconds,
    epoch_post_stimulus_seconds,
    bandpass_low,
    bandpass_high,
    channel_names,
    focus_channels_indices,
    focus_stimuli=None
)
```

### Parameters:

* `sampling_freq` (`float`): Sampling frequency of the EEG signal in Hz.
* `epoch_pre_stimulus_seconds` (`float`): Duration (in seconds) of the pre-stimulus window.
* `epoch_post_stimulus_seconds` (`float`): Duration (in seconds) of the post-stimulus window.
* `bandpass_low` (`float`): Low cutoff frequency of the bandpass filter.
* `bandpass_high` (`float`): High cutoff frequency of the bandpass filter.
* `channel_names` (`list[str]`): List of EEG channel names.
* `focus_channels_indices` (`list[int]`): Indices of channels to focus on when aggregating ERD values.
* `focus_stimuli` (`list[str]`, optional): List of stimulus labels to include during trial-based analysis.

---

## Public Methods

### `calculate_erd_from_bandpass(epoch_data, return_mean=False)`

Calculates ERD by squaring the filtered EEG signal and comparing baseline vs activation power.

* **Inputs:**

  * `epoch_data` (`np.ndarray`): Epoch of EEG data, shape `(n_channels, n_samples)`.
  * `return_mean` (`bool`): Whether to return the mean ERD of focus channels or per-channel values.

* **Returns:** `float`, `dict`, or `None`

---

### `calculate_erd_from_welch(epoch_data, return_mean=False)`

Computes ERD using Welch’s method for spectral power estimation in the frequency band of interest.

* **Returns:** `float`, `dict`, or `None`

---

### `calculate_erd_from_db_correction(epoch_data, return_mean=False)`

Computes ERD using dB correction:

```math
ERD_{dB} = 10 * log10(P_{activation} / P_{baseline})
```

* **Returns:** `float`, `dict`, or `None`

---

### `calculate_erd_moving_average(epoch_data, window_size_samples, return_mean=True, method='percentage')`

Computes ERD using a moving window approach for more granular temporal resolution. Supports both percentage and dB-based methods.

* **Parameters:**

  * `window_size_samples` (`int`): Size of the moving window in samples.
  * `method` (`str`): Either `'percentage'` or `'db_correction'`.

* **Returns:** `(float, np.ndarray)` if `return_mean=True`; otherwise a `dict`.

---

### `calculate_erd_across_trials(data_df, markers_df, subject_id=None)`

Calculates average ERD per stimulus by aggregating across trials.

* **Inputs:**

  * `data_df` (`pd.DataFrame`): EEG data with time as rows and channels as columns.
  * `markers_df` (`pd.DataFrame`): Marker data with `'onset'` (in samples) and `'description'` columns.
  * `subject_id` (`any`, optional): If provided, appended to the result for traceability.

* **Returns:** `dict` mapping stimulus names to mean ERD values for focus channels.

---

## Private Methods

### `_preprocess_epoch(epoch_data)`

Filters and applies Common Average Reference (CAR) to input epoch.

* **Returns:** Filtered epoch (`np.ndarray`) or `None` on failure.

---

### `_compute_erd_percentage(pre_power, post_power)`

Calculates ERD in percent using:

```math
ERD = ((P_{post} - P_{pre}) / P_{pre}) * 100
```

---

### `_compute_erd_db(pre_power, post_power)`

Computes ERD in dB:

```math
ERD = 10 * log10(P_{post} / P_{pre})
```

---

## Notes

* This class assumes **epochs are time-locked** to stimulus markers.
* It uses **zero-phase Butterworth filtering** via `scipy.signal.filtfilt` and `scipy.signal.butter`.
* Methods handle common edge cases such as `NaN` power, invalid shapes, and log-domain issues gracefully.
* Designed to support both **single-epoch** and **multi-trial** analyses.

---

## Example Usage

```python
erd_calc = ERDCalculator(
    sampling_freq=250,
    epoch_pre_stimulus_seconds=1,
    epoch_post_stimulus_seconds=1,
    bandpass_low=8,
    bandpass_high=30,
    channel_names=['C3', 'Cz', 'C4'],
    focus_channels_indices=[0, 2]
)

# For one epoch
erd_value = erd_calc.calculate_erd_from_bandpass(epoch_data, return_mean=True)

# Across all trials
erd_results = erd_calc.calculate_erd_across_trials(data_df, markers_df)
```

