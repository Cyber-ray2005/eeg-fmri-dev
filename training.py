import pygame
import random
import time
import sys
import os
import csv
import serial
import socket # --- NEW: Import socket for TCP communication ---
import threading # --- NEW: Import threading for background data reception ---
import queue # --- NEW: Import queue for thread-safe data passing ---
import json

# --- Experiment Parameters ---
# Screen dimensions (adjust as needed)
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FULLSCREEN_MODE = False # Set to True for actual experiment

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)
RED = (255, 0, 0) # For fixation cross
CIRCLE_COLOR = (200, 200, 200) # Color for the control circle

# Durations (in milliseconds)
INTRO_WAIT_KEY_PRESS = True
INTRO_DURATION_MS = 5000 # Used if INTRO_WAIT_KEY_PRESS is False
INITIAL_CALIBRATION_DURATION_MS = 3000
FIXATION_IN_TRIAL_DURATION_MS = 3000
IMAGE_DISPLAY_DURATION_MS = 3000
SHORT_BREAK_DURATION_MS = 1500

# Trial structure
NUM_SIXTH_FINGER_TRIALS_PER_BLOCK = 15
NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK = 15
NUM_BLANK_TRIALS_PER_BLOCK = 15
NUM_NORMAL_FINGERS = 5
NUM_EACH_NORMAL_FINGER_PER_BLOCK = NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK // NUM_NORMAL_FINGERS
TRIALS_PER_BLOCK = NUM_SIXTH_FINGER_TRIALS_PER_BLOCK + NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK + NUM_BLANK_TRIALS_PER_BLOCK
NUM_BLOCKS = 3

# Streak control parameters
MAX_CONSECUTIVE_CATEGORY_STREAK = 1


# --- Stimulus Paths and Names ---
IMAGE_FOLDER = "images"
SIXTH_FINGER_IMAGE_NAME = "Hand_SixthFinger_Highlighted.png"
NORMAL_FINGER_IMAGE_MAP = {
    "thumb": "Hand_Thumb_Highlighted.png",
    "index": "Hand_Index_Highlighted.png",
    "middle": "Hand_Middle_Highlighted.png",
    "ring": "Hand_Ring_Highlighted.png",
    "pinky": "Hand_Pinky_Highlighted.png"
}
NORMAL_FINGER_TYPES = list(NORMAL_FINGER_IMAGE_MAP.keys())
BLANK_CONDITION_NAME = "blank"

# Condition categories for streak checking
CATEGORY_SIXTH = "sixth_finger_cat"
CATEGORY_NORMAL = "normal_finger_cat"
CATEGORY_BLANK = "blank_cat"

# --- SERIAL PORT CONFIGURATION AND TRIGGERS ---
SERIAL_PORT = 'COM15'
BAUD_RATE = 9600
ser = None

# Define trigger values (bytes). Use unique integers (0-255).
TRIGGER_EXPERIMENT_START = 100
TRIGGER_EXPERIMENT_END = 101
TRIGGER_BLOCK_START = 11
TRIGGER_BLOCK_END = 12
TRIGGER_FIXATION_ONSET = 10
TRIGGER_SIXTH_FINGER_ONSET = 6
TRIGGER_THUMB_ONSET = 1
TRIGGER_INDEX_ONSET = 2
TRIGGER_MIDDLE_ONSET = 3
TRIGGER_RING_ONSET = 4
TRIGGER_PINKY_ONSET = 5
TRIGGER_CONTROL_STIMULUS_ONSET = 7 # For the blank/control (circle) condition
TRIGGER_SHORT_BREAK_ONSET = 20    # Onset of the blank screen after a stimulus

# Mapping from trial condition names (used in your logic) to stimulus trigger codes
STIMULUS_TRIGGER_MAP = {
    "sixth": TRIGGER_SIXTH_FINGER_ONSET,
    "thumb": TRIGGER_THUMB_ONSET,
    "index": TRIGGER_INDEX_ONSET,
    "middle": TRIGGER_MIDDLE_ONSET,
    "ring": TRIGGER_RING_ONSET,
    "pinky": TRIGGER_PINKY_ONSET,
    BLANK_CONDITION_NAME: TRIGGER_CONTROL_STIMULUS_ONSET
}

