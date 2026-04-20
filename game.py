import json
import math
import os
import random
import sys
from dataclasses import dataclass

import pygame

# =========================
# Config
# =========================
WIDTH, HEIGHT = 1280, 720  # Landscape orientation
FPS = 60
GROUND_Y = HEIGHT - 140
LANES_Y = [GROUND_Y - 10, GROUND_Y - 70, GROUND_Y - 130]  # 3 lanes (low/mid/high)
PLAYER_X = 220
SAVE_FILE = "save_data.json"

# Colors
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
    "cart",       # тележка
    "mop",        # швабра
    "shelf",      # полка
    "kid",        # ребенок
    "conveyor",   # конвейер
    "freezer",    # витрина
    "box",        # коробки (низкое препятствие, можно перепрыгнуть)
    "long_box",   # длинный ряд коробок (нужен более длинный прыжок)
    "hanging_sign",  # навесная вывеска (нужно пригнуться)
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

        # powerups
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
            # longer and smoother airtime
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
        # Smooth lane movement
        target_y = LANES_Y[self.target_lane]
        self.y += (target_y - self.y) * min(1.0, 10 * dt)

        # Jump physics
        if not self.on_ground:
            self.vel_y += 17.0 * dt
            self.y += self.vel_y
            ground = LANES_Y[self.target_lane]
            if self.y >= ground:
                self.y = ground
                self.vel_y = 0
                self.on_ground = True
                self.jump_count = 0

        # Slide state
        if self.sliding:
            self.slide_timer -= dt
            self.h = 24
            self.w = 102
            if self.slide_timer <= 0:
                self.sliding = False
                self.h = self.base_h
                self.w = self.base_w

        # Powerup timers
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
        else:  # powerup
            self.w, self.h = 42, 42

        if etype == "hanging_sign":
            self.y = LANES_Y[lane] - 36

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.w // 2), int(self.y - self.h), self.w, self.h)

    def update(self, dt: float, speed: float):
        self.x -= speed * self.speed_mul * dt

    def offscreen(self) -> bool:
        return self.x < -200


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Забег Сосисек: Побег из Супермаркета")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 28)
        self.big_font = pygame.font.SysFont("arial", 52, bold=True)
        self.small_font = pygame.font.SysFont("arial", 20)

        self.save = self.load_save()
        self.state = "menu"
        self.selected_sausage = 0

        self.player = None
        self.entities: list[Entity] = []
        self.particles = []

        self.base_speed = 360.0
        self.world_speed = self.base_speed
        self.difficulty = 1.0
        self.spawn_timer = 0.0
        self.powerup_timer = 0.0
        self.invuln_flash = False

        # Swipe support
        self.touch_start = None
        self.cloud_offset = 0.0

    def load_save(self):
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

    def save_progress(self):
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.save, f, ensure_ascii=False, indent=2)

    def start_run(self):
        sausage = SAUSAGE_TYPES[self.selected_sausage]
        extra_life = self.save["upgrades"]["hp"]
        self.player = Player(sausage, extra_life=extra_life)
        self.entities.clear()
        self.state = "running"
        self.spawn_timer = 1.2
        self.powerup_timer = 3.0
        self.world_speed = self.base_speed + self.save["upgrades"]["speed"] * 28
        self.difficulty = 1.0

    def buy_upgrade(self, name: str):
        lvl = self.save["upgrades"][name]
        cost = 30 + lvl * 35
        if self.save["money"] >= cost and lvl < 5:
            self.save["money"] -= cost
            self.save["upgrades"][name] += 1
            self.save_progress()

    def spawn_obstacle_or_enemy(self):
        lane = random.randint(0, 2)
        roll = random.random()
        if roll < min(0.22 + self.difficulty * 0.05, 0.45):
            etype = random.choice(ENEMY_TYPES)
            ent = Entity(etype, lane, WIDTH + 120, speed_mul=random.uniform(0.95, 1.25), is_enemy=True)
        else:
            etype = random.choice(OBSTACLE_TYPES)
            ent = Entity(etype, lane, WIDTH + 120, speed_mul=random.uniform(0.85, 1.2))
        self.entities.append(ent)

    def spawn_powerup(self):
        lane = random.randint(0, 2)
        ptype = random.choice(POWERUP_TYPES)
        self.entities.append(Entity(ptype, lane, WIDTH + 100, speed_mul=1.0, is_enemy=False))

    def collide_with_player(self, ent: Entity):
        if not self.player:
            return
        p = self.player
        # Damage sources can hit only on the same lane.
        # This prevents getting hurt from lower-lane hazards while running on upper lanes.
        if ent.etype not in POWERUP_TYPES and ent.lane != p.target_lane:
            return

        if ent.rect.colliderect(p.rect):
            if ent.etype in POWERUP_TYPES:
                p.apply_powerup(ent.etype)
                if ent.etype != "olive":
                    p.coins += 4 + self.save["upgrades"]["coin_bonus"]
                if ent in self.entities:
                    self.entities.remove(ent)
                return

            if p.invuln_timer > 0:
                if ent in self.entities:
                    self.entities.remove(ent)
                return

            p.hp -= 1
            p.invuln_timer = 1.2
            if ent in self.entities:
                self.entities.remove(ent)

            if p.hp <= 0:
                self.end_run()

    def end_run(self):
        if not self.player:
            return
        money_gain = self.player.coins + int(self.player.distance // 120)
        self.save["money"] += money_gain
        self.save["best_distance"] = max(self.save["best_distance"], int(self.player.distance))
        self.save_progress()
        self.state = "game_over"

    def handle_swipe(self, dx, dy):
        if self.state != "running" or not self.player:
            return
        if abs(dx) > abs(dy):
            if dx > 35:
                self.player.move_lane(+1)
            elif dx < -35:
                self.player.move_lane(-1)
        else:
            if dy < -35:
                self.player.jump()
            elif dy > 35:
                self.player.slide()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

            if event.type == pygame.KEYDOWN:
                if self.state == "menu":
                    if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        self.selected_sausage = event.key - pygame.K_1
                    if event.key == pygame.K_RETURN:
                        self.start_run()
                    if event.key == pygame.K_h:
                        self.buy_upgrade("hp")
                    if event.key == pygame.K_s:
                        self.buy_upgrade("speed")
                    if event.key == pygame.K_c:
                        self.buy_upgrade("coin_bonus")

                elif self.state == "running" and self.player:
                    if event.key == pygame.K_w:
                        self.player.move_lane(+1)
                    elif event.key == pygame.K_s:
                        self.player.move_lane(-1)
                    elif event.key == pygame.K_LEFT:
                        self.player.move_lane(-1)
                    elif event.key == pygame.K_RIGHT:
                        self.player.move_lane(+1)
                    elif event.key in (pygame.K_UP, pygame.K_SPACE):
                        self.player.jump()
                    elif event.key == pygame.K_DOWN:
                        self.player.slide()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "menu"

                elif self.state == "game_over":
                    if event.key == pygame.K_RETURN:
                        self.start_run()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "menu"

            # Mouse swipe emulation
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.touch_start = pygame.Vector2(event.pos)
            if event.type == pygame.MOUSEBUTTONUP and self.touch_start is not None:
                end = pygame.Vector2(event.pos)
                delta = end - self.touch_start
                self.handle_swipe(delta.x, delta.y)
                self.touch_start = None

    def update_running(self, dt: float):
        p = self.player
        if not p:
            return

        # Difficulty progression
        self.difficulty += dt * 0.03
        speed_bonus = 0
        if p.speed_boost_timer > 0:
            speed_bonus += 120
        if p.instant_boost_timer > 0:
            speed_bonus += 280
        self.world_speed = (self.base_speed + self.save["upgrades"]["speed"] * 28 + self.difficulty * 38 + speed_bonus)

        p.update(dt)
        p.distance += self.world_speed * dt * 0.25
        p.score = int(p.distance) + p.coins * 10

        # spawn obstacles and enemies
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_obstacle_or_enemy()
            self.spawn_timer = max(0.35, 1.2 - self.difficulty * 0.07)

        # spawn powerups
        self.powerup_timer -= dt
        if self.powerup_timer <= 0:
            self.spawn_powerup()
            self.powerup_timer = random.uniform(2.2, 4.5)

        # entity updates
        for ent in list(self.entities):
            ent.update(dt, self.world_speed)

            # Mustard magnet (coin-like pull on powerups)
            if p.magnet_timer > 0 and ent.etype in POWERUP_TYPES:
                ent.y += (p.y - 20 - ent.y) * min(1.0, 6 * dt)

            # reward for passing dangerous entities
            if ent.x < p.x and not ent.passed and ent.etype not in POWERUP_TYPES:
                ent.passed = True
                p.coins += 1 + self.save["upgrades"]["coin_bonus"]

            self.collide_with_player(ent)

            if ent.offscreen() and ent in self.entities:
                self.entities.remove(ent)

    def draw_background(self, t: float):
        self.screen.fill(STORE_BG)

        # bright animated header
        pygame.draw.rect(self.screen, (255, 222, 150), (0, 0, WIDTH, 140))
        pygame.draw.rect(self.screen, (255, 235, 180), (0, 120, WIDTH, 70))
        for i in range(8):
            x = 80 + i * 160
            pulse = 14 + int(4 * math.sin(t * 2.3 + i))
            pygame.draw.ellipse(self.screen, (255, 250, 210), (x, 26, 95, pulse))

        # pseudo-3D floor gradient stripes
        for i in range(14):
            y0 = int(HEIGHT * 0.42 + i * 24)
            shade = max(150, 240 - i * 6)
            pygame.draw.rect(self.screen, (shade, shade, shade + 10), (0, y0, WIDTH, 26))
            if i % 2 == 0:
                pygame.draw.line(self.screen, (245, 245, 255), (0, y0 + 2), (WIDTH, y0 + 2), 1)

        # moving shelf silhouettes (parallax)
        for i in range(9):
            x = (i * 220 - (t * 90) % 220)
            pygame.draw.rect(self.screen, (195, 210, 235), (x, 120, 130, 180), border_radius=12)
            pygame.draw.rect(self.screen, (180, 198, 228), (x + 10, 145, 110, 12), border_radius=5)
            pygame.draw.rect(self.screen, (180, 198, 228), (x + 10, 200, 110, 12), border_radius=5)
            for j in range(4):
                color = [(246, 110, 110), (98, 195, 122), (86, 165, 255), (248, 197, 88)][j]
                pygame.draw.rect(self.screen, color, (x + 16 + j * 24, 160, 18, 30), border_radius=4)

        # moving decorative elements
        for i in range(5):
            bx = WIDTH - ((t * 120 + i * 250) % (WIDTH + 220))
            by = 80 + int(math.sin(t * 1.4 + i) * 15)
            pygame.draw.circle(self.screen, (255, 120, 160), (int(bx), by), 22)
            pygame.draw.circle(self.screen, (255, 182, 70), (int(bx + 36), by + 18), 18)
            pygame.draw.line(self.screen, (190, 190, 210), (int(bx), by + 22), (int(bx), by + 44), 2)
            pygame.draw.line(self.screen, (190, 190, 210), (int(bx + 36), by + 36), (int(bx + 36), by + 58), 2)

        # strong lane separators
        lane_bands = [
            ((77, 156, 255), (148, 210, 255)),
            ((255, 146, 92), (255, 210, 126)),
            ((139, 118, 255), (198, 165, 255)),
        ]
        for idx, lane_y in enumerate(LANES_Y):
            main, glow = lane_bands[idx]
            band_top = lane_y + 5
            pygame.draw.rect(self.screen, glow, (0, band_top - 6, WIDTH, 14), border_radius=8)
            pygame.draw.rect(self.screen, main, (0, band_top - 2, WIDTH, 6), border_radius=6)
            pygame.draw.line(self.screen, WHITE, (0, band_top + 1), (WIDTH, band_top + 1), 2)

        if self.player and self.state == "running":
            ly = LANES_Y[self.player.target_lane]
            overlay = pygame.Surface((WIDTH, 56), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, 40))
            self.screen.blit(overlay, (0, ly - 52))

        # tiny ambient sparkles to reduce flat/carton look
        for i in range(18):
            sx = int((i * 80 + t * 55) % WIDTH)
            sy = 180 + int(16 * math.sin(t * 1.8 + i))
            pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), 1)

    def draw_player(self):
        if not self.player:
            return
        p = self.player
        body_rect = p.rect

        # invulnerability blinking
        if p.invuln_timer > 0:
            self.invuln_flash = not self.invuln_flash
            if not self.invuln_flash:
                return

        # sausage body
        outline = body_rect.inflate(8, 8)
        pygame.draw.ellipse(self.screen, (96, 46, 40), outline)
        pygame.draw.ellipse(self.screen, p.sausage.color, body_rect)
        pygame.draw.ellipse(self.screen, (250, 220, 180), body_rect.inflate(-30, -18), 3)
        pygame.draw.ellipse(self.screen, (255, 245, 225), (body_rect.x + 8, body_rect.y + 6, 42, 12))

        # cartoon face
        eye_y = body_rect.y + 14
        pygame.draw.circle(self.screen, WHITE, (body_rect.x + 26, eye_y), 6)
        pygame.draw.circle(self.screen, WHITE, (body_rect.x + 52, eye_y), 6)
        pygame.draw.circle(self.screen, (0, 0, 0), (body_rect.x + 26, eye_y), 2)
        pygame.draw.circle(self.screen, (0, 0, 0), (body_rect.x + 52, eye_y), 2)
        pygame.draw.arc(self.screen, (70, 20, 20), (body_rect.x + 26, body_rect.y + 16, 28, 14), math.pi * 0.1, math.pi * 0.9, 2)

        # slide trail
        if p.sliding:
            pygame.draw.ellipse(self.screen, (255, 255, 255, 90), (body_rect.x - 34, body_rect.y + 20, 26, 10))

        shadow_w = int(52 + 10 * math.sin(pygame.time.get_ticks() * 0.015))
        pygame.draw.ellipse(self.screen, (120, 120, 145), (body_rect.centerx - shadow_w // 2, LANES_Y[p.target_lane] - 4, shadow_w, 12))

    def draw_entity(self, ent: Entity):
        r = ent.rect
        et = ent.etype

        # Obstacles and enemies in bright comic style
        if et == "cart":
            pygame.draw.rect(self.screen, (112, 132, 165), r, border_radius=8)
            pygame.draw.rect(self.screen, (185, 205, 235), r.inflate(-12, -28), border_radius=6)
            pygame.draw.circle(self.screen, (40, 40, 40), (r.x + 18, r.bottom), 8)
            pygame.draw.circle(self.screen, (40, 40, 40), (r.right - 18, r.bottom), 8)
        elif et == "mop":
            pygame.draw.rect(self.screen, (190, 145, 90), (r.centerx - 4, r.y, 8, r.h))
            pygame.draw.rect(self.screen, (100, 170, 255), (r.centerx - 20, r.bottom - 14, 40, 14))
        elif et == "shelf":
            pygame.draw.rect(self.screen, (190, 120, 65), r, border_radius=6)
            pygame.draw.rect(self.screen, (240, 220, 90), (r.x + 6, r.y + 16, r.w - 12, 12))
            pygame.draw.rect(self.screen, (95, 210, 140), (r.x + 6, r.y + 40, r.w - 12, 12))
            pygame.draw.rect(self.screen, (255, 130, 130), (r.x + 6, r.y + 64, r.w - 12, 12))
        elif et == "kid":
            pygame.draw.circle(self.screen, (255, 220, 160), (r.centerx, r.y + 20), 16)
            pygame.draw.rect(self.screen, (95, 145, 255), (r.x + 12, r.y + 34, r.w - 24, r.h - 34), border_radius=10)
            pygame.draw.circle(self.screen, (255, 90, 140), (r.centerx - 14, r.y + 18), 2)
            pygame.draw.circle(self.screen, (255, 90, 140), (r.centerx + 14, r.y + 18), 2)
        elif et == "conveyor":
            pygame.draw.rect(self.screen, (90, 90, 105), r, border_radius=8)
            for i in range(4):
                pygame.draw.line(self.screen, (155, 155, 175), (r.x + 10 + i * 28, r.y + 8), (r.x + 20 + i * 28, r.bottom - 8), 2)
        elif et == "freezer":
            pygame.draw.rect(self.screen, (180, 235, 255), r, border_radius=8)
            pygame.draw.rect(self.screen, WHITE, r, 2, border_radius=8)
            pygame.draw.rect(self.screen, (140, 198, 240), (r.x + 10, r.y + 16, r.w - 20, 16), border_radius=6)
        elif et == "box":
            pygame.draw.rect(self.screen, (214, 156, 88), r, border_radius=6)
            pygame.draw.rect(self.screen, (190, 134, 66), (r.x + 2, r.y + 2, r.w - 4, r.h - 4), 2, border_radius=6)
            pygame.draw.line(self.screen, (148, 92, 36), (r.centerx, r.y + 2), (r.centerx, r.bottom - 2), 2)
            pygame.draw.line(self.screen, (148, 92, 36), (r.x + 4, r.centery), (r.right - 4, r.centery), 2)
        elif et == "long_box":
            pygame.draw.rect(self.screen, (220, 162, 94), r, border_radius=6)
            segment = r.w // 3
            for i in range(3):
                sx = r.x + i * segment
                pygame.draw.rect(self.screen, (198, 138, 70), (sx + 2, r.y + 2, segment - 4, r.h - 4), 2, border_radius=4)
                pygame.draw.line(self.screen, (148, 92, 36), (sx + segment // 2, r.y + 4), (sx + segment // 2, r.bottom - 4), 2)
        elif et == "hanging_sign":
            pygame.draw.rect(self.screen, (255, 226, 98), r, border_radius=8)
            pygame.draw.rect(self.screen, (190, 124, 40), r, 3, border_radius=8)
            pygame.draw.line(self.screen, (150, 150, 165), (r.x + 16, r.y - 14), (r.x + 16, r.y), 3)
            pygame.draw.line(self.screen, (150, 150, 165), (r.right - 16, r.y - 14), (r.right - 16, r.y), 3)
            warn = self.small_font.render("LOW", True, (70, 35, 15))
            self.screen.blit(warn, (r.centerx - warn.get_width() // 2, r.y + 16))

        elif et == "butcher":
            pygame.draw.rect(self.screen, (255, 255, 255), r, border_radius=10)
            pygame.draw.circle(self.screen, (255, 215, 170), (r.centerx, r.y + 16), 12)
            pygame.draw.circle(self.screen, (80, 80, 80), (r.right - 10, r.y + 24), 10, 2)
            pygame.draw.rect(self.screen, (220, 36, 64), (r.x + 12, r.y + 40, r.w - 24, 10), border_radius=5)
            pygame.draw.rect(self.screen, (245, 245, 245), (r.x + 8, r.y + 52, r.w - 16, 18), border_radius=4)
        elif et == "scanner":
            pygame.draw.rect(self.screen, PURPLE, r, border_radius=8)
            pygame.draw.rect(self.screen, (255, 120, 170), (r.x + 6, r.y + 10, r.w - 12, 9))
            pulse = int(100 + 80 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.03)))
            pygame.draw.rect(self.screen, (255, pulse, pulse), (r.x + 6, r.y + 25, r.w - 12, 7))
            pygame.draw.circle(self.screen, (220, 220, 255), (r.centerx, r.bottom - 12), 6)
        elif et == "robot":
            pygame.draw.rect(self.screen, (155, 175, 205), r, border_radius=10)
            pygame.draw.circle(self.screen, (90, 120, 255), (r.centerx - 12, r.y + 18), 5)
            pygame.draw.circle(self.screen, (90, 120, 255), (r.centerx + 12, r.y + 18), 5)
            pygame.draw.rect(self.screen, (120, 150, 185), (r.x + 12, r.bottom - 14, r.w - 24, 8), border_radius=4)
            pygame.draw.rect(self.screen, (80, 106, 132), (r.x + 20, r.y + 36, r.w - 40, 10), border_radius=4)

        # Powerups
        elif et == "ketchup":
            pygame.draw.circle(self.screen, RED, r.center, r.w // 2)
            self.draw_letter("K", r.center)
        elif et == "mayo":
            pygame.draw.circle(self.screen, WHITE, r.center, r.w // 2)
            pygame.draw.circle(self.screen, (90, 90, 90), r.center, r.w // 2, 2)
            self.draw_letter("M", r.center)
        elif et == "mustard":
            pygame.draw.circle(self.screen, YELLOW, r.center, r.w // 2)
            self.draw_letter("G", r.center)
        elif et == "cola":
            pygame.draw.circle(self.screen, BLUE, r.center, r.w // 2)
            self.draw_letter("C", r.center)
        elif et == "olive":
            pygame.draw.circle(self.screen, GREEN, r.center, r.w // 2)
            self.draw_letter("+", r.center)

        pygame.draw.rect(self.screen, (30, 30, 45), r, 2, border_radius=8)

    def draw_letter(self, letter: str, pos):
        txt = self.small_font.render(letter, True, (30, 30, 30))
        rect = txt.get_rect(center=pos)
        self.screen.blit(txt, rect)

    def draw_hud(self):
        if not self.player:
            return
        p = self.player

        pygame.draw.rect(self.screen, (255, 255, 255, 180), (16, 16, 430, 110), border_radius=12)
        hud1 = self.font.render(f"Дистанция: {int(p.distance)} м", True, TEXT)
        hud2 = self.font.render(f"Монеты: {p.coins}", True, TEXT)
        hud3 = self.font.render(f"Сочность: {p.hp}/{p.max_hp}", True, TEXT)

        self.screen.blit(hud1, (28, 24))
        self.screen.blit(hud2, (28, 56))
        self.screen.blit(hud3, (28, 88))

        tags = []
        if p.speed_boost_timer > 0:
            tags.append(("Кетчуп x2", ORANGE))
        if p.invuln_timer > 0:
            tags.append(("Майонез: щит", (230, 230, 230)))
        if p.magnet_timer > 0:
            tags.append(("Горчица: магнит", YELLOW))
        if p.instant_boost_timer > 0:
            tags.append(("Кола: рывок", BLUE))

        x = 480
        for text, color in tags:
            s = self.small_font.render(text, True, (20, 20, 20))
            pad = 12
            w = s.get_width() + pad * 2
            pygame.draw.rect(self.screen, color, (x, 20, w, 30), border_radius=14)
            self.screen.blit(s, (x + pad, 26))
            x += w + 8

    def draw_menu(self):
        self.draw_background(pygame.time.get_ticks() / 1000)

        title = self.big_font.render("Забег Сосисек: Побег из Супермаркета", True, TEXT)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 42))

        subtitle = self.font.render("Выбери сосиску (1-3), ENTER — старт", True, TEXT)
        self.screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 108))

        for i, s in enumerate(SAUSAGE_TYPES):
            x = 180 + i * 330
            y = 200
            card = pygame.Rect(x, y, 280, 220)
            color = (255, 250, 230) if i == self.selected_sausage else (245, 245, 245)
            pygame.draw.rect(self.screen, color, card, border_radius=16)
            pygame.draw.rect(self.screen, (120, 120, 140), card, 2, border_radius=16)

            pygame.draw.ellipse(self.screen, s.color, (x + 70, y + 70, 140, 50))
            name = self.font.render(f"{i+1}. {s.name}", True, TEXT)
            abil = self.small_font.render(s.ability, True, (70, 70, 90))
            self.screen.blit(name, (x + 20, y + 14))
            self.screen.blit(abil, (x + 20, y + 160))

        # upgrades
        up = self.save["upgrades"]
        money = self.save["money"]
        best = self.save["best_distance"]
        info = [
            f"Бюджет: {money} монет",
            f"Рекорд: {best} м",
            f"H: Жизни ({up['hp']}/5), цена {30 + up['hp'] * 35}",
            f"S: Скорость ({up['speed']}/5), цена {30 + up['speed'] * 35}",
            f"C: Бонус монет ({up['coin_bonus']}/5), цена {30 + up['coin_bonus'] * 35}",
            "Управление: W/S (или ←/→) смена полосы, ↑ прыжок, ↓ подкат, свайпы тоже работают",
        ]

        panel = pygame.Rect(120, 470, WIDTH - 240, 200)
        pygame.draw.rect(self.screen, (252, 253, 255), panel, border_radius=12)
        pygame.draw.rect(self.screen, (185, 190, 210), panel, 2, border_radius=12)

        for i, row in enumerate(info):
            t = self.small_font.render(row, True, TEXT)
            self.screen.blit(t, (140, 492 + i * 28))

    def draw_game_over(self):
        self.draw_background(pygame.time.get_ticks() / 1000)
        if not self.player:
            return

        p = self.player
        lines = [
            "ПОЙМАНЫ! Но побег почти удался.",
            f"Дистанция: {int(p.distance)} м",
            f"Монеты за забег: {p.coins}",
            f"Счет: {p.score}",
            "ENTER — еще один забег, ESC — в меню",
        ]

        box = pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 180, 660, 320)
        pygame.draw.rect(self.screen, (255, 255, 255), box, border_radius=18)
        pygame.draw.rect(self.screen, (160, 160, 180), box, 3, border_radius=18)

        for i, line in enumerate(lines):
            font = self.big_font if i == 0 else self.font
            txt = font.render(line, True, TEXT)
            self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, box.y + 36 + i * 56))

    def draw_running(self):
        self.draw_background(pygame.time.get_ticks() / 1000)
        for ent in sorted(self.entities, key=lambda e: e.y):
            self.draw_entity(ent)
        self.draw_player()
        self.draw_hud()

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()

            if self.state == "running":
                self.update_running(dt)
                self.draw_running()
            elif self.state == "menu":
                self.draw_menu()
            elif self.state == "game_over":
                self.draw_game_over()

            pygame.display.flip()


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
