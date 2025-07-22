# process_all_mats_mem_efficient.py



import os

import sys

import argparse

import pandas as pd

import numpy as np

import mne

import scipy.io as sio

import gc # Import the Garbage Collector interface



#

# --- Your Data Loading and TFR Functions (Unchanged) ---

#

def load_and_process_mat_file(file_path):

    """Loads and processes a .mat file."""

    # (This function is identical to your provided one)

    raw_data = sio.loadmat(file_path)

    o = raw_data['o'][0][0]

    sampling_frequency = o[2][0][0]

    num_samples = o[3][0][0]

    markers = o[4]

    data = o[5]

    channel_names = [channel[0][0] for channel in o[6]]

    data_df = pd.DataFrame(data, columns=channel_names)

    markers_df = pd.DataFrame(markers, columns=['description'])

    markers_df.reset_index(inplace=True)

    markers_df.rename(columns={'index': 'onset'}, inplace=True)

    is_new_marker_start = (markers_df['description'] != 0) & \
                          (markers_df['description'].shift(1) != markers_df['description'])

    markers_df = markers_df[is_new_marker_start].copy()

    return data_df, markers_df, sampling_frequency, num_samples, channel_names



def compute_tfr_from_mat(file_path, tmin=-1.5, tmax=1.5, baseline=(-1.0, 0)):

    """Computes an unaveraged TFR from a .mat file."""

    # (This function is also identical to the previous version)

    data_df, markers_df, sfreq, _, ch_names = load_and_process_mat_file(file_path)

    data_for_mne = data_df.values.T

    ch_types = ['eeg'] * len(ch_names)

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types=ch_types)

    raw = mne.io.RawArray(data_for_mne, info, verbose=False)

    events = np.array([markers_df['onset'], np.zeros(len(markers_df)), markers_df['description']]).T.astype(int)

    unique_markers = markers_df['description'].unique()

    event_id = {f"event_{marker}": marker for marker in unique_markers}

    epochs = mne.Epochs(raw, events, event_id, tmin=tmin, tmax=tmax, preload=True, baseline=None, verbose=False)

    freqs = np.arange(8., 30.)

    n_cycles = freqs / 2.

    tfr = epochs.compute_tfr(method='multitaper', freqs=freqs, n_cycles=n_cycles, use_fft=True, return_itc=False, average=False, verbose=False, n_jobs=-1)

    tfr.apply_baseline(mode='percent', baseline=baseline, verbose=False)

    return tfr



#

# --- NEW: Memory-Efficient Main Processing Loop ---

#

def main(data_dir, output_path):

    """

    Main function that processes each file and saves its result to a temporary

    file to keep memory usage low, then combines them at the end.

    """

    # Create a directory for temporary files

    temp_dir = os.path.join(os.path.dirname(output_path), 'temp_tfr_results')

    os.makedirs(temp_dir, exist_ok=True)

    print(f"Temporary files will be stored in: {temp_dir}")



    try:

        mat_files = [f for f in os.listdir(data_dir) if f.endswith('.mat')]

        if not mat_files:

            print(f"Error: No .mat files found in '{data_dir}'", file=sys.stderr)

            sys.exit(1)

        print(f"Found {len(mat_files)} .mat files to process.")

    except FileNotFoundError:

        print(f"Error: Data directory not found at '{data_dir}'", file=sys.stderr)

        sys.exit(1)

        

    # --- Part 1: Process each file and save its result individually ---

    for file_name in mat_files:

        subject_id = os.path.splitext(file_name)[0]

        file_path = os.path.join(data_dir, file_name)

        temp_output_path = os.path.join(temp_dir, f"{subject_id}.parquet")

        

        # Check if the result for this subject already exists

        if os.path.exists(temp_output_path):

            print(f"Skipping already processed subject: {subject_id}")

            continue

            

        print(f"\n--- Processing subject: {subject_id} ---")

        try:

            # Compute TFR (memory intensive)

            tfr = compute_tfr_from_mat(file_path)

            

            # Convert to DataFrame (memory intensive)

            tfr_df = tfr.copy().crop(-1, 1).to_data_frame()

            

            # Aggregate THIS SUBJECT ONLY (greatly reduces size)

            aggregated_subject_df = tfr_df.groupby(['condition', 'time', 'freq']).mean().reset_index()

            

            # Save the small, aggregated result for this subject

            aggregated_subject_df.to_parquet(temp_output_path, index=False)

            print(f"Saved temporary result for {subject_id} to {temp_output_path}")



            # **CRUCIAL STEP: Free up memory**

            del tfr, tfr_df, aggregated_subject_df

            gc.collect() # Ask the garbage collector to release the memory now



        except Exception as e:

            print(f"Could not process {file_name}. Error: {e}", file=sys.stderr)

            continue



    # --- Part 2: Combine all the small, temporary files ---

    print("\n--- Combining all temporary results ---")

    temp_files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith('.parquet')]

    

    if not temp_files:

        print("No temporary results found to combine. Exiting.", file=sys.stderr)

        sys.exit(1)



    all_subjects_dfs = []

    for f in temp_files:

        subject_id = os.path.splitext(os.path.basename(f))[0]

        df = pd.read_parquet(f)

        df['subject'] = subject_id

        all_subjects_dfs.append(df)

        

    final_df = pd.concat(all_subjects_dfs, ignore_index=True)



    # Reorder columns for clarity

    cols = ['subject', 'condition', 'time', 'freq'] + [c for c in final_df.columns if c not in ['subject', 'condition', 'time', 'freq']]

    final_df = final_df[cols]



    # Save the final combined file

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    final_df.to_parquet(output_path, index=False)

    print(f"\nSuccessfully saved final aggregated data to {output_path}")

    print("Final DataFrame head:")

    print(final_df.head())

    

    # Optional: Clean up temporary directory

    # import shutil

    # shutil.rmtree(temp_dir)

    # print(f"Removed temporary directory: {temp_dir}")





if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Memory-efficiently process .mat EEG files to generate and save aggregated TFR results.")

    parser.add_argument("data_dir", type=str, help="The directory containing the .mat data files.")

    parser.add_argument("output_path", type=str, help="The path to save the final aggregated Parquet file.")

    args = parser.parse_args()

    main(args.data_dir, args.output_path)
