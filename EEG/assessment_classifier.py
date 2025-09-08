#!/usr/bin/env python3
"""
Assessment Classifier - Motor Imagery EEG Analysis Pipeline

This script automates the complete EEG analysis pipeline from the analysis.ipynb notebook,
providing ERD analysis results for motor imagery assessment data.

Features:
- Configurable data paths and participant names
- Multiple ERD calculation methods (bandpass, welch, db_correction, moving_average)
- Automated data loading from BrainVision format or NumPy arrays
- Summary statistics generation using get_summary function
- Focus on C3, C1, CP3, CP1 channels for motor cortex analysis

Usage:
    python assessment_classifier.py --participant randy
    python assessment_classifier.py -p john --data_dir ./custom/path/
"""

import numpy as np
import pandas as pd
import mne
import os
import argparse
from ERDCalculator.ERDCalculator import ERDCalculator


class AssessmentConfig:
    """
    Configuration class for EEG analysis parameters and file paths.
    Modify these settings to match your experimental setup.
    """
    def __init__(self, participant=None, data_dir=None):
        # === DATA PATH CONFIGURATION ===
        self.DATA_DIR = data_dir if data_dir else './data/rawdata/'  # Base directory for raw data files
        
        # Participant identifier is required - must be provided at runtime
        if participant is None:
            raise ValueError("Participant identifier is required. Use --participant argument.")
        self.PARTICIPANT = participant
        
        # === EEG DATA PARAMETERS ===
        self.FOCUS_CHANNEL_NAMES = ["C3", "C1", "CP3", "CP1"]  # Motor cortex channels
        self.BAD_CHANNELS = ['FT9', 'TP9', 'FT10', 'TP10']  # Channels to exclude from analysis
        
        # === EPOCHING PARAMETERS ===
        self.EPOCH_PRE_STIMULUS_SECONDS = 2.0   # Baseline period before stimulus
        self.EPOCH_POST_STIMULUS_SECONDS = 2.0  # Analysis period after stimulus
        
        # === FILTERING PARAMETERS ===
        self.BANDPASS_LOW = 8.0   # Low cutoff frequency (Hz) - Alpha/Beta band
        self.BANDPASS_HIGH = 30.0 # High cutoff frequency (Hz)
        
        # === ERD ANALYSIS METHODS ===
        # Available methods: 'bandpass', 'welch', 'db_correction', 'moving_average'
        self.ERD_METHODS = ['bandpass', 'welch', 'db_correction', 'moving_average']
        
        # === MOVING AVERAGE SPECIFIC PARAMETERS ===
        self.MOVING_AVERAGE_WINDOW_SIZE = 75  # Window size in samples
        self.MOVING_AVERAGE_METHOD = 'percentage'  # 'percentage' or 'db'
        
        # === STIMULUS MAPPING ===
        self.EVENTS_MAP = {
            "sixth": 6,   # Sixth finger (supernumerary)
            "thumb": 1,
            "index": 2,
            "middle": 3,
            "ring": 4,
            "pinky": 5,
            "blank": 7    # Rest condition
        }


