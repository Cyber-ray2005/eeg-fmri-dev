import numpy as np

# --- read_npy.py: Quick NPY File Reader ---

# Load the NPY file
# This script loads and prints the contents of a saved EEG data .npy file (e.g., collected_eeg_data.npy)
data = np.load('collected_eeg_data.npy')

# Print the loaded array
print(data)