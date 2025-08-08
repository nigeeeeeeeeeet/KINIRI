import pygame
import os
import sys
import math
from typing import List, Tuple, Optional

# Initialize Pygame
pygame.init()

# Window settings
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("KINRI - Level 1")

# Camera class
class Camera:
    def __init__(self, width, height):
        self.camera = pygame.Rect(0, 0, width, height)
        self.width = width
        self.height = height
        self.zoom = 1.0

# Create camera
camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)

# Load images
try:
    # First try with the original path structure
    tileset = pygame.image.load(r"Levels\Tiled\Tileset.png").convert_alpha()
    background = pygame.image.load("Levels/Preview/lvl.jpg").convert()
except FileNotFoundError:
    # If the above fails, try with the full path
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tileset = pygame.image.load(os.path.join(base_dir, "Levels", "Tiled", "Tileset.png")).convert_alpha()
    background = pygame.image.load(os.path.join(base_dir, "Levels", "Preview", "lvl.jpg")).convert()

# Tile settings
TILE_SIZE = 64  # all blocks are 64x64 pixels

# Animation settings
ANIMATION_SPEED = 0.05  # Speed of the pulsing animation

class AnimatedRuby:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
        self.animation_time = 0
        self.base_tile = tileset.subsurface((2 * TILE_SIZE, 0, TILE_SIZE, TILE_SIZE))
        
    def update(self, dt: float):
        # Update animation time
        self.animation_time += dt * ANIMATION_SPEED
        self.animation_time %= (2 * math.pi)  # Keep it in 0-2π range for smooth looping
        
    def draw(self, surface: pygame.Surface):
        # Calculate scale factor (0.8 to 1.0)
        scale = 0.9 + 0.1 * math.sin(self.animation_time)
        
        # Create a scaled copy of the ruby
        new_size = (int(TILE_SIZE * scale), int(TILE_SIZE * scale))
        if new_size[0] > 0 and new_size[1] > 0:
            scaled_ruby = pygame.transform.scale(self.base_tile, new_size)
            
            # Calculate position to keep the ruby centered
            x_offset = (TILE_SIZE - new_size[0]) // 2
            y_offset = (TILE_SIZE - new_size[1]) // 2
            
            # Draw the scaled ruby
            surface.blit(scaled_ruby, 
                        (self.x * TILE_SIZE + x_offset, 
                         self.y * TILE_SIZE + y_offset))

# Function to get a tile from the tileset
def get_tile(x: int, y: int) -> pygame.Surface:
    return tileset.subsurface((x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))

# Level map (manually created)
level_map = [
    "                                                                                ",
    "                                                                                ",
    "                            $$$                                                 ",
    "      [ ]                  #####                  [ ]                           ",
    "     ####                ##     ##               ####                           ",
    "    ##                  ##       ##             ##                              ",
    "   ##                  ##         ##           ##                               ",
    "  ##                  ##           ##         ##                                ",
    " ##                  ##             ##       ##                                 ",
    "##                  ##               ##     ##                                  ",
    "                    ##               ##     ##                                  ",
    "                    ##               ##     ##                                  ",
    "                    #################       #################                   ",
    "                                                                                ",
    "                                                                                "
]

# Symbols:
# '#' - ground
# '[' - box start
# ']' - box end
# '$' - ruby
# '^' - spikes

def draw_level(rubies: List[AnimatedRuby], dt: float):
    # Draw background (scaled to fit screen)
    bg_width, bg_height = background.get_size()
    scale = max(SCREEN_WIDTH / bg_width, SCREEN_HEIGHT / bg_height)
    scaled_bg = pygame.transform.scale(background, 
        (int(bg_width * scale), int(bg_height * scale)))
    screen.blit(scaled_bg, (0, 0))
    
    # Calculate visible area
    start_x = max(0, -camera.camera.x // TILE_SIZE - 1)
    end_x = min(len(level_map[0]), (-camera.camera.x + SCREEN_WIDTH) // TILE_SIZE + 2)
    start_y = max(0, -camera.camera.y // TILE_SIZE - 1)
    end_y = min(len(level_map), (-camera.camera.y + SCREEN_HEIGHT) // TILE_SIZE + 2)
    
    # Draw visible tiles
    for y in range(start_y, end_y):
        for x in range(start_x, end_x):
            if y >= len(level_map) or x >= len(level_map[y]):
                continue
                
            tile = level_map[y][x]
            pos = (x * TILE_SIZE + camera.camera.x, 
                  y * TILE_SIZE + camera.camera.y)
            
            if tile == "#":
                screen.blit(get_tile(0, 1), pos)  # ground
            elif tile == "[" or tile == "]":
                screen.blit(get_tile(1, 1), pos)  # box
            elif tile == "^":
                screen.blit(get_tile(3, 0), pos)  # spikes
    
    # Draw animated rubies
    for ruby in rubies:
        ruby.update(dt)
        # Convert ruby position to screen coordinates
        screen_x = ruby.x * TILE_SIZE + camera.camera.x
        screen_y = ruby.y * TILE_SIZE + camera.camera.y
        
        # Only draw if visible
        if (-TILE_SIZE <= screen_x <= SCREEN_WIDTH and 
            -TILE_SIZE <= screen_y <= SCREEN_HEIGHT):
            ruby.draw(screen)

def find_ruby_positions() -> List[Tuple[int, int]]:
    """Find all ruby positions in the level map."""
    ruby_positions = []
    for y, row in enumerate(level_map):
        for x, tile in enumerate(row):
            if tile == "$":
                ruby_positions.append((x, y))
    return ruby_positions

def handle_events():
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                camera.zoom = min(2.0, camera.zoom + 0.1)
            elif event.key == pygame.K_MINUS:
                camera.zoom = max(0.5, camera.zoom - 0.1)
    return True

def update_camera():
    # Simple auto-scroll to show the whole level
    level_width = len(level_map[0]) * TILE_SIZE
    level_height = len(level_map) * TILE_SIZE
    
    # Center camera on level
    target_x = (SCREEN_WIDTH // 2) - (level_width // 2)
    target_y = (SCREEN_HEIGHT // 2) - (level_height // 2)
    
    # Apply zoom
    camera.camera.x = int(target_x * camera.zoom)
    camera.camera.y = int(target_y * camera.zoom)

# Main game loop
def main():
    clock = pygame.time.Clock()
    running = True
    
    # Create animated rubies
    ruby_positions = find_ruby_positions()
    rubies = [AnimatedRuby(x, y) for x, y in ruby_positions]
    
    # For tracking time between frames
    last_time = pygame.time.get_ticks()
    
    while running:
        # Handle events
        running = handle_events()
        
        # Update camera
        update_camera()
        
        # Calculate delta time for smooth animation
        current_time = pygame.time.get_ticks()
        dt = (current_time - last_time) / 1000.0  # Convert to seconds
        last_time = current_time
        
        # Draw everything
        draw_level(rubies, dt)
        
        # Display zoom level
        font = pygame.font.Font(None, 36)
        zoom_text = font.render(f"Zoom: {camera.zoom:.1f}x (Press + or - to adjust)", True, (255, 255, 255))
        screen.blit(zoom_text, (10, 10))
        
        # Update the display
        pygame.display.flip()
        
        # Cap the frame rate
        clock.tick(60)
    
    # Clean up
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
