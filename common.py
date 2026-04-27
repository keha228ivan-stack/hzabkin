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
BACKGROUND_FILE = "assets/store_shelf_bg.png"

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
_BG_CACHE: pygame.Surface | None = None
_BG_CACHE_SIZE: tuple[int, int] | None = None
_BG_SOURCE: str | None = None
_BG_DECOR_CACHE: dict[tuple[bool, int, int], pygame.Surface] = {}


def _build_background_decor(using_photo_bg: bool) -> pygame.Surface:
    decor = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    outer_alpha = 10 if using_photo_bg else 22
    pygame.draw.rect(decor, (0, 0, 0, outer_alpha), (0, 0, WIDTH, HEIGHT))
    pygame.draw.rect(decor, (0, 0, 0, 0), (24, 12, WIDTH - 48, HEIGHT - 24), border_radius=22)

    for i in range(8):
        x = 80 + i * 160
        alpha = 86 if using_photo_bg else 125
        pygame.draw.ellipse(decor, (255, 250, 210, alpha), (x, 26, 95, 14))

    if not using_photo_bg:
        floor_start = int(HEIGHT * 0.42)
        floor_end = LANES_Y[0] + 48
        row = 0
        y0 = floor_start
        while y0 < floor_end:
            shade = max(158, 240 - row * 6)
            pygame.draw.rect(decor, (shade, shade, shade + 10), (0, y0, WIDTH, 24))
            if row % 2 == 0:
                pygame.draw.line(decor, (245, 245, 255), (0, y0 + 2), (WIDTH, y0 + 2), 1)
            row += 1
            y0 += 24

        for i in range(9):
            x = i * 220
            pygame.draw.rect(decor, (195, 210, 235), (x, 120, 130, 180), border_radius=12)
            pygame.draw.rect(decor, (180, 198, 228), (x + 10, 145, 110, 12), border_radius=5)
            pygame.draw.rect(decor, (180, 198, 228), (x + 10, 200, 110, 12), border_radius=5)
            for j, color in enumerate([(246, 110, 110), (98, 195, 122), (86, 165, 255), (248, 197, 88)]):
                pygame.draw.rect(decor, color, (x + 16 + j * 24, 160, 18, 30), border_radius=4)

    lane_bands = [
        ((77, 156, 255), (148, 210, 255)),
        ((255, 146, 92), (255, 210, 126)),
        ((139, 118, 255), (198, 165, 255)),
    ]
    for idx, lane_y in enumerate(LANES_Y):
        main, glow = lane_bands[idx]
        band_top = lane_y + 5
        pygame.draw.rect(decor, glow, (0, band_top - 6, WIDTH, 14), border_radius=8)
        pygame.draw.rect(decor, main, (0, band_top - 2, WIDTH, 6), border_radius=6)
        pygame.draw.line(decor, WHITE, (0, band_top + 1), (WIDTH, band_top + 1), 2)

    return decor


def _pick_background_file() -> str | None:
    if os.path.exists(BACKGROUND_FILE):
        return BACKGROUND_FILE
    if not os.path.isdir("assets"):
        return None

    candidates: list[tuple[int, str]] = []
    for name in os.listdir("assets"):
        lower = name.lower()
        if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        path = os.path.join("assets", name)
        try:
            img = pygame.image.load(path)
        except pygame.error:
            continue
        w, h = img.get_size()
        if h == 0:
            continue
        aspect = w / h
        if not (1.4 <= aspect <= 4.5):
            continue
        score = w * h
        if any(k in lower for k in ("bg", "background", "store", "shelf", "фон")):
            score += 10_000_000
        candidates.append((score, path))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


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
        "leaderboard": [],
    }
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            default.update(data)
            if not isinstance(default.get("leaderboard"), list):
                default["leaderboard"] = []
        except Exception:
            pass
    return default


def save_progress(save_data):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)


def draw_background(screen: pygame.Surface, t: float, highlighted_lane: int | None = None):
    global _BG_CACHE, _BG_CACHE_SIZE, _BG_SOURCE, _BG_DECOR_CACHE
    bg_path = _pick_background_file()
    using_photo_bg = bool(bg_path)
    if using_photo_bg:
        if _BG_SOURCE != bg_path:
            _BG_CACHE = None
            _BG_CACHE_SIZE = None
            _BG_SOURCE = bg_path
            _BG_DECOR_CACHE = {}
        if _BG_CACHE is None or _BG_CACHE_SIZE != (WIDTH, HEIGHT):
            loaded = pygame.image.load(bg_path).convert()
            _BG_CACHE = pygame.transform.smoothscale(loaded, (WIDTH, HEIGHT))
            _BG_CACHE_SIZE = (WIDTH, HEIGHT)
        drift_x = int(math.sin(t * 0.12) * 8)
        screen.blit(_BG_CACHE, (drift_x, 0))
    else:
        screen.fill(STORE_BG)
        sky_grad = pygame.Surface((WIDTH, 210), pygame.SRCALPHA)
        for y in range(210):
            mix = y / 210
            r = int(255 - 12 * mix)
            g = int(238 - 42 * mix)
            b = int(180 + 35 * mix)
            pygame.draw.line(sky_grad, (r, g, b, 255), (0, y), (WIDTH, y))
        screen.blit(sky_grad, (0, 0))
        pygame.draw.rect(screen, (255, 247, 206), (0, 120, WIDTH, 76))

    decor_key = (using_photo_bg, WIDTH, HEIGHT)
    decor = _BG_DECOR_CACHE.get(decor_key)
    if decor is None:
        decor = _build_background_decor(using_photo_bg)
        _BG_DECOR_CACHE[decor_key] = decor
    screen.blit(decor, (0, 0))

    if highlighted_lane is not None:
        ly = LANES_Y[highlighted_lane]
        overlay = pygame.Surface((WIDTH, 56), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 52))
        screen.blit(overlay, (0, ly - 52))


def draw_glass_panel(screen: pygame.Surface, rect: pygame.Rect, fill=(255, 255, 255, 205), border=(170, 185, 220), radius: int = 16):
    shadow = pygame.Surface((rect.w + 12, rect.h + 12), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (34, 41, 68, 70), (6, 6, rect.w, rect.h), border_radius=radius + 3)
    screen.blit(shadow, (rect.x - 6, rect.y - 2))

    glass = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(glass, fill, (0, 0, rect.w, rect.h), border_radius=radius)
    highlight_h = max(24, rect.h // 3)
    pygame.draw.rect(glass, (255, 255, 255, 68), (10, 8, rect.w - 20, highlight_h), border_radius=max(8, radius - 4))
    pygame.draw.rect(glass, border, (0, 0, rect.w, rect.h), 2, border_radius=radius)
    screen.blit(glass, rect.topleft)


def random_obstacle_or_enemy():
    lane = random.randint(0, 2)
    roll = random.random()
    if roll < 0.36:
        etype = random.choice(ENEMY_TYPES)
        return Entity(etype, lane, WIDTH + 120, speed_mul=random.uniform(0.95, 1.25), is_enemy=True)
    weighted_obstacles = OBSTACLE_TYPES + ["hanging_sign", "hanging_sign"]
    etype = random.choice(weighted_obstacles)
    return Entity(etype, lane, WIDTH + 120, speed_mul=random.uniform(0.85, 1.2))


def random_powerup():
    lane = random.randint(0, 2)
    ptype = random.choice(POWERUP_TYPES)
    return Entity(ptype, lane, WIDTH + 100, speed_mul=1.0, is_enemy=False)
