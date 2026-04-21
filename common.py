import json
import math
import os
import random
from dataclasses import dataclass

import pygame

WIDTH, HEIGHT = 1280, 720
FPS = 60
GROUND_Y = HEIGHT - 140
LANES_Y = [GROUND_Y - 10, GROUND_Y - 70, GROUND_Y - 130]
PLAYER_X = 220
SAVE_FILE = "save_data.json"

SKY = (255, 236, 170)
STORE_BG = (236, 246, 255)
FLOOR = (224, 224, 240)
TEXT = (32, 32, 48)
WHITE = (255, 255, 255)
RED = (226, 65, 65)
GREEN = (40, 190, 95)
BLUE = (60, 145, 255)
YELLOW = (255, 210, 70)
PURPLE = (165, 95, 245)
ORANGE = (255, 145, 55)


@dataclass
class SausageType:
    name: str
    color: tuple[int, int, int]
    ability: str


SAUSAGE_TYPES = [
    SausageType("Классическая", (220, 90, 65), "Стандартный баланс"),
    SausageType("Охотничья", (160, 80, 55), "Двойной прыжок"),
    SausageType("Баварская", (235, 145, 95), "+1 дополнительная жизнь"),
]

OBSTACLE_TYPES = [
    "cart",
    "mop",
    "shelf",
    "kid",
    "conveyor",
    "freezer",
    "box",
    "long_box",
    "hanging_sign",
]
ENEMY_TYPES = ["butcher", "scanner", "robot"]
POWERUP_TYPES = ["ketchup", "mayo", "mustard", "cola", "olive"]


class Player:
    def __init__(self, sausage: SausageType, extra_life: int = 0):
        self.sausage = sausage
        self.x = PLAYER_X
        self.lane = 1
        self.target_lane = 1
        self.y = LANES_Y[self.lane]
        self.base_w = 92
        self.base_h = 40
        self.w = self.base_w
        self.h = self.base_h
        self.vel_y = 0.0
        self.on_ground = True
        self.jump_count = 0
        self.max_jumps = 2 if sausage.name == "Охотничья" else 1
        self.sliding = False
        self.slide_timer = 0.0

        self.max_hp = 3 + extra_life
        self.hp = self.max_hp
        self.score = 0
        self.coins = 0
        self.distance = 0.0

        self.invuln_timer = 0.0
        self.speed_boost_timer = 0.0
        self.magnet_timer = 0.0
        self.instant_boost_timer = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.w // 2), int(self.y - self.h), self.w, self.h)

    def move_lane(self, direction: int):
        self.target_lane = max(0, min(2, self.target_lane + direction))

    def jump(self):
        if self.jump_count < self.max_jumps:
            self.vel_y = -16.8
            self.on_ground = False
            self.jump_count += 1

    def slide(self):
        if not self.sliding and self.on_ground:
            self.sliding = True
            self.slide_timer = 0.6

    def apply_powerup(self, ptype: str):
        if ptype == "ketchup":
            self.speed_boost_timer = 5.0
        elif ptype == "mayo":
            self.invuln_timer = 4.0
        elif ptype == "mustard":
            self.magnet_timer = 7.0
        elif ptype == "cola":
            self.instant_boost_timer = 1.2
        elif ptype == "olive":
            self.hp = min(self.max_hp, self.hp + 1)

    def update(self, dt: float):
        target_y = LANES_Y[self.target_lane]
        self.y += (target_y - self.y) * min(1.0, 10 * dt)

        if not self.on_ground:
            self.vel_y += 17.0 * dt
            self.y += self.vel_y
            ground = LANES_Y[self.target_lane]
            if self.y >= ground:
                self.y = ground
                self.vel_y = 0
                self.on_ground = True
                self.jump_count = 0

        if self.sliding:
            self.slide_timer -= dt
            self.h = 24
            self.w = 102
            if self.slide_timer <= 0:
                self.sliding = False
                self.h = self.base_h
                self.w = self.base_w

        for attr in ["invuln_timer", "speed_boost_timer", "magnet_timer", "instant_boost_timer"]:
            value = getattr(self, attr)
            if value > 0:
                setattr(self, attr, max(0.0, value - dt))


