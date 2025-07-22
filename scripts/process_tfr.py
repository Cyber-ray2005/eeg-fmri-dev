# process_tfr.py

import os

import argparse

import mne

import numpy as np

import pandas as pd

import sys



def process_all_subjects(data_dir, output_path):

    """

    Finds all .vhdr files in a directory, computes TFR for each,

    aggregates the results, and saves them to a file.

    """

    print(f"Searching for .vhdr files in: {data_dir}")

    try:

        vhdr_files = [f for f in os.listdir(data_dir) if f.endswith('.vhdr')]

        if not vhdr_files:

            print("Error: No .vhdr files found in the specified directory.", file=sys.stderr)

            sys.exit(1)

    except FileNotFoundError:

        print(f"Error: Data directory not found at '{data_dir}'", file=sys.stderr)

        sys.exit(1)



    all_tfr_dfs = []



    for file_name in vhdr_files:

        subject_id = os.path.splitext(file_name)[0]

        print(f"Processing subject: {subject_id}...")

        vhdr_path = os.path.join(data_dir, file_name)



        try:

            raw_data = mne.io.read_raw_brainvision(vhdr_path, preload=True, verbose=False)

            events, event_id = mne.events_from_annotations(raw_data, verbose=False)

            event_id = {x.split('/')[1]: y for x, y in event_id.items()}



            tmin, tmax = -1.5, 1.5

            picks = mne.pick_channels(raw_data.ch_names, include=["C3", "C4", "CP3", "CP1"])

            

            # Reduce memory by not preloading epochs initially if RAM is an issue

            epochs = mne.Epochs(raw_data, events, event_id, tmin=tmin, tmax=tmax, 

                                picks=picks, baseline=None, preload=True, verbose=False)



            freqs = np.arange(8, 30)

            baseline = (-1, 0)



            tfr = epochs.compute_tfr(

                freqs=freqs, n_cycles=freqs / 2, return_itc=False, average=False,

                method='multitaper', use_fft=True, verbose=False, n_jobs=-1 # Use all available CPUs

            )

            tfr.crop(tmin=tmin, tmax=tmax).apply_baseline(baseline=baseline, mode='percent', verbose=False)



            tfr_df = tfr.copy().crop(tmin=-1, tmax=1.0).to_data_frame()

            tfr_df['subject'] = subject_id

            all_tfr_dfs.append(tfr_df)

            print(f"Finished subject: {subject_id}")



        except Exception as e:

            print(f"Could not process {file_name}. Error: {e}", file=sys.stderr)

            continue

            

    if not all_tfr_dfs:

        print("No subjects were processed successfully. Exiting.", file=sys.stderr)

        sys.exit(1)



    print("\nConcatenating data from all subjects...")

    final_tfr_df = pd.concat(all_tfr_dfs, ignore_index=True)

    

    print("Aggregating final DataFrame...")

    # Group by all relevant columns and average the channel data

    tfr_df_agg = final_tfr_df.groupby(['subject', 'condition', 'time', 'freq']).mean().reset_index()

    # Drop the now-unnecessary epoch column

    if 'epoch' in tfr_df_agg.columns:

        tfr_df_agg = tfr_df_agg.drop(columns=['epoch'])

    

    # Save the aggregated dataframe

    print(f"Saving aggregated data to {output_path}")

    tfr_df_agg.to_parquet(output_path, index=False)



    print("Processing complete.")





if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Process BrainVision data to generate and save TFR.")

    parser.add_argument("data_dir", type=str, help="The directory containing the .vhdr data files.")

    parser.add_argument("output_path", type=str, help="The path to save the final Parquet file.")

    

    args = parser.parse_args()

    

    process_all_subjects(args.data_dir, args.output_path)