erd_history = []


# --- NEW: TCP Server Configuration ---
TCP_HOST = '127.0.0.1'  # The server's hostname or IP address (localhost)
TCP_PORT = 50000        # The port used by the server
tcp_socket = None       # Global socket object
received_data_queue = queue.Queue() # Queue to pass data from thread to main loop
stop_listener_event = threading.Event() # Event to signal the listener thread to stop

# --- Pygame Setup ---
pygame.init()
pygame.font.init()

if FULLSCREEN_MODE:
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    SCREEN_WIDTH, SCREEN_HEIGHT = screen.get_size()
else:
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Motor Imagery Experiment")

try:
    FONT_LARGE = pygame.font.Font(None, 74)
    FONT_MEDIUM = pygame.font.Font(None, 50)
    FONT_SMALL = pygame.font.Font(None, 36)
except Exception as e:
    print(f"Error loading default font: {e}. Using basic font.")
    FONT_LARGE = pygame.font.SysFont("arial", 60)
    FONT_MEDIUM = pygame.font.SysFont("arial", 40)
    FONT_SMALL = pygame.font.SysFont("arial", 30)


# --- SERIAL PORT HELPER FUNCTIONS ---
def initialize_serial(port=SERIAL_PORT, baudrate=BAUD_RATE):
    """Initializes the serial port."""
    global ser
    try:
        ser = serial.Serial(port, baudrate, timeout=0.01) # Small timeout for non-blocking
        print(f"Serial port {port} opened successfully at {baudrate} baud.")
        time.sleep(0.1) # Give the port a moment to initialize
    except serial.SerialException as e:
        print(f"Error: Could not open serial port {port}. {e}")
        print("Proceeding without serial triggers.")
        ser = None
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred during serial port initialization: {e}")
        ser = None

def send_trigger(trigger_value):
    """Sends a single byte trigger to the serial port."""
    global ser
    if ser and ser.is_open:
        try:
            ser.write(bytes([trigger_value]))
            print(f"Sent trigger: {trigger_value} (0x{trigger_value:02X})") # Optional: for debugging
            time.sleep(0.001) # Tiny delay to help ensure signal stability/reception
        except serial.SerialTimeoutException:
            print(f"Serial port timeout when sending trigger {trigger_value}.")
        except Exception as e:
            print(f"Error sending trigger {trigger_value}: {e}")

def close_serial():
    """Closes the serial port if it's open."""
    global ser
    if ser and ser.is_open:
        try:
            ser.close()
            print("Serial port closed.")
        except Exception as e:
            print(f"Error closing serial port: {e}")
    ser = None

# --- NEW: TCP Communication Helper Functions ---
def connect_to_tcp_server(host, port):
    """Attempts to connect to the TCP server."""
    global tcp_socket
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect((host, port))
        tcp_socket.settimeout(0.1) # Set a small timeout for non-blocking receive
        print(f"Successfully connected to TCP server at {host}:{port}")
        return True
    except ConnectionRefusedError:
        print(f"Connection refused. Ensure the TCP server is running at {host}:{port}.")
    except socket.timeout:
        print(f"Connection timed out when trying to connect to {host}:{port}.")
    except Exception as e:
        print(f"An error occurred while connecting to TCP server: {e}")
    tcp_socket = None
    return False

def tcp_listener_thread():
    """
    Function to be run in a separate thread to listen for incoming TCP data.
    Puts received data into a thread-safe queue.
    """
    global tcp_socket
    while not stop_listener_event.is_set():
        if tcp_socket:
            try:
                # Adjust buffer size (e.g., 4096 bytes) as needed for your data
                data = tcp_socket.recv(1024)
                if data:
                    decoded_data = data.decode('utf-8').strip() # Decode bytes to string
                    print(f"Received from TCP server: {decoded_data}")
                    received_data_queue.put(decoded_data) # Put data into the queue
                elif not data: # Server closed connection
                    print("TCP server closed the connection.")
                    break
            except socket.timeout:
                # No data for the timeout period, just continue looping
                pass
            except socket.error as e:
                print(f"Socket error in listener thread: {e}")
                break # Exit thread on socket error
            except Exception as e:
                print(f"Error in TCP listener thread: {e}")
                break # Exit thread on other errors
        time.sleep(0.01) # Small delay to prevent busy-waiting
    print("TCP listener thread stopping.")
    if tcp_socket:
        tcp_socket.close() # Ensure socket is closed
        tcp_socket = None