class Entity:
    def __init__(self, etype: str, lane: int, x: float, speed_mul: float = 1.0, is_enemy: bool = False):
        self.etype = etype
        self.lane = lane
        self.x = x
        self.y = LANES_Y[lane]
        self.is_enemy = is_enemy
        self.speed_mul = speed_mul
        self.passed = False

        if etype in ["cart", "shelf", "freezer"]:
            self.w, self.h = 95, 90
        elif etype == "box":
            self.w, self.h = 66, 34
        elif etype == "long_box":
            self.w, self.h = 170, 38
        elif etype == "hanging_sign":
            self.w, self.h = 105, 55
        elif etype in ["mop", "scanner"]:
            self.w, self.h = 40, 100
        elif etype in ["kid", "butcher", "robot"]:
            self.w, self.h = 68, 86
        elif etype == "conveyor":
            self.w, self.h = 120, 42
        else:
            self.w, self.h = 44, 44

        if etype == "hanging_sign":
            self.y = LANES_Y[lane] - 36

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.w // 2), int(self.y - self.h), self.w, self.h)

    def update(self, dt: float, speed: float):
        self.x -= speed * self.speed_mul * dt

    def offscreen(self) -> bool:
        return self.x < -200


def load_save():
    default = {
        "money": 0,
        "upgrades": {
            "hp": 0,
            "speed": 0,
            "coin_bonus": 0,
        },
        "best_distance": 0,
    }
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            default.update(data)
        except Exception:
            pass
    return default


def save_progress(save_data):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)


def draw_background(screen: pygame.Surface, t: float, highlighted_lane: int | None = None):
    screen.fill(STORE_BG)
    pygame.draw.rect(screen, (255, 222, 150), (0, 0, WIDTH, 140))
    pygame.draw.rect(screen, (255, 235, 180), (0, 120, WIDTH, 70))
    for i in range(8):
        x = 80 + i * 160
        pulse = 14 + int(4 * math.sin(t * 2.3 + i))
        pygame.draw.ellipse(screen, (255, 250, 210), (x, 26, 95, pulse))

    for i in range(14):
        y0 = int(HEIGHT * 0.42 + i * 24)
        shade = max(150, 240 - i * 6)
        pygame.draw.rect(screen, (shade, shade, shade + 10), (0, y0, WIDTH, 26))
        if i % 2 == 0:
            pygame.draw.line(screen, (245, 245, 255), (0, y0 + 2), (WIDTH, y0 + 2), 1)

    for i in range(9):
        x = i * 220 - (t * 90) % 220
        pygame.draw.rect(screen, (195, 210, 235), (x, 120, 130, 180), border_radius=12)
        pygame.draw.rect(screen, (180, 198, 228), (x + 10, 145, 110, 12), border_radius=5)
        pygame.draw.rect(screen, (180, 198, 228), (x + 10, 200, 110, 12), border_radius=5)
        for j, color in enumerate([(246, 110, 110), (98, 195, 122), (86, 165, 255), (248, 197, 88)]):
            pygame.draw.rect(screen, color, (x + 16 + j * 24, 160, 18, 30), border_radius=4)

    lane_bands = [
        ((77, 156, 255), (148, 210, 255)),
        ((255, 146, 92), (255, 210, 126)),
        ((139, 118, 255), (198, 165, 255)),
    ]
    for idx, lane_y in enumerate(LANES_Y):
        main, glow = lane_bands[idx]
        band_top = lane_y + 5
        pygame.draw.rect(screen, glow, (0, band_top - 6, WIDTH, 14), border_radius=8)
        pygame.draw.rect(screen, main, (0, band_top - 2, WIDTH, 6), border_radius=6)
        pygame.draw.line(screen, WHITE, (0, band_top + 1), (WIDTH, band_top + 1), 2)

    if highlighted_lane is not None:
        ly = LANES_Y[highlighted_lane]
        overlay = pygame.Surface((WIDTH, 56), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 40))
        screen.blit(overlay, (0, ly - 52))

    for i in range(18):
        sx = int((i * 80 + t * 55) % WIDTH)
        sy = 180 + int(16 * math.sin(t * 1.8 + i))
        pygame.draw.circle(screen, (255, 255, 255), (sx, sy), 1)


def random_obstacle_or_enemy():
    lane = random.randint(0, 2)
    roll = random.random()
    if roll < 0.36:
        etype = random.choice(ENEMY_TYPES)
        return Entity(etype, lane, WIDTH + 120, speed_mul=random.uniform(0.95, 1.25), is_enemy=True)
    etype = random.choice(OBSTACLE_TYPES)
    return Entity(etype, lane, WIDTH + 120, speed_mul=random.uniform(0.85, 1.2))


def random_powerup():
    lane = random.randint(0, 2)
    ptype = random.choice(POWERUP_TYPES)
    return Entity(ptype, lane, WIDTH + 100, speed_mul=1.0, is_enemy=False)