class AssessmentClassifier:
    """
    Main class for running EEG motor imagery analysis pipeline.
    
    This class replicates the functionality from analysis.ipynb, providing:
    1. Data loading from BrainVision files
    2. ERD calculation using multiple methods
    3. Summary statistics generation
    4. Results output and logging
    """
    
    def __init__(self, config=None):
        """
        Initialize the classifier with configuration parameters.
        
        Args:
            config (AssessmentConfig): Configuration object with analysis parameters
        """
        self.config = config if config else AssessmentConfig()
        self.raw_data = None
        self.events = None
        self.event_id = None
        self.data_df = None
        self.markers_df = None
        self.erd_calculator = None
        self.focus_channels_indices = None
        
    def load_data(self):
        """
        Load EEG data from BrainVision format files.
        Automatically constructs file paths based on participant name.
        """
        print(f"=== Loading Data for Participant: {self.config.PARTICIPANT} ===")
        
        # Construct file paths
        participant_dir = os.path.join(self.config.DATA_DIR, self.config.PARTICIPANT)
        vhdr_file = os.path.join(participant_dir, f"{self.config.PARTICIPANT}.vhdr")
        
        # Check if files exist
        if not os.path.exists(vhdr_file):
            raise FileNotFoundError(f"BrainVision header file not found: {vhdr_file}")
        
        print(f"Loading BrainVision file: {vhdr_file}")
        
        # Load raw data
        self.raw_data = mne.io.read_raw_brainvision(vhdr_file, preload=True, verbose=False)
        
        # Extract events from annotations
        self.events, self.event_id = mne.events_from_annotations(self.raw_data, verbose=False)
        
        # Print basic information
        sfreq = self.raw_data.info['sfreq']
        n_channels = len(self.raw_data.ch_names)
        highpass = self.raw_data.info['highpass']
        lowpass = self.raw_data.info['lowpass']
        
        print(f"Sampling Frequency: {sfreq} Hz")
        print(f"Number of Channels: {n_channels}")
        print(f"Highpass Filter: {highpass} Hz")
        print(f"Lowpass Filter: {lowpass} Hz")
        
        # Prepare data for analysis
        self._prepare_data_for_analysis()
        
    def _prepare_data_for_analysis(self):
        """
        Prepare loaded data for ERD analysis:
        1. Remove bad channels
        2. Create focus channel indices
        3. Convert to DataFrame format
        4. Prepare markers DataFrame
        """
        print("\n=== Preparing Data for Analysis ===")
        
        # Get clean channel names (excluding bad channels)
        clean_channel_names = [ch for ch in self.raw_data.ch_names if ch not in self.config.BAD_CHANNELS]
        
        # Find indices of focus channels
        self.focus_channels_indices = []
        for ch in self.config.FOCUS_CHANNEL_NAMES:
            if ch in clean_channel_names:
                self.focus_channels_indices.append(clean_channel_names.index(ch))
            else:
                print(f"Warning: Focus channel '{ch}' not found in clean channel list")
        
        print(f"Focus channels: {self.config.FOCUS_CHANNEL_NAMES}")
        print(f"Focus channel indices: {self.focus_channels_indices}")
        
        # Convert raw data to DataFrame and remove bad channels + time column
        columns_to_drop = ['time'] + self.config.BAD_CHANNELS
        self.data_df = self.raw_data.to_data_frame().drop(columns=columns_to_drop, errors='ignore')
        
        # Prepare events DataFrame - filter for relevant stimulus codes (1-7)
        events_df = pd.DataFrame(self.events, columns=['onset', 'duration', 'description'])
        self.markers_df = events_df[events_df['description'].isin(list(range(1, 8)))].copy()
        
        print(f"Data shape: {self.data_df.shape}")
        print(f"Number of markers: {len(self.markers_df)}")
        print(f"Marker distribution:")
        print(self.markers_df['description'].value_counts().sort_index())
        
        # Initialize ERD Calculator
        self._initialize_erd_calculator(clean_channel_names)
        
    def _initialize_erd_calculator(self, channel_names):
        """
        Initialize the ERD Calculator with current configuration.
        
        Args:
            channel_names (list): List of clean channel names for analysis
        """
        sfreq = self.raw_data.info['sfreq']
        
        self.erd_calculator = ERDCalculator(
            sampling_freq=sfreq,
            epoch_pre_stimulus_seconds=self.config.EPOCH_PRE_STIMULUS_SECONDS,
            epoch_post_stimulus_seconds=self.config.EPOCH_POST_STIMULUS_SECONDS,
            bandpass_low=self.config.BANDPASS_LOW,
            bandpass_high=self.config.BANDPASS_HIGH,
            channel_names=channel_names,
            focus_channels_indices=self.focus_channels_indices
        )
        
        print(f"ERD Calculator initialized with {len(channel_names)} channels")
        
    def calculate_erd_for_all_markers(self, method='bandpass', per_channel=False,
                                    moving_average_window_size=100, moving_average_method='percentage'):
        """
        Calculate ERD values for all markers using the specified method.
        
        This function replicates the calculate_erd_for_all_markers from analysis.ipynb.
        
        Args:
            method (str): ERD computation method ('bandpass', 'welch', 'db_correction', 'moving_average')
            per_channel (bool): If True, returns ERD values per channel
            moving_average_window_size (int): Window size for moving average method
            moving_average_method (str): Method for moving average ('percentage' or 'db')
            
        Returns:
            list: List of dictionaries containing ERD results
        """
        print(f"\n--- Calculating ERD using method: '{method}' ---")
        
        results = []
        processed_epochs = 0
        
        for idx, marker_row in self.markers_df.iterrows():
            marker_onset = int(marker_row['onset'])
            stimulus_description = int(marker_row['description'])
            
            # Extract epoch data around the marker
            epoch_start = marker_onset - self.erd_calculator.samples_before_marker
            epoch_end = marker_onset + self.erd_calculator.samples_after_marker
            
            # Check bounds
            if epoch_start < 0 or epoch_end >= len(self.data_df):
                print(f"Skipping epoch at sample {marker_onset}: out of bounds")
                continue
                
            # Extract epoch data and transpose to (channels, samples)
            epoch_data = self.data_df.iloc[epoch_start:epoch_end].values.T
            
            # Calculate ERD using the specified method
            erd_value = None
            erds = None  # For moving average method
            
            if method == 'bandpass':
                erd_value = self.erd_calculator.calculate_erd_from_bandpass(epoch_data, return_mean=True)
            elif method == 'welch':
                erd_value = self.erd_calculator.calculate_erd_from_welch(epoch_data, return_mean=True)
            elif method == 'db_correction':
                erd_value = self.erd_calculator.calculate_erd_from_db_correction(epoch_data, return_mean=True)
            elif method == 'moving_average':
                result = self.erd_calculator.calculate_erd_moving_average(
                    epoch_data, 
                    window_size_samples=moving_average_window_size,
                    return_mean=True, 
                    method=moving_average_method
                )
                if isinstance(result, tuple):
                    erd_value, erds = result
                else:
                    erd_value = result
            else:
                raise ValueError(f"Unknown method '{method}'. Supported methods are: {self.config.ERD_METHODS}")
            
            # Store results
            if erd_value is not None and not np.isnan(erd_value):
                result_dict = {
                    'stimulus': stimulus_description,
                    'erd_value': erd_value
                }
                if erds is not None:
                    result_dict['erds'] = erds
                results.append(result_dict)
                processed_epochs += 1
        
        print(f"Finished ERD calculation. Successfully processed {processed_epochs} epochs.")
        return results
    
    def get_summary(self, erd_results, boundary, target_value='erd_value'):
        """
        Generate summary statistics for ERD results by stimulus category.
        
        This function replicates the get_summary function from analysis.ipynb.
        
        Args:
            erd_results (pd.DataFrame): DataFrame containing ERD values and stimulus labels
            boundary (float): Threshold to filter ERD values by sign
            target_value (str): Column name to summarize
            
        Returns:
            pd.DataFrame: Summary table with mean, std dev, and count for each category
        """
        # Define stimulus categories (NT=Normal Touch, ST=Sixth finger Touch, Rest)
        STIMULUS_CATEGORIES = {
            'NT': {'stimulus_values': list(range(1, 6))},  # Fingers 1-5 (thumb to pinky)
            'ST': {'stimulus_values': [6]},                # Sixth finger
            'Rest': {'stimulus_values': [7]},              # Rest condition
        }
        
        summary_data = []
        
        # Loop through each category and compute statistics
        for category_name, conditions in STIMULUS_CATEGORIES.items():
            stim_values = conditions['stimulus_values']
            
            # Apply filtering based on boundary and category
            if category_name in ['NT', 'ST']:
                # For motor imagery, we expect negative ERD (desynchronization)
                filtered_df = erd_results[
                    (erd_results[target_value] < boundary) &
                    (erd_results['stimulus'].isin(stim_values))
                ]
            else:  # 'Rest' category
                # For rest, we expect positive ERD (synchronization) or different pattern
                filtered_df = erd_results[
                    (erd_results[target_value] > boundary) &
                    (erd_results['stimulus'].isin(stim_values))
                ]
            
            # Calculate summary statistics
            std_val = filtered_df[target_value].std()
            mean_val = filtered_df[target_value].mean()
            count_val = filtered_df[target_value].count()
            
            # Total number of trials for the category
            total_trials = len(erd_results[erd_results['stimulus'].isin(stim_values)])
            
            # Append statistics to summary
            summary_data.append({
                'Category': category_name,
                'Mean': f'{mean_val:.3f}',
                'Std Dev': f'{std_val:.3f}',
                'Count': f'{count_val}/{total_trials} ({(count_val/total_trials*100):.2f}%)'
            })
        
        return pd.DataFrame(summary_data)
    
    def run_analysis(self):
        """
        Run the complete ERD analysis pipeline for all configured methods.
        This replicates the main analysis loop from analysis.ipynb.
        """
        print("\n" + "="*60)
        print("=== MOTOR IMAGERY ERD ANALYSIS RESULTS ===")
        print("="*60)
        
        all_results = {}
        
        # Loop through each ERD computation method
        for method_name in self.config.ERD_METHODS:
            print(f"\n## Analysis for Method: '{method_name.capitalize()}'")
            print("-" * (len(method_name) + 26))
            
            # Calculate ERD values
            if method_name == "moving_average":
                # Special parameters for moving average method
                results = self.calculate_erd_for_all_markers(
                    method="moving_average",
                    moving_average_window_size=self.config.MOVING_AVERAGE_WINDOW_SIZE,
                    moving_average_method=self.config.MOVING_AVERAGE_METHOD
                )
            else:
                # Standard methods
                results = self.calculate_erd_for_all_markers(method=method_name)
            
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            if len(results_df) == 0:
                print("No valid ERD results obtained for this method.")
                continue
            
            # Generate summary statistics
            summary_df = self.get_summary(results_df, boundary=0, target_value='erd_value')
            
            # Print formatted summary
            print(summary_df.to_string(index=False))
            
            # Print total count
            total_count = summary_df['Count'].apply(lambda x: int(x.split('/')[0])).sum()
            print(f"Total: {total_count}")
            
            # Store results for potential further analysis
            all_results[method_name] = {
                'results_df': results_df,
                'summary_df': summary_df
            }
        
        print("\n" + "="*60)
        print("=== ANALYSIS COMPLETE ===")
        print("="*60)
        
        return all_results
    
    def run_single_method_analysis(self, method='moving_average'):
        """
        Run analysis for a single ERD method and return detailed results.
        
        Args:
            method (str): ERD method to use
            
        Returns:
            dict: Dictionary containing results DataFrame and summary DataFrame
        """
        print(f"\n=== Running Single Method Analysis: {method} ===")
        
        if method == "moving_average":
            results = self.calculate_erd_for_all_markers(
                method="moving_average",
                moving_average_window_size=self.config.MOVING_AVERAGE_WINDOW_SIZE,
                moving_average_method=self.config.MOVING_AVERAGE_METHOD
            )
        else:
            results = self.calculate_erd_for_all_markers(method=method)
        
        results_df = pd.DataFrame(results)
        
        if len(results_df) == 0:
            print("No valid ERD results obtained.")
            return None
        
        summary_df = self.get_summary(results_df, boundary=0, target_value='erd_value')
        
        print("\n--- Summary Results ---")
        print(summary_df.to_string(index=False))
        total_count = summary_df['Count'].apply(lambda x: int(x.split('/')[0])).sum()
        print(f"Total: {total_count}")
        
        return {
            'results_df': results_df,
            'summary_df': summary_df,
            'method': method
        }