def close_tcp_connection():
    """Signals the listener thread to stop and cleans up the TCP socket."""
    global tcp_socket
    if tcp_socket:
        stop_listener_event.set() # Signal the thread to stop
        # Give the thread a moment to clean up (optional, but good practice)
        # for t in threading.enumerate():
        #     if t.name == "TCPListener": # Assuming you name your thread
        #         t.join(timeout=1)
        print("TCP connection marked for closure.")
        # Actual socket closing happens in the thread or can be done here if no thread active
        if tcp_socket: # Check again in case thread closed it
            try:
                tcp_socket.shutdown(socket.SHUT_RDWR) # Shutdown both read and write
                tcp_socket.close()
                print("TCP socket closed.")
            except OSError as e:
                print(f"Error shutting down/closing TCP socket: {e}")
            except Exception as e:
                print(f"Unexpected error closing TCP socket: {e}")
        tcp_socket = None
    stop_listener_event.clear() # Clear the event for potential re-runs


# --- Helper Functions (Remaining unchanged from original code, except for display_message_screen additions) ---

def load_and_scale_image(name, folder=IMAGE_FOLDER, target_screen_width=SCREEN_WIDTH, target_screen_height=SCREEN_HEIGHT):
    """Loads an image and scales it to fit the screen, preserving aspect ratio."""
    fullname = os.path.join(folder, name)
    try:
        original_image = pygame.image.load(fullname)
    except pygame.error as message:
        print(f"Cannot load image: {name} from {folder}")
        raise SystemExit(message)

    img_width, img_height = original_image.get_size()

    if img_width == 0 or img_height == 0: # Avoid division by zero for empty images
        print(f"Warning: Image {name} has zero dimension.")
        return original_image

    scale_w = target_screen_width / img_width
    scale_h = target_screen_height / img_height
    scale_factor = min(scale_w, scale_h)

    new_width = int(img_width * scale_factor)
    new_height = int(img_height * scale_factor)

    try:
        scaled_image = pygame.transform.smoothscale(original_image, (new_width, new_height))
    except ValueError:
        print(f"Warning: Could not scale image {name} to zero dimensions. Using original.")
        return original_image
    return scaled_image


def draw_text(surface, text, font, color, center_x, center_y, line_spacing_factor=1.2):
    """Draws multi-line text on the surface, centered."""
    lines = text.split('\n')
    rendered_lines_with_rects = []
    total_height = 0
    line_height = font.get_linesize() * line_spacing_factor

    # Calculate total height first
    for i, line_text in enumerate(lines):
        rendered_line = font.render(line_text, True, color)
        rect = rendered_line.get_rect()
        if i == 0:
            total_height += rect.height
        else:
            total_height += line_height

    if not lines: total_height = 0
    elif len(lines) == 1:
        # If only one line, use its actual height
        if lines[0].strip(): # check if the line is not just whitespace
            single_line_render = font.render(lines[0], True, color)
            total_height = single_line_render.get_height()
        else: # if it's an empty string or only whitespace
            total_height = 0


    current_y = center_y - total_height / 2

    for i, line_text in enumerate(lines):
        rendered_line = font.render(line_text, True, color)
        rect = rendered_line.get_rect(centerx=center_x)
        if i == 0:
            rect.top = current_y
        else:
            # For subsequent lines, position based on the accumulated line_height
            rect.top = current_y + (font.render(lines[0], True, color).get_height() if len(lines)>1 else 0) + (i-1)*line_height


        surface.blit(rendered_line, rect)
        if i == 0 and len(lines) > 1: # after drawing the first line, update current_y for the next spacing
            current_y += rect.height # move current_y to the bottom of the first line
        elif i > 0 : # for lines after the first, use fixed line_height
            current_y += line_height


