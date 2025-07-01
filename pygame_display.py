import pygame
import time
import sys
import os
import re

class PygameDisplay:
    def __init__(self, config):
        pygame.init()
        pygame.font.init()
        self.config = config
        self.screen = self._setup_screen()
        self.clock = pygame.time.Clock()
        self.FONT_LARGE = pygame.font.Font(None, 74)
        self.FONT_MEDIUM = pygame.font.Font(None, 50)
        self.FONT_SMALL = pygame.font.Font(None, 36)
        self.scaled_images = {}
        

    def _setup_screen(self):
        if self.config.FULLSCREEN_MODE:
            display_info = pygame.display.Info()
            screen_width = display_info.current_w
            screen_height = display_info.current_h
            screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
            self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT = screen_width, screen_height
        else:
            screen = pygame.display.set_mode((self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT))
        pygame.display.set_caption("Motor Imagery Experiment")
        return screen

    def _load_and_scale_image(self, name, folder, target_screen_width, target_screen_height):
        fullname = os.path.join(folder, name)
        try:
            original_image = pygame.image.load(fullname)
        except pygame.error as message:
            print(f"Cannot load image: {name} from {folder}")
            raise SystemExit(message)

        img_width, img_height = original_image.get_size()

        if img_width == 0 or img_height == 0:
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

    def load_stimulus_images(self):
        try:
            self.scaled_images["sixth"] = self._load_and_scale_image(
                self.config.SIXTH_FINGER_IMAGE_NAME, self.config.IMAGE_FOLDER,
                self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT
            )
            self.scaled_images["rest"] = self._load_and_scale_image(
                self.config.REST_FINGER_IMAGE_NAME, self.config.IMAGE_FOLDER,
                self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT
            )
            self.scaled_images["sixth_blue"] = self._load_and_scale_image(
                self.config.SIXTH_FINGER_IMAGE_NAME_BLUE, self.config.IMAGE_FOLDER,
                self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT
            )
            for finger_type, img_name in self.config.NORMAL_FINGER_IMAGE_MAP.items():
                self.scaled_images[finger_type] = self._load_and_scale_image(
                    img_name, self.config.IMAGE_FOLDER,
                    self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT
                )
            print("INFO: All images loaded and scaled successfully.")
        except SystemExit:
            print("CRITICAL: Error loading or scaling images. Ensure 'images' folder and all .png files exist and are valid.")
            pygame.quit()
            sys.exit()
        except Exception as e:
            print(f"CRITICAL: An unexpected error occurred during image loading/scaling: {e}")
            pygame.quit()
            sys.exit()

    def _draw_text(self, surface, text, font, color, center_x, center_y, line_spacing_factor=1.2):
        lines = text.split('\n')
        total_height = 0
        line_height = font.get_linesize() * line_spacing_factor

        for i, line_text in enumerate(lines):
            rendered_line = font.render(line_text, True, color)
            rect = rendered_line.get_rect()
            if i == 0:
                total_height += rect.height
            else:
                total_height += line_height

        if not lines: total_height = 0
        elif len(lines) == 1:
            if lines[0].strip():
                single_line_render = font.render(lines[0], True, color)
                total_height = single_line_render.get_height()
            else:
                total_height = 0

        current_y = center_y - total_height / 2

        for i, line_text in enumerate(lines):
            rendered_line = font.render(line_text, True, color)
            rect = rendered_line.get_rect(centerx=center_x)
            if i == 0:
                rect.top = current_y
            else:
                rect.top = current_y + (font.render(lines[0], True, color).get_height() if len(lines) > 1 else 0) + (i-1)*line_height

            surface.blit(rendered_line, rect)
            if i == 0 and len(lines) > 1:
                current_y += rect.height
            elif i > 0 :
                current_y += line_height

    def display_message_screen(self, message, duration_ms=0, wait_for_key=False, font=None, bg_color=None, text_color=None, server_response=""):
        font = font if font else self.FONT_LARGE
        bg_color = bg_color if bg_color else self.config.GRAY
        text_color = text_color if text_color else self.config.BLACK

        self.screen.fill(bg_color)
        
        # --- Start of Multi-Line and Color Processing ---

        lines = message.splitlines() # Split the message by '\n'
        
        # Pre-process all lines to find segments and calculate dimensions
        processed_lines = []
        max_line_width = 0
        pattern = r'#([A-Za-z0-9_]+):([^#]+)#'

        for line in lines:
            processed_segments = []
            last_end = 0
            
            # Use regex to find all color-tagged sections
            for match in re.finditer(pattern, line):
                # Add text before the match with default color
                if match.start() > last_end:
                    processed_segments.append((line[last_end:match.start()], text_color))
                
                # Extract color name and text
                color_name, color_text = match.groups()
                
                # Get color from config or default
                color = getattr(self.config, color_name.upper(), text_color)
                if color == text_color and not hasattr(self.config, color_name.upper()):
                    print(f"Warning: Color '{color_name}' not found. Using default.")

                processed_segments.append((color_text, color))
                last_end = match.end()
            
            # Add any remaining text after the last match
            if last_end < len(line):
                processed_segments.append((line[last_end:], text_color))

            # Calculate the total width of this line for centering
            line_width = sum(font.size(seg[0])[0] for seg in processed_segments)
            max_line_width = max(max_line_width, line_width) # Keep track for potential block centering

            processed_lines.append({'segments': processed_segments, 'width': line_width})

        # --- Drawing Logic ---
        
        # Calculate the starting Y position to center the entire text block vertically
        font_height = font.get_height()
        total_text_height = len(lines) * font_height
        current_y = (self.config.SCREEN_HEIGHT - total_text_height) // 2

        # Draw each line
        for line_data in processed_lines:
            # Calculate the starting X to center this specific line horizontally
            current_x = (self.config.SCREEN_WIDTH - line_data['width']) // 2
            
            # Draw each segment of the line
            for text_segment, color in line_data['segments']:
                if text_segment: # Avoid rendering empty strings
                    text_surface = font.render(text_segment, True, color)
                    self.screen.blit(text_surface, (current_x, current_y))
                    current_x += text_surface.get_width() # Move X for the next segment
            
            current_y += font_height # Move Y down for the next line

        # --- End of Drawing Logic ---

        if server_response:
            response_text = self.FONT_SMALL.render(f"Server Says: {server_response}", True, self.config.BLACK)
            response_rect = response_text.get_rect(centerx=self.config.SCREEN_WIDTH // 2, bottom=self.config.SCREEN_HEIGHT - 20)
            self.screen.blit(response_text, response_rect)

        pygame.display.flip()

        # --- Game Loop for Displaying the Message ---
        start_time = pygame.time.get_ticks()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.quit_pygame_and_exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE: self.quit_pygame_and_exit()
                    if wait_for_key: running = False
            if not wait_for_key and (pygame.time.get_ticks() - start_time >= duration_ms):
                running = False
            pygame.time.wait(10)

    def display_fixation_cross(self, duration_ms):
        self.screen.fill(self.config.BLACK)
        cross_size = 100
        line_thickness = 10 # Define line thickness
        center_x, center_y = self.config.SCREEN_WIDTH // 2, self.config.SCREEN_HEIGHT // 2

        # Horizontal line
        # Adjust coordinates to account for line thickness, ensuring perfect centering
        pygame.draw.line(self.screen, self.config.WHITE, 
                         (center_x - cross_size // 2, center_y), 
                         (center_x + cross_size // 2, center_y), 
                         line_thickness)
        
        # Vertical line
        # Adjust coordinates to account for line thickness, ensuring perfect centering
        pygame.draw.line(self.screen, self.config.WHITE, 
                         (center_x, center_y - cross_size // 2), 
                         (center_x, center_y + cross_size // 2), 
                         line_thickness)
        
        pygame.display.flip()

        start_time = pygame.time.get_ticks()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.quit_pygame_and_exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: self.quit_pygame_and_exit()
            if pygame.time.get_ticks() - start_time >= duration_ms: running = False
            pygame.time.wait(10)

    def display_image_stimulus(self, image_surface, duration_ms, crop_rect=None):
        self.screen.fill(self.config.BLACK)

        if crop_rect is not None:
            try:
                # The SRCALPHA flag is a good addition for transparency
                cropped_surface = pygame.Surface((crop_rect[2], crop_rect[3]), pygame.SRCALPHA)
                cropped_surface.blit(image_surface, (0,0))
                image_to_display = cropped_surface
            except Exception as e:
                print(f"Error cropping image: {e}. Displaying original.")
                image_to_display = image_surface
        else:
            image_to_display = image_surface


        screen_center = self.screen.get_rect().center
        image_rect = image_to_display.get_rect(center=screen_center)
        
        self.screen.blit(image_to_display, image_rect)

        pygame.display.flip()

        # The rest of your event loop is fine
        start_time = pygame.time.get_ticks()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.quit_pygame_and_exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: self.quit_pygame_and_exit()
            if pygame.time.get_ticks() - start_time >= duration_ms: running = False
            pygame.time.wait(10)

    def display_control_stimulus(self, duration_ms):
        self.screen.fill(self.config.BLACK)
        circle_radius = 50
        center_x, center_y = self.config.SCREEN_WIDTH // 2, self.config.SCREEN_HEIGHT // 2
        pygame.draw.circle(self.screen, self.config.CIRCLE_COLOR, (center_x, center_y), circle_radius)
        pygame.display.flip()

        start_time = pygame.time.get_ticks()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.quit_pygame_and_exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: self.quit_pygame_and_exit()
            if pygame.time.get_ticks() - start_time >= duration_ms: running = False
            pygame.time.wait(10)

    def display_blank_screen(self, duration_ms, color=None):
        color = color if color else self.config.BLACK
        self.screen.fill(color)
        pygame.display.flip()

        start_time = pygame.time.get_ticks()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: self.quit_pygame_and_exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: self.quit_pygame_and_exit()
            if pygame.time.get_ticks() - start_time >= duration_ms: running = False
            pygame.time.wait(10)

    def display_loading_screen(self, message="Loading...", font=None, bg_color=None, text_color=None):
        font = font if font else self.FONT_MEDIUM
        bg_color = bg_color if bg_color else self.config.BLACK
        text_color = text_color if text_color else self.config.WHITE
        self.screen.fill(bg_color)
        self._draw_text(self.screen, message, font, text_color, self.config.SCREEN_WIDTH // 2, self.config.SCREEN_HEIGHT // 2)
        pygame.display.flip()
    
    def display_erd_feedback_bar(self, erd_value, duration_ms=1500):
        self.screen.fill(self.config.BLACK)

        bar_width = int(self.config.SCREEN_WIDTH * 0.6)
        bar_height = 40
        bar_x = (self.config.SCREEN_WIDTH - bar_width) // 2
        bar_y = self.config.SCREEN_HEIGHT // 2

        # Clamp ERD value
        erd_value = max(min(erd_value, 100), 0)
        target_fill = int((erd_value / 100.0) * (bar_width))

        start_time = pygame.time.get_ticks()
        current_fill = 0

        while pygame.time.get_ticks() - start_time < duration_ms:
            self.screen.fill(self.config.BLACK)

            # Determine bar color based on ERD value
            bar_color = (0, 200, 0)  # Default Green
            if erd_value < 20:
                bar_color = (255, 0, 0)  # Red
            elif 20 <= erd_value <= 50:
                bar_color = (255, 165, 0) # Orange
            else: # erd_value > 50
                bar_color = (0, 200, 0) # Green

            # Draw background bar
            pygame.draw.rect(self.screen, self.config.GRAY, (bar_x, bar_y, bar_width, bar_height))
            
            # Animate toward target
            if current_fill < target_fill:
                current_fill += min(5, target_fill - current_fill)
            elif current_fill > target_fill:
                current_fill -= min(5, current_fill - target_fill)

            # Draw fill with dynamic color
            pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, current_fill, bar_height)) # Starts at bar_x, fills right
            
            # Label
            percent_text = self.FONT_MEDIUM.render(f"Quality of Imagery: {erd_value:.1f}%", True, self.config.WHITE)
            text_rect = percent_text.get_rect(center=(self.config.SCREEN_WIDTH // 2, bar_y - 60))
            self.screen.blit(percent_text, text_rect)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()

            pygame.time.wait(5)  # Smooth animation

    
    def ask_yes_no_question(self, question):
        """
        Displays a yes/no question with interactive buttons.

        Args:
            question (str): The question to display to the user.

        Returns:
            bool: True if 'Yes' is selected, False if 'No' is selected.
        """
        # Define colors for buttons
        BUTTON_NORMAL_COLOR = self.config.GRAY
        BUTTON_HIGHLIGHT_COLOR = (100, 100, 255) # A distinct blue for highlighting
        TEXT_COLOR = self.config.WHITE

        # Define button properties
        button_width = 200
        button_height = 80
        button_spacing = 50

        # Calculate positions
        center_x = self.config.SCREEN_WIDTH // 2
        center_y = self.config.SCREEN_HEIGHT // 2

        # Question text position
        question_surface = self.FONT_MEDIUM.render(question, True, TEXT_COLOR)
        question_rect = question_surface.get_rect(center=(center_x, center_y - button_height - 50))

        # Button positions
        yes_x = center_x - button_width - button_spacing // 2
        no_x = center_x + button_spacing // 2
        button_y = center_y + 50

        yes_rect = pygame.Rect(yes_x, button_y, button_width, button_height)
        no_rect = pygame.Rect(no_x, button_y, button_width, button_height)

        # Initial selection (Yes is default)
        selected_option = "yes" 

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_pygame_and_exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.quit_pygame_and_exit()
                    elif (event.key == pygame.K_y):
                        selected_option = "yes"
                        running = False
                    elif event.key == pygame.K_n:
                        selected_option = "no"
                        running = False
                    elif event.key == pygame.K_RETURN: # Enter key to confirm selection
                        running = False

            # Drawing
            self.screen.fill(self.config.BLACK)

            # Draw question
            self.screen.blit(question_surface, question_rect)

            # Draw Yes button
            yes_color = BUTTON_HIGHLIGHT_COLOR if selected_option == "yes" else BUTTON_NORMAL_COLOR
            pygame.draw.rect(self.screen, yes_color, yes_rect, border_radius=10)
            yes_text_surface = self.FONT_MEDIUM.render("Yes", True, TEXT_COLOR)
            yes_text_rect = yes_text_surface.get_rect(center=yes_rect.center)
            self.screen.blit(yes_text_surface, yes_text_rect)

            # Draw No button
            no_color = BUTTON_HIGHLIGHT_COLOR if selected_option == "no" else BUTTON_NORMAL_COLOR
            pygame.draw.rect(self.screen, no_color, no_rect, border_radius=10)
            no_text_surface = self.FONT_MEDIUM.render("No", True, TEXT_COLOR)
            no_text_rect = no_text_surface.get_rect(center=no_rect.center)
            self.screen.blit(no_text_surface, no_text_rect)

            pygame.display.flip()
            pygame.time.wait(10) # Small delay to reduce CPU usage

        return selected_option == "yes"

    def display_timer_with_message(self, message, duration_ms, font=None, bg_color=None, text_color=None):
        """
        Displays a countdown timer with a message.
        
        Args:
            message (str): The message to display above the timer
            duration_ms (int): Total duration in ms
            font (pygame.font.Font): Font to use (defaults to FONT_MEDIUM)
            bg_color (tuple): Background color (defaults to BLACK)
            text_color (tuple): Text color (defaults to WHITE)
        """
        font = font if font else self.FONT_MEDIUM
        bg_color = bg_color if bg_color else self.config.BLACK
        text_color = text_color if text_color else self.config.WHITE
        
        start_time = time.time()
        end_time = start_time + duration_ms / 1000.0
        
        running = True
        while running:
            current_time = time.time()
            remaining_time = max(0, end_time - current_time)
            
            # Convert to minutes:seconds format
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            time_text = f"{minutes:02d}:{seconds:02d}"
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_pygame_and_exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.quit_pygame_and_exit()
            
            # Draw screen
            self.screen.fill(bg_color)

            message_lines = message.split('\n')
            line_height = font.get_linesize()
            start_y = (self.config.SCREEN_HEIGHT // 2 - 50) - (line_height * (len(message_lines) -1)) / 2


            for i, line in enumerate(message_lines):
                message_surface = font.render(line, True, text_color)
                # 3. Calculate the rect for each line, adjusting the y position
                message_rect = message_surface.get_rect(
                    center=(self.config.SCREEN_WIDTH // 2, start_y + i * line_height)
                )
                self.screen.blit(message_surface, message_rect)


            # Draw timer
            timer_surface = self.FONT_LARGE.render(time_text, True, text_color)
            timer_rect = timer_surface.get_rect(center=(self.config.SCREEN_WIDTH // 2, 
                                                        self.config.SCREEN_HEIGHT // 2 + 50))
            self.screen.blit(timer_surface, timer_rect)
            
            pygame.display.flip()
            
            # Check if timer has expired
            if remaining_time <= 0:
                running = False
            
            # Small delay to reduce CPU usage
            pygame.time.wait(10)
    def quit_pygame_and_exit(self):
        pygame.quit()
        sys.exit()