def parse_arguments():
    """
    Parse command-line arguments for the assessment classifier.
    
    Returns:
        argparse.Namespace: Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="Motor Imagery EEG Assessment Classifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python assessment_classifier.py --participant randy
    python assessment_classifier.py -p john --data_dir ./custom/path/
    python assessment_classifier.py -p sarah -d /path/to/data --method moving_average
        """
    )
    
    parser.add_argument(
        '-p', '--participant',
        type=str,
        required=True,
        help='Participant identifier (used for file naming, e.g., "randy" for randy.vhdr)'
    )
    
    parser.add_argument(
        '-d', '--data_dir',
        type=str,
        default='./data/rawdata/',
        help='Base directory containing participant data folders (default: ./data/rawdata/)'
    )
    
    parser.add_argument(
        '-m', '--method',
        type=str,
        choices=['bandpass', 'welch', 'db_correction', 'moving_average', 'all'],
        default='all',
        help='ERD calculation method to use (default: all methods)'
    )
    
    parser.add_argument(
        '--window_size',
        type=int,
        default=75,
        help='Window size for moving average method in samples (default: 75)'
    )
    
    return parser.parse_args()


def main():
    """
    Main execution function for the assessment classifier.
    """
    try:
        # Parse command-line arguments
        args = parse_arguments()
        
        print(f"=== Motor Imagery EEG Assessment Classifier ===")
        print(f"Participant: {args.participant}")
        print(f"Data Directory: {args.data_dir}")
        print(f"Method: {args.method}")
        
        # Initialize configuration with runtime parameters
        config = AssessmentConfig(
            participant=args.participant,
            data_dir=args.data_dir
        )
        
        # Update moving average window size if specified
        config.MOVING_AVERAGE_WINDOW_SIZE = args.window_size
        
        # Create classifier instance
        classifier = AssessmentClassifier(config)
        
        # Load and prepare data
        classifier.load_data()
        
        # Run analysis based on specified method
        if args.method == 'all':
            # Run complete analysis with all methods
            all_results = classifier.run_analysis()
            
            # Also run detailed analysis for moving average method
            print("\n" + "="*60)
            print("=== DETAILED MOVING AVERAGE ANALYSIS ===")
            print("="*60)
            detailed_results = classifier.run_single_method_analysis('moving_average')
            
            return all_results, detailed_results
        else:
            # Run analysis for single method
            results = classifier.run_single_method_analysis(args.method)
            return results
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        raise


if __name__ == "__main__":
    results = main()