def display_message_screen(message, duration_ms=0, wait_for_key=False, font=FONT_MEDIUM, bg_color=GRAY, text_color=BLACK, server_response=""):
    """
    Draws multi-line text on the surface, centered.
    Includes an optional server_response display area at the bottom.
    """
    screen.fill(bg_color)
    draw_text(screen, message, font, text_color, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    # --- NEW: Display server response at the bottom ---
    if server_response:
        response_text = FONT_SMALL.render(f"Server Says: {server_response}", True, BLACK)
        response_rect = response_text.get_rect(centerx=SCREEN_WIDTH // 2, bottom=SCREEN_HEIGHT - 20)
        screen.blit(response_text, response_rect)

    pygame.display.flip()

    start_time = pygame.time.get_ticks()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
                if wait_for_key: running = False
        if not wait_for_key and (pygame.time.get_ticks() - start_time >= duration_ms):
            running = False
        pygame.time.wait(10)

def display_fixation_cross(duration_ms, trigger_code=None):
    screen.fill(BLACK)
    cross_size = 90
    center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    pygame.draw.line(screen, WHITE, (center_x - cross_size // 2, center_y), (center_x + cross_size // 2, center_y), 10)
    pygame.draw.line(screen, WHITE, (center_x, center_y - cross_size // 2), (center_x, center_y + cross_size // 2), 10)

    # if trigger_code is not None:
    #     send_trigger(trigger_code)
    pygame.display.flip()

    start_time = pygame.time.get_ticks()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
        if pygame.time.get_ticks() - start_time >= duration_ms: running = False
        pygame.time.wait(10)

def display_image_stimulus(image_surface, duration_ms, crop_rect=None, trigger_code=None):
    screen.fill(BLACK)

    if crop_rect is not None:
        try:
            cropped_surface = pygame.Surface((crop_rect[2], crop_rect[3]))
            cropped_surface.blit(image_surface, (0, 0), crop_rect)
            image_to_display = cropped_surface
        except Exception as e:
            print(f"Error cropping image: {e}. Displaying original.")
            image_to_display = image_surface
    else:
        image_to_display = image_surface

    image_rect = image_to_display.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    screen.blit(image_to_display, image_rect)

    if trigger_code is not None:
        send_trigger(trigger_code)
    pygame.display.flip()

    start_time = pygame.time.get_ticks()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
        if pygame.time.get_ticks() - start_time >= duration_ms: running = False
        pygame.time.wait(10)

def display_control_stimulus(duration_ms, trigger_code=None):
    screen.fill(BLACK)
    circle_radius = 50
    center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    pygame.draw.circle(screen, CIRCLE_COLOR, (center_x, center_y), circle_radius)

    if trigger_code is not None:
        send_trigger(trigger_code)
    pygame.display.flip()

    start_time = pygame.time.get_ticks()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
        if pygame.time.get_ticks() - start_time >= duration_ms: running = False
        pygame.time.wait(10)

def display_blank_screen(duration_ms, color=BLACK, trigger_code=None):
    screen.fill(color)
    # if trigger_code is not None:
    #     send_trigger(trigger_code)
    pygame.display.flip()

    start_time = pygame.time.get_ticks()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
        if pygame.time.get_ticks() - start_time >= duration_ms: running = False
        pygame.time.wait(10)


def get_condition_category(condition_name):
    if condition_name == "sixth": return CATEGORY_SIXTH
    elif condition_name == BLANK_CONDITION_NAME: return CATEGORY_BLANK
    elif condition_name in NORMAL_FINGER_TYPES: return CATEGORY_NORMAL
    return "unknown_category"

def check_streak_violations(trial_list, max_allowed_streak):
    if not trial_list: return False
    current_streak_count = 0
    last_category = None
    for condition_name in trial_list:
        current_category = get_condition_category(condition_name)
        if current_category == "unknown_category": continue
        if (current_category == CATEGORY_SIXTH or current_category == CATEGORY_BLANK) and current_category == last_category:
            current_streak_count += 1
        else:
            last_category = current_category
            current_streak_count = 1
        if current_streak_count > max_allowed_streak: return True
    return False

def display_loading_screen(message="Loading...", font=FONT_MEDIUM, bg_color=BLACK, text_color=WHITE):
    """
    Displays a persistent loading screen. Call this function and then perform
    your long-running task. The screen will remain until another display function is called.
    """
    screen.fill(bg_color)
    draw_text(screen, message, font, text_color, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    pygame.display.flip()

def display_erd_feedback_bar(erd_value, duration_ms=1500):
    screen.fill(BLACK)

    bar_width = int(SCREEN_WIDTH * 0.6)
    bar_height = 40
    bar_x = (SCREEN_WIDTH - bar_width) // 2
    bar_y = SCREEN_HEIGHT // 2

    # Clamp ERD value
    erd_value = max(min(erd_value, 100), 0)
    target_fill = int((erd_value / 100.0) * (bar_width))

    start_time = pygame.time.get_ticks()
    current_fill = 0

    while pygame.time.get_ticks() - start_time < duration_ms:
        screen.fill(BLACK)

        # Draw background: left and right halves separately
        # pygame.draw.rect(screen, GRAY, (bar_x, bar_y, bar_width // 2, bar_height))  # Left half (negative)
        # pygame.draw.rect(screen, GRAY, (bar_x + bar_width // 2, bar_y, bar_width // 2, bar_height))  # Right half (positive)
        pygame.draw.rect(screen, GRAY, (bar_x, bar_y, bar_width, bar_height))
        # Animate toward target
        if current_fill < target_fill:
            current_fill += min(5, target_fill - current_fill)
        elif current_fill > target_fill:
            current_fill -= min(5, current_fill - target_fill)

        # Draw fill
        # if current_fill > 0:
        #     pygame.draw.rect(screen, (0, 200, 0), (bar_x + bar_width // 2, bar_y, current_fill, bar_height))
        # elif current_fill < 0:
        #     pygame.draw.rect(screen, (200, 0, 0), (bar_x + bar_width // 2 + current_fill, bar_y, -current_fill, bar_height))
        pygame.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, current_fill, bar_height)) # Starts at bar_x, fills right
        # Label
        percent_text = FONT_MEDIUM.render(f"ERD: {erd_value:.1f}%", True, WHITE)
        text_rect = percent_text.get_rect(center=(SCREEN_WIDTH // 2, bar_y - 60))
        screen.blit(percent_text, text_rect)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()

        pygame.time.wait(10)  # Smooth animation

def generate_trial_list_for_block():
    base_trial_conditions = []
    base_trial_conditions.extend(["sixth"] * NUM_SIXTH_FINGER_TRIALS_PER_BLOCK)
    for finger_type in NORMAL_FINGER_TYPES:
        base_trial_conditions.extend([finger_type] * NUM_EACH_NORMAL_FINGER_PER_BLOCK)
    base_trial_conditions.extend([BLANK_CONDITION_NAME] * NUM_BLANK_TRIALS_PER_BLOCK)
    shuffled_list = list(base_trial_conditions)

    while True:
        random.shuffle(shuffled_list)
        if not check_streak_violations(shuffled_list, MAX_CONSECUTIVE_CATEGORY_STREAK):
            return shuffled_list


# --- Load and Scale Images ---
scaled_images = {}
try:
    scaled_images["sixth"] = load_and_scale_image(SIXTH_FINGER_IMAGE_NAME)
    for finger_type, img_name in NORMAL_FINGER_IMAGE_MAP.items():
        scaled_images[finger_type] = load_and_scale_image(img_name)
except SystemExit:
    print("CRITICAL: Error loading or scaling images. Ensure 'images' folder and all .png files exist and are valid.")
    pygame.quit()
    close_serial()
    close_tcp_connection() # --- NEW: Close TCP connection on exit ---
    sys.exit()
except Exception as e:
    print(f"CRITICAL: An unexpected error occurred during image loading/scaling: {e}")
    pygame.quit()
    close_serial()
    close_tcp_connection() # --- NEW: Close TCP connection on exit ---
    sys.exit()


def run_trial(trial_number_global, trial_condition):
    print(f"Global Trial: {trial_number_global}, Condition: {trial_condition} "
          f"(Category: {get_condition_category(trial_condition)})")

    # Display fixation cross with its trigger
    display_fixation_cross(FIXATION_IN_TRIAL_DURATION_MS, trigger_code=None)

    stimulus_trigger_code = STIMULUS_TRIGGER_MAP.get(trial_condition)

    if trial_condition == BLANK_CONDITION_NAME:
        display_control_stimulus(IMAGE_DISPLAY_DURATION_MS, trigger_code=stimulus_trigger_code)
    elif trial_condition in scaled_images:
        if stimulus_trigger_code is not None:
            current_image_surface = scaled_images[trial_condition]
            display_image_stimulus(current_image_surface, IMAGE_DISPLAY_DURATION_MS, (0 , 0, 500, 600), trigger_code=stimulus_trigger_code)
        else:
            print(f"Warning: No trigger defined for image condition '{trial_condition}'. Stimulus shown without trigger.")
            current_image_surface = scaled_images[trial_condition]
            display_image_stimulus(current_image_surface, IMAGE_DISPLAY_DURATION_MS, (0 , 0, 500, 600)) # Show without trigger
    else:
        print(f"Error: Unknown trial condition or image key '{trial_condition}'.")
        display_message_screen(f"Error: Missing stimulus for {trial_condition}", 2000, font=FONT_SMALL, bg_color=RED)

    # Display short break (blank screen) with its trigger
    return trial_condition


# --- Main Experiment Loop ---
def run_experiment():
    all_trial_data = []
    participant_id = "P" + str(random.randint(100,999))

    initialize_serial()

    # --- NEW: Connect to TCP server and start listener thread ---
    if connect_to_tcp_server(TCP_HOST, TCP_PORT):
        listener_thread = threading.Thread(target=tcp_listener_thread, name="TCPListener")
        listener_thread.daemon = True # Allow the main program to exit even if thread is running
        listener_thread.start()
    else:
        print("Could not connect to TCP server. Proceeding without real-time data reception.")


    intro_text = "Welcome to the Motor Imagery Experiment!\n\nPlease focus on the stimulus presented.\n\n"
    if INTRO_WAIT_KEY_PRESS:
        intro_text += "Press any key to begin."
        display_message_screen(intro_text, wait_for_key=True, font=FONT_MEDIUM)
    else:
        intro_text += f"The experiment will begin in {INTRO_DURATION_MS/1000:.0f} seconds."
        display_message_screen(intro_text, duration_ms=INTRO_DURATION_MS, font=FONT_MEDIUM)

    for block_num in range(1, NUM_BLOCKS + 1):
        # send_trigger(TRIGGER_BLOCK_START)

        # --- NEW: Check for and display any pending server messages before block starts ---
        latest_server_response = ""
        while not received_data_queue.empty():
            latest_server_response = received_data_queue.get_nowait()
            if latest_server_response:
                print(f"Displaying pending message: {latest_server_response}")
                # We can choose to show all or just the latest message
                # For this intro, we'll only show the *latest* if any are pending
                break

        display_loading_screen("Generating trials for Block...", font=FONT_MEDIUM, bg_color=BLACK, text_color=WHITE)        
        current_block_trial_conditions = generate_trial_list_for_block()
        if len(current_block_trial_conditions) != TRIALS_PER_BLOCK:
            print(f"CRITICAL Error: Trial list length mismatch.")
            display_message_screen("CRITICAL Error: Trial configuration issue.", 5000, bg_color=RED)
            pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()

        for trial_num_in_block, condition in enumerate(current_block_trial_conditions, 1):
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.quit(); close_serial(); close_tcp_connection(); sys.exit()

            trial_global_num = (block_num - 1) * TRIALS_PER_BLOCK + trial_num_in_block
            presented_condition = run_trial(trial_global_num, condition)

            # --- NEW: Check for and display received data after each trial ---
            server_response_for_trial = ""
            server_feedback_dict = {}
            try:
                # Use get_nowait() to check if data is available without blocking
                server_response_for_trial = received_data_queue.get_nowait()
                if server_response_for_trial:
                    server_feedback_dict = json.loads(server_response_for_trial)
            except queue.Empty:
                server_response_for_trial = "No new data from server." # Or leave empty if you prefer

            trial_data = {
                "participant_id": participant_id,
                "block": block_num,
                "trial_in_block": trial_num_in_block,
                "global_trial_num": trial_global_num,
                "condition": presented_condition,
                "category": get_condition_category(presented_condition),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "server_feedback": server_response_for_trial # Store feedback
            }
            all_trial_data.append(trial_data)
            try:
                erd_value = float(server_feedback_dict.get("erd_percent", 0))
                erd_history.append(erd_value)
                display_erd_feedback_bar(erd_value, duration_ms=SHORT_BREAK_DURATION_MS)
            except ValueError:
                display_message_screen("Neurofeedback\n(No ERD data)", duration_ms=SHORT_BREAK_DURATION_MS, font=FONT_SMALL)

            display_blank_screen(SHORT_BREAK_DURATION_MS)
            

            #
        # send_trigger(TRIGGER_BLOCK_END)

        # --- NEW: Check for and display any pending server messages after block ends ---
        block_end_server_response = ""
        while not received_data_queue.empty():
            block_end_server_response = received_data_queue.get_nowait()
            if block_end_server_response:
                print(f"Displaying pending block end message: {block_end_server_response}")
                break

        if block_num < NUM_BLOCKS:
            long_break_message = f"End of Block {block_num}.\n\nTake a break.\n\nPress any key to continue to the next block."
            display_message_screen(long_break_message, wait_for_key=True, font=FONT_MEDIUM, server_response=block_end_server_response)
        else:
            display_message_screen("All Blocks Completed!", duration_ms=3000, font=FONT_MEDIUM, server_response=block_end_server_response)

    display_message_screen("Experiment Finished!\n\nThank you for your participation.", duration_ms=5000, wait_for_key=True, font=FONT_LARGE)

    if all_trial_data:
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        data_folder = "data"
        if not os.path.exists(data_folder): os.makedirs(data_folder)
        filename = os.path.join(data_folder, f"{participant_id}_motor_imagery_data_{timestamp_str}.csv")
        try:
            with open(filename, 'w', newline='') as csvfile:
                # Add 'server_feedback' to fieldnames
                fieldnames = ["participant_id", "block", "trial_in_block", "global_trial_num", "condition", "category", "timestamp", "server_feedback"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_trial_data)
            print(f"Data saved to {filename}")
            display_message_screen(f"Data saved to:\n{filename}", duration_ms=4000, font=FONT_SMALL)
        except IOError as e:
            print(f"Error: Could not save data to {filename}. Error: {e}")
            display_message_screen(f"Error: Could not save data!", duration_ms=3000, font=FONT_SMALL, bg_color=RED)

    pygame.quit()
    close_serial()
    close_tcp_connection() # --- NEW: Ensure TCP connection is closed on exit ---
    sys.exit()

if __name__ == "__main__":
    expected_total_trials = NUM_SIXTH_FINGER_TRIALS_PER_BLOCK + \
                            (NUM_EACH_NORMAL_FINGER_PER_BLOCK * NUM_NORMAL_FINGERS) + \
                            NUM_BLANK_TRIALS_PER_BLOCK
    if expected_total_trials != TRIALS_PER_BLOCK:
        print(f"Error: Mismatch in total trial count. Expected: {expected_total_trials}, Got: {TRIALS_PER_BLOCK}")
        sys.exit()
    if NUM_TOTAL_NORMAL_FINGER_TRIALS_PER_BLOCK != NUM_EACH_NORMAL_FINGER_PER_BLOCK * NUM_NORMAL_FINGERS:
        print(f"Error: Mismatch in normal finger trial counts.")
        sys.exit()
    else:
        try:
            run_experiment()
        except SystemExit:
            print("Experiment exited.")
        except Exception as e:
            print(f"An unexpected error occurred during the experiment: {e}")
        finally:
            close_serial()
            close_tcp_connection() # --- NEW: Ensure TCP connection is closed in finally block too ---
