import pygame
import os
import sys
from pygame import *

# Initialize Pygame
pygame.init()

# Set up the display
WINDOW_WIDTH = 1370
WINDOW_HEIGHT = 768
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("KINRI Game")

# Colors
BLACK = (0, 0, 0)

class GameSprite(pygame.sprite.Sprite):
    def __init__(self, player_image, player_x, player_y, size_x, size_y):
        pygame.sprite.Sprite.__init__(self)
        self.image_normal = pygame.transform.scale(pygame.image.load(player_image), (size_x, size_y))
        self.image = self.image_normal
        self.rect = self.image.get_rect()
        self.rect.x = player_x
        self.rect.y = player_y
    
    def update(self, mouse_pos, player_image_hover, size_x, size_y):
        if self.rect.collidepoint(mouse_pos):
            self.image_hover = pygame.transform.scale(pygame.image.load(player_image_hover), (size_x, size_y))
            self.image = self.image_hover
        else:
            self.image = self.image_normal

    def reset(self):
        screen.blit(self.image, (self.rect.x, self.rect.y))

class Player(GameSprite):
    def __init__(self, player_image, player_x, player_y, size_x, size_y, player_x_speed, player_y_speed):
        super().__init__(player_image, player_x, player_y, size_x, size_y)
        self.x_speed = player_x_speed
        self.y_speed = 0
        self.direction = "right"
        self.animation_frames = []
        self.frame_index = 0
        self.jump_power = -15
        self.gravity = 0.8
        self.on_ground = False
        self.load_animation()
        self.load_jump_fall_images()

    def load_animation(self):
        # Load run animation
        sheet_right = pygame.image.load("Main Characters\\q\\Run.png").convert_alpha()
        sheet_width, sheet_height = sheet_right.get_size()
        frame_width = sheet_width // 12
        frame_height = sheet_height
        self.frames_right = [
            pygame.transform.scale(sheet_right.subsurface((i * frame_width, 0, frame_width, frame_height)), (192, 192))
            for i in range(12)
        ]
        self.frames_left = [pygame.transform.flip(f, True, False) for f in self.frames_right]
        
        # Load idle animation
        idle_sheet = pygame.image.load("Main Characters\\q\\Idle.png").convert_alpha()
        idle_width, idle_height = idle_sheet.get_size()
        idle_frame_width = idle_width // 11  # Assuming 11 frames in idle animation
        self.idle_frames_right = [
            pygame.transform.scale(idle_sheet.subsurface((i * idle_frame_width, 0, idle_frame_width, idle_height)), (192, 192))
            for i in range(11)
        ]
        self.idle_frames_left = [pygame.transform.flip(f, True, False) for f in self.idle_frames_right]
        
        self.animation_frames = self.idle_frames_right  # Start with idle animation
        self.is_moving = False
        
    def load_jump_fall_images(self):
        # Load jump image
        jump_img = pygame.image.load("Main Characters\\q\\Jump.png").convert_alpha()
        self.jump_img_right = pygame.transform.scale(jump_img, (192, 192))
        self.jump_img_left = pygame.transform.flip(self.jump_img_right, True, False)
        
        # Load fall image
        fall_img = pygame.image.load("Main Characters\\q\\Fall.png").convert_alpha()
        self.fall_img_right = pygame.transform.scale(fall_img, (192, 192))
        self.fall_img_left = pygame.transform.flip(self.fall_img_right, True, False)

    def update_animation(self):
        self.frame_index += 0.2
        if self.frame_index >= len(self.animation_frames):
            self.frame_index = 0
        self.image = self.animation_frames[int(self.frame_index)]

    def jump(self):
        if self.on_ground:
            self.y_speed = self.jump_power
            self.on_ground = False

    def update(self, barriers):
        keys = pygame.key.get_pressed()
        
        # Handle jump
        if keys[pygame.K_UP] and self.on_ground:
            self.jump()
        
        # Reset horizontal speed and movement state
        self.x_speed = 0
        self.is_moving = False
        
        # Handle left/right movement
        if keys[pygame.K_LEFT]:
            self.x_speed = -6
            self.direction = "left"
            self.is_moving = True
            if self.on_ground:
                self.animation_frames = self.frames_left
        elif keys[pygame.K_RIGHT]:
            self.x_speed = 6
            self.direction = "right"
            self.is_moving = True
            if self.on_ground:
                self.animation_frames = self.frames_right
        
        # Apply gravity
        self.y_speed += self.gravity
        
        # Update position based on speed
        self.rect.x += self.x_speed
        self.rect.y += self.y_speed
        
        # Check for ground collision
        if self.rect.bottom >= WINDOW_HEIGHT - 50:  # 50 is ground level
            self.rect.bottom = WINDOW_HEIGHT - 50
            self.y_speed = 0
            self.on_ground = True
            # Reset to run animation when on ground
            if self.direction == "right":
                self.animation_frames = self.frames_right
            else:
                self.animation_frames = self.frames_left
        else:
            self.on_ground = False
            # Use jump or fall image based on vertical movement
            if self.y_speed < 0:  # Going up (jumping)
                if self.direction == "right":
                    self.animation_frames = [self.jump_img_right]
                else:
                    self.animation_frames = [self.jump_img_left]
            else:  # Coming down (falling)
                if self.direction == "right":
                    self.animation_frames = [self.fall_img_right]
                else:
                    self.animation_frames = [self.fall_img_left]
        
        # Keep player on screen
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > WINDOW_WIDTH:
            self.rect.right = WINDOW_WIDTH
        if self.rect.top < 0:
            self.rect.top = 0
            self.y_speed = 0
        
        # Set idle animation when not moving and on ground
        if not self.is_moving and self.on_ground:
            if self.direction == "right":
                self.animation_frames = self.idle_frames_right
            else:
                self.animation_frames = self.idle_frames_left
        
        # Update animation
        self.update_animation()

# Create player instance after class definitions
player = Player("Main Characters\\q\\Run.png", 
                WINDOW_WIDTH // 2 - 96,  # Center horizontally (192x192 sprite)
                WINDOW_HEIGHT // 2 - 96,  # Center vertically
                192, 192, 0, 0)  # Size and initial speed

# Main game loop
running = True
clock = pygame.time.Clock()
FPS = 60

while running:
    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
    
    # Fill the screen with black
    screen.fill(BLACK)
    
    # Update player
    player.update([])  # Pass empty barriers list for now
    
    # Draw player
    player.reset()
    
    # Update the display
    pygame.display.flip()
    
    # Cap the frame rate
    clock.tick(FPS)

# Quit Pygame
pygame.quit()
sys.exit()