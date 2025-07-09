# Embodiment Exercise

This module provides a pre-experiment embodiment exercise for the Motor Imagery EEG Experiment Suite. The exercise is designed to help participants establish a mental and physical representation of a supernumerary (extra) robotic thumb by practicing writing characters with it.

## Purpose

The embodiment exercise is typically run before the main experiment (e.g., before motor imagery or assessment blocks). It familiarizes participants with the use of the supernumerary thumb and helps induce a sense of embodiment, which is important for subsequent experimental tasks.

## What It Does

- Presents a series of characters (e.g., words or letters) to the participant, one at a time.
- Instructs the participant to use the supernumerary robotic thumb to write each character on sand (or another medium).
- Waits for the participant to press a key before moving to the next character.
- Logs the sequence of displayed characters and exercise events to a timestamped log file in the `exercise_logs/` directory.
- Shows a thank-you message at the end of the exercise.

## Configuration

The exercise is controlled by the experiment's configuration object (`config`), which should define:
- `CHARACTERS_TO_WRITE`: A list of possible characters/words to present.
- `NUMBER_OF_CHARACTERS_TO_WRITE`: How many characters to present in each session.

## Dependencies

- `pygame` (for display and user input)
- `utils/pygame_display.py` (for screen management)
- `utils/logger.py` (for logging events)

## Usage Example

The embodiment exercise is typically invoked from the main experiment script:

```python
from embodiment.EmbodimentExcercise import EmbodimentExercise
# ...
exercise = EmbodimentExercise(config)
exercise.run()
```

This will display instructions, present a randomized sequence of characters, and log the session.

## Log Output

- Log files are saved in the `exercise_logs/` directory with timestamps.
- Each log records the start and end of the exercise, as well as each character shown.

## Customization

- To change the set of characters or the number of trials, edit the relevant fields in your experiment's configuration.
- You can modify the instruction or thank-you messages by editing the `EmbodimentExercise` class.

--- 