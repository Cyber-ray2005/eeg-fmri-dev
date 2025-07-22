# Utilities for Motor Imagery EEG Experiment Suite

This folder contains utility modules that support the main experiment scripts (`training.py`, `assessment.py`, `collect_data.py`, etc.). These modules provide core functionality for stimulus display, data logging, trial generation, hardware communication, data emulation, and more.

## Contents

- [`EEGVisualizer.py`](#eegvisualizerpy)
- [`pygame_display.py`](#pygame_displaypy)
- [`logger.py`](#loggerpy)
- [`trial_generator.py`](#trial_generatorpy)
- [`serial_communication.py`](#serial_communicationpy)
- [`emulator.py`](#emulatorpy)
- [`tcp_client.py`](#tcp_clientpy)
- [`livestream_receiver.py`](#livestream_receiverpy)
- [`mock_eeg_server.py`](#mock_eeg_serverpy)
- [`read_npy.py`](#read_npypy)

---

### `EEGVisualizer.py`
A PyQt5/pyqtgraph-based GUI for real-time visualization of EEG data and event markers streamed over TCP. Connects to the ERD broadcaster (e.g., `collect_data.py`) and displays multi-channel EEG traces with live marker annotations.

---

### `pygame_display.py`
Handles all visual presentation for the experiment using Pygame. Features include:
- Fullscreen or windowed display setup.
- Loading and scaling of all stimulus images.
- Display of fixation crosses, images, feedback bars, messages, and timers.
- Support for multi-line and color-tagged text.
- User input handling for yes/no questions and experiment control.

---

### `logger.py`
Provides two logging utilities:
- `TrialDataLogger`: Collects and saves structured trial-by-trial data to CSV files, with customizable fieldnames and filenames.
- `TextLogger`: Appends unstructured text messages (optionally timestamped) to a log file for session/event tracking.

---

### `trial_generator.py`
Generates randomized and balanced trial lists for each experiment block, enforcing constraints such as maximum consecutive trials of the same category. Ensures fair distribution of all trial types (e.g., sixth finger, normal fingers, blank).

---

### `serial_communication.py`
Manages serial port communication for sending event triggers to external hardware (e.g., EEG amplifiers). Handles port initialization, trigger transmission, and safe closure.

---

### `emulator.py`
Simulates a live EEG data stream by reading from pre-recorded BrainVision files. Provides data chunks and event markers in the same format as a real EEG server, enabling development and testing without hardware.

---

### `tcp_client.py`
Implements a TCP client for connecting to the ERD broadcaster. Supports background listening (in a thread), data queueing, and clean shutdown. Used by experiment scripts to receive live ERD feedback.

---

### `livestream_receiver.py`
Connects to a live EEG data server (e.g., LSL or a compatible TCP server), receives and unpacks data blocks and event markers, and provides them to the experiment scripts. Supports optional broadcasting of classification results.

---

### `mock_eeg_server.py`
A standalone script that simulates a live EEG server for development and testing. Streams synthetic EEG data and periodic event markers to any connected clients, mimicking the protocol expected by `livestream_receiver.py`.

---

### `read_npy.py`
A simple utility script to quickly load and print the contents of a saved EEG data `.npy` file (e.g., `collected_eeg_data.npy`).

---

## Usage

These modules are not typically run directly (except for `mock_eeg_server.py` and `read_npy.py` for testing). Instead, they are imported and used by the main experiment scripts. See the docstrings and comments in each file for detailed usage and API documentation.

--- 