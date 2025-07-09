# Motor Imagery EEG Experiment Suite

This project provides a comprehensive suite of tools for conducting motor imagery experiments involving EEG data. It features real-time EEG acquisition and processing, visual stimulus presentation, serial trigger synchronization, and live data broadcasting, all built with a modular and extensible architecture.

---

## 🌟 Key Features

* **Flexible EEG Data Acquisition (`collect_data.py`):**
    * Connects to either a live EEG streaming source (e.g., LSL via `livestream_receiver.py`) or an internal data emulator (`emulator.py`).
    * Performs real-time signal processing, including band-pass filtering and Event-Related Desynchronization (ERD) calculation for specified channels.
    * **Live TCP Broadcasting:** Transmits real-time ERD results over a TCP socket (`collect_data.py` acts as the server), allowing external applications like `EEGVisualizer.py` or `tcp_client.py` to consume the processed data.
    * **Comprehensive Data Logging:** Saves raw EEG data (as `.npy` files) and associated markers (as `.csv`) for post-experiment analysis in the `data/` directory.

* **Experiment Phases (`training.py`, `assessment.py`):**
    * **`training.py`**: Used for practice or familiarization, may include live feedback.
    * **`assessment.py`**: Used for formal assessment of motor imagery performance, with a fixed protocol, embodiment exercise, and detailed data logging. No live feedback is provided to participants.
    * Both leverage `pygame_display.py` for visual stimuli and `serial_communication.py` for precise trigger synchronization with EEG recording systems.
    * Trial sequences are managed by `trial_generator.py` to ensure randomized yet constrained stimulus presentation.

* **EEG Visualization (`EEGVisualizer.py`):**
    * A dedicated application to visualize live ERD data streamed from `collect_data.py` via TCP.

* **Utility & Core Modules:**
    * `pygame_display.py`: Manages all visual aspects of the experiment (screen setup, text, images, stimuli).
    * `serial_communication.py`: Handles communication with external hardware via serial port for sending triggers.
    * `trial_generator.py`: Creates and randomizes trial lists, adhering to experiment design constraints.
    * `emulator.py`: Provides simulated EEG data for development and testing.
    * `livestream_receiver.py`: Connects to an actual EEG data stream (e.g., LSL) for live acquisition.
    * `mock_eeg_server.py`: A simple server to provide mock EEG data, potentially used for testing `livestream_receiver.py`.
    * `logger.py`: A utility for standardized logging.
    * `client.py`, `tcp_client.py`: Generic TCP client implementations, potentially for testing or simple consumption of broadcasted data.
    * `read_npy.py`: A utility to quickly read saved NumPy (`.npy`) EEG data files.

---

## 📝 About `assessment.py`

**`assessment.py`** is designed for the *formal assessment* of motor imagery performance, typically following a fixed protocol. It is similar in structure to `training.py` but is intended for use in the main experimental session, where data is collected for analysis and performance metrics.

**Key features and flow:**
- **Formal Protocol:** Implements a stricter, assessment-oriented protocol, often with more trials per block and a fixed number of blocks, suitable for data collection and analysis.
- **Embodiment Exercise:** Includes a pre-experiment embodiment exercise to help participants establish a mental representation of the sixth finger.
- **No Live ERD Feedback:** Unlike `training.py`, which may provide live ERD feedback to participants, `assessment.py` typically does not display real-time feedback, focusing instead on unbiased data collection.
- **Data Logging:** Saves detailed trial-by-trial data (including block, trial number, condition, and timestamp) to the `experiment_logs/` directory for later analysis.
- **Motor Execution and Imagery:** Each session includes both motor execution (actual movement) and motor imagery (imagination only) phases, with randomized and balanced trial sequences.
- **Configuration:** All experiment parameters (timings, trial counts, triggers, etc.) are centralized in the `ExperimentConfig` class for easy modification.

Use `assessment.py` for the main experimental session where you want to formally assess and record participants' motor imagery performance, following a standardized protocol.

---

## 📝 Code Structure & Documentation

All major scripts and modules in this project are **thoroughly commented and documented**. Each class, method, and major code block includes docstrings and comments explaining its purpose, logic, and usage. This makes it easy for new users and collaborators to:

- Understand the experiment flow and data processing pipeline.
- Modify experiment parameters, trial logic, or data handling.
- Extend the codebase for new experimental protocols or hardware.

**Where to look for explanations:**
- **`collect_data.py`**: Contains detailed comments on EEG data acquisition, real-time processing, ERD calculation, and broadcasting.
- **`training.py`**: Explains the experiment structure, block/trial logic, hardware communication, and feedback mechanisms.
- **`assessment.py`**: Documents the formal assessment protocol, including the embodiment exercise, block/trial structure, and data logging for analysis.
- **Utility modules** (in `utils/`): Each has docstrings and inline comments describing their role (e.g., stimulus display, serial communication, trial generation).

If you are new to the codebase, start by reading the docstrings at the top of each main class and method in `collect_data.py`, `training.py`, and `assessment.py`.

---

## 🛠️ Getting Started

### Prerequisites

* Python 3.x
* A serial port connection (if using hardware triggers).
* Your EEG data acquisition system providing a stream (e.g., LSL) or a compatible mock server.
* An `images/` folder in the root directory containing your visual stimulus images.

### Installation

1.  **Clone the repository** (if applicable) or ensure all project files are in your working directory.
2.  **Install Python dependencies:**
    The `requirements.txt` file lists all necessary Python packages.
    ```bash
    pip install -r requirements.txt
    ```
