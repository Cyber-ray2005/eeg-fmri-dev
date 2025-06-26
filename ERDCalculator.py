import numpy as np
from scipy.signal import butter, filtfilt, welch

class ERDCalculator:
    """
    A refactored class to calculate Event-Related Desynchronization (ERD) from EEG data.

    This version consolidates redundant methods and abstracts common processing steps
    to improve clarity, reduce code duplication, and enhance maintainability.
    """
    def __init__(self, sampling_freq, epoch_pre_stimulus_seconds, epoch_post_stimulus_seconds, bandpass_low, bandpass_high, channel_names, focus_channels_indices, focus_stimuli=None):
        """
        Initializes the ERDCalculator with necessary parameters.
        """
        self.sampling_freq = sampling_freq
        self.samples_before_marker = int(epoch_pre_stimulus_seconds * sampling_freq)
        self.samples_after_marker = int(epoch_post_stimulus_seconds * sampling_freq)
        self.epoch_total_samples = self.samples_before_marker + self.samples_after_marker
        
        # Pre-compile the bandpass filter coefficients
        self.b, self.a = butter(5, [bandpass_low, bandpass_high], btype='band', fs=sampling_freq)
        
        self.channel_names = channel_names
        self.channel_count = len(channel_names)
        self.focus_channels_indices = focus_channels_indices
        self.bandpass_low = bandpass_low
        self.bandpass_high = bandpass_high
        self.focus_stimuli = focus_stimuli

    def _preprocess_epoch(self, epoch_data):
        """
        Private helper to validate, filter, and apply CAR to epoch data.
        
        Args:
            epoch_data (np.array): The EEG data for a single epoch.
                                   Shape: (n_channels, n_samples)

        Returns:
            np.array or None: The preprocessed epoch data, or None if validation fails.
        """
        # 1. Validate the shape of the epoch data
        # if epoch_data.shape != (self.channel_count, self.epoch_total_samples):
        #     print(f"Epoch data invalid. Shape: {epoch_data.shape}, Expected: ({self.channel_count}, {self.epoch_total_samples})")
        #     return None
        
        # 2. Apply the bandpass filter
        filtered_epoch = filtfilt(self.b, self.a, epoch_data, axis=1)
        
        # 3. Apply Common Average Reference (CAR)
        filtered_epoch -= np.mean(filtered_epoch, axis=0, keepdims=True)
        
        return filtered_epoch

    def _compute_erd_percentage(self, pre_power, post_power):
        """
        Private helper to calculate ERD percentage from power values.
        
        Args:
            pre_power (np.array): Power in the pre-stimulus (baseline) period.
            post_power (np.array): Power in the post-stimulus (activation) period.

        Returns:
            np.array: The calculated ERD percentage for each channel.
        """
        erd_percent = np.full(self.channel_count, np.nan)
        non_zero_pre_power_indices = pre_power != 0
        
        erd_percent[non_zero_pre_power_indices] = (
            (post_power[non_zero_pre_power_indices] - pre_power[non_zero_pre_power_indices]) / 
            pre_power[non_zero_pre_power_indices]
        ) * 100
        
        return erd_percent
    def _compute_erd_db(self, pre_power, post_power):
        """
        Private helper to calculate ERD using decibel (dB) correction.
        """
        erd_db = np.full(self.channel_count, np.nan)
        # To avoid math errors, both pre and post power must be positive
        valid_indices = (pre_power > 0) & (post_power > 0)

        # Calculate dB corrected power only for valid indices
        ratio = post_power[valid_indices] / pre_power[valid_indices]
        erd_db[valid_indices] = 10 * np.log10(ratio)
        
        return erd_db
    
    def calculate_erd_from_bandpass(self, epoch_data, return_mean=False):
        """
        Calculates ERD by squaring a bandpassed signal to estimate power.

        Args:
            epoch_data (np.array): The EEG data for a single epoch.
            return_mean (bool): If True, returns the mean ERD of focus channels.
                                If False, returns a dict of ERD values per focus channel.

        Returns:
            float, dict, or None: The calculated ERD value(s) or None on failure.
        """
        processed_epoch = self._preprocess_epoch(epoch_data)
        if processed_epoch is None:
            return None

        # Separate pre and post-stimulus data
        pre_stimulus_data = processed_epoch[:, :self.samples_before_marker]
        post_stimulus_data = processed_epoch[:, self.samples_before_marker:]
        
        # Calculate power for pre and post stimulus periods by squaring
        pre_power = np.nanmean(pre_stimulus_data ** 2, axis=1)
        post_power = np.nanmean(post_stimulus_data ** 2, axis=1)

        # Compute ERD for all channels
        erd_percent_all_channels = self._compute_erd_percentage(pre_power, post_power)
        
        # Extract ERD for focus channels
        erd_focus_values = erd_percent_all_channels[self.focus_channels_indices]

        if return_mean:
            return np.nanmean(erd_focus_values) if np.any(~np.isnan(erd_focus_values)) else None
        else:
            return {self.channel_names[i]: erd_percent_all_channels[i] for i in range(len(erd_percent_all_channels))}

    def calculate_erd_from_welch(self, epoch_data, return_mean=False):
        """
        Calculates ERD using Welch's method for power spectral density estimation.

        Args:
            epoch_data (np.array): The EEG data for a single epoch.
            return_mean (bool): If True, returns the mean ERD of focus channels.
                                If False, returns a dict of ERD values per focus channel.

        Returns:
            float, dict, or None: The calculated ERD value(s) or None on failure.
        """
        if epoch_data.shape != (self.channel_count, self.epoch_total_samples):
            print(f"Epoch data invalid. Shape: {epoch_data.shape}, Expected: ({self.channel_count}, {self.epoch_total_samples})")
            return None

        # Separate pre and post-stimulus data
        pre_stimulus_data = epoch_data[:, :self.samples_before_marker]
        post_stimulus_data = epoch_data[:, self.samples_before_marker:]
        
        # Calculate power spectral density using Welch's method
        f_pre, pxx_pre = welch(pre_stimulus_data, fs=self.sampling_freq, axis=1)
        f_post, pxx_post = welch(post_stimulus_data, fs=self.sampling_freq, axis=1)

        # Find frequency indices for the band of interest
        band_indices = (f_pre >= self.bandpass_low) & (f_pre <= self.bandpass_high)
        if not np.any(band_indices):
            print("Invalid frequency band. Please check bandpass frequencies.")
            return None

        # Calculate average power within the band
        pre_power = np.nanmean(pxx_pre[:, band_indices], axis=1)
        post_power = np.nanmean(pxx_post[:, band_indices], axis=1)

        # Compute ERD for all channels
        erd_percent_all_channels = self._compute_erd_percentage(pre_power, post_power)
        
        # Extract ERD for focus channels
        erd_focus_values = erd_percent_all_channels[self.focus_channels_indices]

        if return_mean:
            return np.nanmean(erd_focus_values) if np.any(~np.isnan(erd_focus_values)) else None
        else:
            if len(erd_percent_all_channels) != len(self.channel_names):
                print("Warning: Number of ERD values does not match number of channel names.")
                return None
            return {self.channel_names[i]: erd_percent_all_channels[i] for i in range(len(self.channel_names))}

    
    def calculate_erd_from_db_correction(self, epoch_data, return_mean=False):
        """
        Calculates ERD based on decibel (dB) baseline correction.

        This method computes ERD by comparing the log-transformed power of the
        activation period to the baseline period. The formula applied is:
        ERD_dB = 10 * log10(Power_activation / Power_baseline)

        Args:
            epoch_data (np.array): The EEG data for a single epoch.
                                   Shape: (n_channels, n_samples)
            return_mean (bool): If True, returns the mean ERD of focus channels.
                                If False, returns a dict of ERD values per focus channel.

        Returns:
            float, dict, or None: The calculated ERD value(s) or None on failure.
        """
        # Preprocess the epoch (bandpass filter + CAR)
        processed_epoch = self._preprocess_epoch(epoch_data)
        if processed_epoch is None:
            return None

        # Calculate instantaneous power by squaring the signal
        power_signal = processed_epoch ** 2

        # Separate pre and post-stimulus power signals
        pre_stimulus_power = power_signal[:, :self.samples_before_marker] # shape: (n_channels, samples_before_marker)
        post_stimulus_power = power_signal[:, self.samples_before_marker:] # shape: (n_channels, samples_after_marker)

        # Calculate average power for pre (baseline) and post (activation) periods
        baseline_power = np.nanmean(pre_stimulus_power, axis=1) # shape: (n_channels,)
        # activation_power = np.nanmean(post_stimulus_power, axis=1)
        # print(pre_stimulus_power.shape, pre_stimulus_power[self.focus_channels_indices, :5])
        # print(baseline_power.shape, baseline_power[self.focus_channels_indices])
        # print(post_stimulus_power.shape, post_stimulus_power[self.focus_channels_indices, :5])
        baseline_corrected_power = np.full((self.channel_count, self.samples_after_marker), np.nan)
        # devide the post-stimulus power by the baseline power and store in baseline_corrected_power
        for i in range(self.channel_count):
            if baseline_power[i] > 0:
                baseline_corrected_power[i, :] = 10* np.log10(post_stimulus_power[i, :] / baseline_power[i])
        
        # Calculate ERD using dB correction formula, handling potential math errors
        # erd_db_all_channels = np.full(self.channel_count, np.nan)
        
        # To avoid division by zero or log(0), only calculate for positive baseline power
        # valid_indices = baseline_power > 0
        # valid_indices = baseline_corrected_power > 0
        
        # ratio = np.full(self.channel_count, np.nan)
        # ratio[valid_indices] = baseline_corrected_power[valid_indices].mean(axis=1)
        ratio = np.nanmean(baseline_corrected_power, axis=1)  # shape: (n_channels,)
        # print(f"Ratio shape: {ratio.shape}, {ratio[0:5]}")
        
        # Calculate the ratio of activation to baseline power
        # ratio = np.full(self.channel_count, np.nan)
        # ratio[valid_indices] = activation_power[valid_indices] / baseline_power[valid_indices]
        # Calculate log10 only for positive ratios to avoid math errors
        # erd_db_all_channels[valid_ratio_indices] = 10 * np.log10(ratio[valid_ratio_indices])\
        erd_db_all_channels = ratio

        # Extract ERD for focus channels
        erd_focus_values = erd_db_all_channels[self.focus_channels_indices]

        # Return based on 'return_mean' flag
        if return_mean:
            return np.nanmean(erd_focus_values) if np.any(~np.isnan(erd_focus_values)) else None
        else:
            return {self.channel_names[i]: erd_db_all_channels[i] for i in range(len(erd_db_all_channels))}
    
    def calculate_erd_moving_average(self, epoch_data, window_size_samples, return_mean=True, method='percentage'):
        """
        Calculates ERD using a moving average approach with a selectable calculation method.

        Args:
            epoch_data (np.array): The EEG data for a single epoch.
            window_size_samples (int): The size of the moving window in samples.
            return_mean (bool): If True, returns the mean ERD of focus channels.
                                If False, returns a dict of ERD values per focus channel.
            method (str): The calculation method to use. Options: 'percentage', 'db'.
                          Defaults to 'percentage'.

        Returns:
            float, dict, or None: The calculated ERD value(s) or None if calculation fails.
        """
        processed_epoch = self._preprocess_epoch(epoch_data)
        if processed_epoch is None:
            return None

        pre_stimulus_data = processed_epoch[:, :self.samples_before_marker]
        post_stimulus_data = processed_epoch[:, self.samples_before_marker:]

        pre_len, post_len = pre_stimulus_data.shape[1], post_stimulus_data.shape[1]
        if not (0 < window_size_samples <= pre_len and window_size_samples <= post_len):
            print(f"Window size ({window_size_samples}) is invalid for pre ({pre_len}) or post ({post_len}) data lengths.")
            return None

        num_windows = min(pre_len, post_len) - window_size_samples + 1
        if num_windows <= 0:
            print("Not enough samples to form any full window pairs.")
            return None

        all_window_erds = np.full((self.channel_count, num_windows), np.nan)

        for i in range(num_windows):
            pre_power = np.mean(pre_stimulus_data[:, i:i + window_size_samples]**2, axis=1)
            post_power = np.mean(post_stimulus_data[:, i:i + window_size_samples]**2, axis=1)

            # Select the calculation method based on the 'method' parameter
            if method == 'percentage':
                erd_window = self._compute_erd_percentage(pre_power, post_power)
            elif method == 'db_correction':
                erd_window = self._compute_erd_db(pre_power, post_power)
            else:
                print(f"Invalid method '{method}'. Please choose 'percentage' or 'db'.")
                return None
            
            all_window_erds[:, i] = erd_window

        mean_erd_all_channels = np.nanmean(all_window_erds, axis=1)
        erd_focus_values = mean_erd_all_channels[self.focus_channels_indices]
        
        if np.all(np.isnan(erd_focus_values)):
            print("No valid ERD values could be calculated from any moving window.")
            return None

        if return_mean:
            return np.nanmean(erd_focus_values)
        else:
            return {self.channel_names[i]: mean_erd_all_channels[i] for i in range(len(self.channel_names))}

    def calculate_erd_across_trials(self, data_df, markers_df, subject_id=None):
        """
        Calculates average ERD/ERS across all trials for each stimulus type.
        This method works by first averaging the power across trials and then
        calculating ERD once from this averaged power profile.
        
        Args:
            data_df (pd.DataFrame): DataFrame with channels as columns and samples as rows.
            markers_df (pd.DataFrame): DataFrame with 'onset' (in samples) and 'description' columns.
            subject_id (any): Optional identifier for the subject.

        Returns:
            dict: A dictionary where keys are stimulus descriptions and values are the mean ERD.
        """
        epochs_by_stimulus = {}
        for row in markers_df.itertuples():
            # Filter for focus stimuli if specified
            if self.focus_stimuli and row.description not in self.focus_stimuli:
                continue

            # Define epoch boundaries and extract data
            start_sample = row.onset - self.samples_before_marker
            end_sample = row.onset + self.samples_after_marker

            if start_sample >= 0 and end_sample < len(data_df):
                epoch_raw = data_df.iloc[start_sample:end_sample].values.T
                
                # Preprocess the epoch (filter and CAR)
                epoch_processed = self._preprocess_epoch(epoch_raw)
                if epoch_processed is None:
                    continue
                
                # Square to get instantaneous power
                epoch_power = epoch_processed ** 2
                
                # Group power epochs by stimulus description
                if row.description not in epochs_by_stimulus:
                    epochs_by_stimulus[row.description] = []
                epochs_by_stimulus[row.description].append(epoch_power)
        
        erd_results = {}
        for stimulus, epochs_list in epochs_by_stimulus.items():
            if not epochs_list:
                continue

            # Average power across all trials for this stimulus
            mean_power_across_trials = np.nanmean(np.stack(epochs_list, axis=2), axis=2)
            
            # Get mean power for baseline and activation periods
            mean_baseline_power = np.nanmean(mean_power_across_trials[:, :self.samples_before_marker], axis=1)
            mean_activation_power = np.nanmean(mean_power_across_trials[:, self.samples_before_marker:], axis=1)
            
            # Calculate ERD for all channels based on the averaged power
            erd_percent = self._compute_erd_percentage(mean_baseline_power, mean_activation_power)
            
            # Get the mean ERD for the focus channels
            erd_percent_focus = erd_percent[self.focus_channels_indices]
            
            if np.any(~np.isnan(erd_percent_focus)):
                erd_results[stimulus] = np.nanmean(erd_percent_focus)
            else:
                erd_results[stimulus] = None
                
        if subject_id is not None:
            erd_results['subject_id'] = subject_id
            
        return erd_results