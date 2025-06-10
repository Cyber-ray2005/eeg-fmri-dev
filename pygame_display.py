import pygame
import time
import sys
import os

class PygameDisplay:
    def __init__(self, config):
        pygame.init()
        pygame.font.init()
        self.config = config
        self.screen = self._setup_screen()
        self.FONT_LARGE = pygame.font.Font(None, 74)
        self.FONT_MEDIUM = pygame.font.Font(None, 50)
        self.FONT_SMALL = pygame.font.Font(None, 36)
        self.scaled_images = {}

    def _setup_screen(self):
        if self.config.FULLSCREEN_MODE:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT = screen.get_size()
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
            for finger_type, img_name in self.config.NORMAL_FINGER_IMAGE_MAP.items():
                self.scaled_images[finger_type] = self._load_and_scale_image(
                    img_name, self.config.IMAGE_FOLDER,
                    self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT
                )
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
        font = font if font else self.FONT_MEDIUM
        bg_color = bg_color if bg_color else self.config.GRAY
        text_color = text_color if text_color else self.config.BLACK

        self.screen.fill(bg_color)
        self._draw_text(self.screen, message, font, text_color, self.config.SCREEN_WIDTH // 2, self.config.SCREEN_HEIGHT // 2)

        if server_response:
            response_text = self.FONT_SMALL.render(f"Server Says: {server_response}", True, self.config.BLACK)
            response_rect = response_text.get_rect(centerx=self.config.SCREEN_WIDTH // 2, bottom=self.config.SCREEN_HEIGHT - 20)
            self.screen.blit(response_text, response_rect)

        pygame.display.flip()

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
        cross_size = 90
        center_x, center_y = self.config.SCREEN_WIDTH // 2, self.config.SCREEN_HEIGHT // 2
        pygame.draw.line(self.screen, self.config.WHITE, (center_x - cross_size // 2, center_y), (center_x + cross_size // 2, center_y), 10)
        pygame.draw.line(self.screen, self.config.WHITE, (center_x, center_y - cross_size // 2), (center_x, center_y + cross_size // 2), 10)
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
                cropped_surface = pygame.Surface((crop_rect[2], crop_rect[3]), pygame.SRCALPHA) # Use SRCALPHA for transparent images
                cropped_surface.blit(image_surface, (0, 0), crop_rect)
                image_to_display = cropped_surface
            except Exception as e:
                print(f"Error cropping image: {e}. Displaying original.")
                image_to_display = image_surface
        else:
            image_to_display = image_surface

        image_rect = image_to_display.get_rect(center=(self.config.SCREEN_WIDTH // 2, self.config.SCREEN_HEIGHT // 2))
        self.screen.blit(image_to_display, image_rect)

        pygame.display.flip()

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

    def quit_pygame_and_exit(self):
        pygame.quit()
        sys.exit()