3.  **Prepare the `images` folder:**
    Create a directory named `images` in the root of your project. Place all necessary stimulus image files (e.g., `Hand_SixthFinger_Highlighted.png`, `Hand_Thumb_Highlighted.png`, `Circle.png`, etc.) inside this folder as referenced by the `pygame_display.py` and `ExperimentConfig` within `training.py`/`assessment.py`.

---

## ⚙️ Configuration

Key parameters for the experiment are distributed across the main application files. You'll need to modify these directly to suit your experimental setup:

* **`collect_data.py`**:
    * `EEG_SERVER_IP`, `EEG_SERVER_PORT`: Address of your EEG data stream.
    * `COLLECT_FROM_EMULATOR`: Set to `True` to use `emulator.py` instead of a live stream.
    * `FOCUS_CHANNELS`, `FOCUS_MARKERS`: Define which EEG channels and markers are relevant for ERD calculation.
    * `LOW_CUT`, `HIGH_CUT`, `FILTER_ORDER`: Band-pass filter settings for ERD.
    * `SECONDS_BEFORE_MARKER`, `SECONDS_AFTER_MARKER`: The time window around markers for epoch extraction.
    * `ENABLE_BROADCASTING`, `BROADCAST_IP`, `BROADCAST_PORT`: Settings for the live ERD data broadcast.

* **`training.py` / `assessment.py`**:
    * Contain their own experiment-specific configurations, including screen dimensions, trial timings, trial counts per block, and stimulus categories.
    * `SERIAL_PORT`, `BAUD_RATE`: Configure the serial port for trigger output.
    * `TRIGGER_EXPERIMENT_START`, `TRIGGER_BLOCK_START`, etc.: Define trigger codes for synchronization with your EEG recording system.

---

## 🏃 Running the Experiment

To run a full experiment session (EEG acquisition, experiment presentation, and visualization), you typically start the components in separate terminal windows:

1.  **Start the EEG Data Collector & Broadcaster:**
    Open a terminal and run:
    ```bash
    python collect_data.py
    ```
    This script will initialize the EEG connection (or emulator) and start listening for client connections for broadcasting. It will prompt you to press Enter to begin data collection.

2.  **Start the Experiment Session (e.g., Training or Assessment):**
    Open a **second terminal** and run either the training or assessment script:
    ```bash
    python training.py
    # OR
    python assessment.py
    ```
    This will launch the Pygame window and begin the visual experiment. Ensure your serial cable is connected and configured if you're sending triggers.

3.  **Start the EEG Visualizer (Optional):**
    Open a **third terminal** to visualize the live ERD data:
    ```bash
    python EEGVisualizer.py
    ```
    This will connect to the broadcast server run by `collect_data.py` and display the real-time ERD values.

---

## 📊 Data Output

All collected data is saved into the `data/` directory (created automatically if it doesn't exist).

* **Raw EEG Data (`.npy`)**: The full EEG data stream collected during the session.
* **Markers (`.csv`)**: A list of all received markers with their descriptions, positions, and associated channels.
* **Trial Event Data (`.csv`)**: (Generated by `training.py` and `assessment.py`) Contains details for each trial, such as `participant_id`, `block`, `trial_in_block`, `global_trial_num`, `condition`, `category`, and `timestamp`.

---

## 📡 Live ERD Broadcasting Details

The `collect_data.py` script acts as a TCP server, broadcasting real-time ERD results.

* **Default Address:** `127.0.0.1` (localhost)
* **Default Port:** `50000` (configurable in `collect_data.py`)
* **Data Format:** Each broadcast is a JSON object, terminated by a newline character (`\n`), making it easy for clients to parse.
* **Content:**
    * `timestamp`: The time of ERD calculation.
    * `marker_description`: The marker that triggered the ERD calculation.
    * `marker_stream_pos`: The sample index of the marker in the overall stream.
    * `erd_percent`: A list of ERD percentages for the configured focus channels.
    * `channel_names`: The names of the channels corresponding to the `erd_percent` values.

**Important Note on Live Broadcasting:**
The system broadcasts ERD results as they are computed from **live** EEG data. It does not store or re-send historical ERD data to new clients. If a client connects mid-experiment, they will start receiving ERD updates from that moment onwards.

---

## ⚠️ Troubleshooting

* **"Connection refused" or no EEG data**:
    * Ensure your EEG acquisition software is actively streaming on the configured IP and port in `collect_data.py`.
    * Double-check `EEG_SERVER_IP` and `EEG_SERVER_PORT`.
    * Confirm no firewall is blocking the connection.
    * Try setting `COLLECT_FROM_EMULATOR = True` in `collect_data.py` to test if the issue is with the external EEG source or the setup itself.
* **No ERD data received by `EEGVisualizer.py`**:
    * Verify `ENABLE_BROADCASTING` is `True` in `collect_data.py`.
    * Ensure `collect_data.py` is running and has accepted a client connection (check its console output).
    * Confirm `EEGVisualizer.py` and `collect_data.py` are using the same `BROADCAST_IP` and `BROADCAST_PORT`.
* **Serial port errors in `training.py` / `assessment.py`**:
    * Check that the `SERIAL_PORT` in the respective script's configuration matches your hardware.
    * Ensure the serial port isn't already in use by another program.
    * Verify your serial cable is correctly connected.
* **Pygame display issues**:
    * Check for missing `images/` folder or incorrectly named image files.
    * Ensure `pygame` is correctly installed.

---