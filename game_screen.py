import math
import random

import pygame

from common import (
    BLUE,
    ENEMY_TYPES,
    GREEN,
    HEIGHT,
    LANES_Y,
    OBSTACLE_TYPES,
    ORANGE,
    POWERUP_TYPES,
    PURPLE,
    RED,
    SAUSAGE_TYPES,
    TEXT,
    WHITE,
    WIDTH,
    YELLOW,
    Player,
    draw_background,
    random_obstacle_or_enemy,
    random_powerup,
    save_progress,
)


class GameScreen:
    def __init__(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font], save_data: dict):
        self.screen = screen
        self.font = fonts["font"]
        self.big_font = fonts["big"]
        self.small_font = fonts["small"]
        self.save = save_data

        self.player = None
        self.entities = []
        self.base_speed = 360.0
        self.world_speed = self.base_speed
        self.difficulty = 1.0
        self.spawn_timer = 1.2
        self.powerup_timer = 3.0
        self.invuln_flash = False
        self.state = "running"

    def start_run(self, sausage_index: int):
        sausage = SAUSAGE_TYPES[sausage_index]
        self.player = Player(sausage, extra_life=self.save["upgrades"]["hp"])
        self.entities = []
        self.spawn_timer = 1.2
        self.powerup_timer = 3.0
        self.world_speed = self.base_speed + self.save["upgrades"]["speed"] * 28
        self.difficulty = 1.0
        self.state = "running"

    def handle_swipe(self, dx: float, dy: float):
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

    def handle_keydown(self, key: int):
        if self.state == "running" and self.player:
            if key in (pygame.K_w, pygame.K_RIGHT):
                self.player.move_lane(+1)
            elif key in (pygame.K_s, pygame.K_LEFT):
                self.player.move_lane(-1)
            elif key in (pygame.K_UP, pygame.K_SPACE):
                self.player.jump()
            elif key == pygame.K_DOWN:
                self.player.slide()
            elif key == pygame.K_ESCAPE:
                return "menu"
        elif self.state == "game_over":
            if key == pygame.K_RETURN:
                return "restart"
            if key == pygame.K_ESCAPE:
                return "menu"
        return None

    def collide_with_player(self, ent):
        if not self.player:
            return
        p = self.player
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
        save_progress(self.save)
        self.state = "game_over"

    def update(self, dt: float):
        if self.state != "running" or not self.player:
            return
        p = self.player
        self.difficulty += dt * 0.03
        speed_bonus = 120 if p.speed_boost_timer > 0 else 0
        if p.instant_boost_timer > 0:
            speed_bonus += 280
        self.world_speed = self.base_speed + self.save["upgrades"]["speed"] * 28 + self.difficulty * 38 + speed_bonus

        p.update(dt)
        p.distance += self.world_speed * dt * 0.25
        p.score = int(p.distance) + p.coins * 10

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.entities.append(random_obstacle_or_enemy())
            self.spawn_timer = max(0.35, 1.2 - self.difficulty * 0.07)

        self.powerup_timer -= dt
        if self.powerup_timer <= 0:
            self.entities.append(random_powerup())
            self.powerup_timer = random.uniform(2.2, 4.5)

        for ent in list(self.entities):
            ent.update(dt, self.world_speed)
            if p.magnet_timer > 0 and ent.etype in POWERUP_TYPES:
                ent.y += (p.y - 20 - ent.y) * min(1.0, 6 * dt)
            if ent.x < p.x and not ent.passed and ent.etype not in POWERUP_TYPES:
                ent.passed = True
                p.coins += 1 + self.save["upgrades"]["coin_bonus"]
            self.collide_with_player(ent)
            if ent.offscreen() and ent in self.entities:
                self.entities.remove(ent)

    def draw(self, t: float):
        draw_background(self.screen, t, self.player.target_lane if self.player and self.state == "running" else None)
        if self.state == "running":
            for ent in sorted(self.entities, key=lambda e: e.y):
                self.draw_entity(ent)
            self.draw_player()
            self.draw_hud()
        else:
            self.draw_game_over()

    def draw_player(self):
        if not self.player:
            return
        p = self.player
        body_rect = p.rect
        if p.invuln_timer > 0:
            self.invuln_flash = not self.invuln_flash
            if not self.invuln_flash:
                return

        pygame.draw.ellipse(self.screen, (96, 46, 40), body_rect.inflate(8, 8))
        pygame.draw.ellipse(self.screen, p.sausage.color, body_rect)
        pygame.draw.ellipse(self.screen, (250, 220, 180), body_rect.inflate(-30, -18), 3)
        pygame.draw.ellipse(self.screen, (255, 245, 225), (body_rect.x + 8, body_rect.y + 6, 42, 12))

        eye_y = body_rect.y + 14
        pygame.draw.circle(self.screen, WHITE, (body_rect.x + 26, eye_y), 6)
        pygame.draw.circle(self.screen, WHITE, (body_rect.x + 52, eye_y), 6)
        pygame.draw.circle(self.screen, (0, 0, 0), (body_rect.x + 26, eye_y), 2)
        pygame.draw.circle(self.screen, (0, 0, 0), (body_rect.x + 52, eye_y), 2)
        pygame.draw.arc(self.screen, (70, 20, 20), (body_rect.x + 26, body_rect.y + 16, 28, 14), math.pi * 0.1, math.pi * 0.9, 2)
        pygame.draw.ellipse(self.screen, (120, 120, 145), (body_rect.centerx - 28, LANES_Y[p.target_lane] - 4, 56, 12))

    def draw_sauce_packet(self, rect: pygame.Rect, base_color, accent_color, label: str):
        pygame.draw.polygon(
            self.screen,
            base_color,
            [(rect.x + 4, rect.y), (rect.right - 4, rect.y), (rect.right, rect.bottom - 6), (rect.x, rect.bottom - 6)],
        )
        pygame.draw.rect(self.screen, accent_color, (rect.x + 6, rect.y + 8, rect.w - 12, rect.h - 18), border_radius=7)
        pygame.draw.line(self.screen, WHITE, (rect.x + 10, rect.y + 4), (rect.right - 10, rect.y + 4), 2)
        pygame.draw.line(self.screen, (30, 30, 40), (rect.x + 8, rect.bottom - 5), (rect.right - 8, rect.bottom - 5), 1)
        txt = self.small_font.render(label, True, (25, 25, 30))
        self.screen.blit(txt, txt.get_rect(center=(rect.centerx, rect.centery + 1)))

    def draw_entity(self, ent):
        r = ent.rect
        et = ent.etype

        if et == "cart":
            pygame.draw.rect(self.screen, (122, 138, 165), r, border_radius=10)
            pygame.draw.rect(self.screen, (198, 214, 240), r.inflate(-10, -22), border_radius=8)
            for col in range(3):
                x = r.x + 14 + col * 24
                pygame.draw.line(self.screen, (160, 180, 205), (x, r.y + 12), (x, r.bottom - 26), 2)
            pygame.draw.line(self.screen, (95, 110, 130), (r.x + 6, r.y + 14), (r.right - 6, r.y + 14), 3)
            pygame.draw.circle(self.screen, (44, 44, 54), (r.x + 18, r.bottom), 8)
            pygame.draw.circle(self.screen, (44, 44, 54), (r.right - 18, r.bottom), 8)
        elif et == "mop":
            pygame.draw.rect(self.screen, (182, 138, 84), (r.centerx - 4, r.y, 8, r.h - 14), border_radius=3)
            pygame.draw.rect(self.screen, (80, 165, 255), (r.centerx - 20, r.bottom - 16, 40, 12), border_radius=6)
            for i in range(5):
                pygame.draw.line(self.screen, (205, 235, 255), (r.centerx - 18 + i * 8, r.bottom - 3), (r.centerx - 14 + i * 8, r.bottom + 8), 2)
        elif et == "shelf":
            pygame.draw.rect(self.screen, (190, 120, 65), r, border_radius=6)
            for i, c in enumerate([(240, 220, 90), (95, 210, 140), (255, 130, 130)]):
                pygame.draw.rect(self.screen, c, (r.x + 6, r.y + 14 + i * 24, r.w - 12, 12), border_radius=4)
                for j in range(4):
                    pygame.draw.rect(self.screen, (250 - i * 10, 250 - j * 12, 235), (r.x + 9 + j * 20, r.y + 16 + i * 24, 12, 8), border_radius=2)
        elif et == "kid":
            pygame.draw.circle(self.screen, (255, 220, 160), (r.centerx, r.y + 20), 16)
            pygame.draw.rect(self.screen, (95, 145, 255), (r.x + 12, r.y + 34, r.w - 24, r.h - 34), border_radius=10)
            pygame.draw.circle(self.screen, (20, 20, 25), (r.centerx - 6, r.y + 18), 2)
            pygame.draw.circle(self.screen, (20, 20, 25), (r.centerx + 6, r.y + 18), 2)
            pygame.draw.arc(self.screen, (120, 40, 40), (r.centerx - 8, r.y + 20, 16, 10), 0.3, 2.8, 2)
        elif et == "conveyor":
            pygame.draw.rect(self.screen, (90, 90, 105), r, border_radius=8)
            for i in range(6):
                pygame.draw.line(self.screen, (155, 155, 175), (r.x + 8 + i * 18, r.y + 6), (r.x + 18 + i * 18, r.bottom - 6), 2)
            pygame.draw.circle(self.screen, (70, 70, 80), (r.x + 8, r.bottom), 5)
            pygame.draw.circle(self.screen, (70, 70, 80), (r.right - 8, r.bottom), 5)
        elif et == "freezer":
            pygame.draw.rect(self.screen, (180, 235, 255), r, border_radius=8)
            pygame.draw.rect(self.screen, WHITE, r, 2, border_radius=8)
            pygame.draw.rect(self.screen, (140, 198, 240), (r.x + 8, r.y + 14, r.w - 16, r.h - 22), border_radius=6)
            pygame.draw.line(self.screen, WHITE, (r.x + 14, r.y + 20), (r.right - 14, r.bottom - 14), 2)
        elif et == "box":
            pygame.draw.rect(self.screen, (214, 156, 88), r, border_radius=6)
            pygame.draw.rect(self.screen, (190, 134, 66), r.inflate(-4, -4), 2, border_radius=6)
            pygame.draw.line(self.screen, (148, 92, 36), (r.centerx, r.y + 2), (r.centerx, r.bottom - 2), 2)
            pygame.draw.line(self.screen, (148, 92, 36), (r.x + 4, r.centery), (r.right - 4, r.centery), 2)
        elif et == "long_box":
            pygame.draw.rect(self.screen, (220, 162, 94), r, border_radius=6)
            seg = r.w // 3
            for i in range(3):
                sx = r.x + i * seg
                pygame.draw.rect(self.screen, (198, 138, 70), (sx + 2, r.y + 2, seg - 4, r.h - 4), 2, border_radius=4)
        elif et == "hanging_sign":
            pygame.draw.rect(self.screen, (255, 226, 98), r, border_radius=8)
            pygame.draw.rect(self.screen, (190, 124, 40), r, 3, border_radius=8)
            pygame.draw.line(self.screen, (150, 150, 165), (r.x + 16, r.y - 14), (r.x + 16, r.y), 3)
            pygame.draw.line(self.screen, (150, 150, 165), (r.right - 16, r.y - 14), (r.right - 16, r.y), 3)
            low = self.small_font.render("LOW", True, (70, 35, 15))
            self.screen.blit(low, low.get_rect(center=r.center))
        elif et == "butcher":
            pygame.draw.rect(self.screen, (255, 255, 255), r, border_radius=10)
            pygame.draw.circle(self.screen, (255, 215, 170), (r.centerx, r.y + 16), 12)
            pygame.draw.rect(self.screen, (220, 36, 64), (r.x + 12, r.y + 40, r.w - 24, 10), border_radius=5)
            pygame.draw.circle(self.screen, (80, 80, 80), (r.right - 11, r.y + 25), 9, 2)
        elif et == "scanner":
            pygame.draw.rect(self.screen, PURPLE, r, border_radius=8)
            pulse = int(120 + 100 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.03)))
            pygame.draw.rect(self.screen, (255, pulse, pulse), (r.x + 6, r.y + 25, r.w - 12, 8), border_radius=3)
        elif et == "robot":
            pygame.draw.rect(self.screen, (155, 175, 205), r, border_radius=10)
            pygame.draw.circle(self.screen, (90, 120, 255), (r.centerx - 12, r.y + 18), 5)
            pygame.draw.circle(self.screen, (90, 120, 255), (r.centerx + 12, r.y + 18), 5)
            pygame.draw.rect(self.screen, (120, 150, 185), (r.x + 12, r.bottom - 14, r.w - 24, 8), border_radius=4)
        elif et == "ketchup":
            self.draw_sauce_packet(r, (228, 84, 70), (245, 203, 190), "K")
        elif et == "mayo":
            self.draw_sauce_packet(r, (246, 244, 232), (225, 222, 210), "M")
        elif et == "mustard":
            self.draw_sauce_packet(r, (246, 210, 82), (252, 238, 168), "G")
        elif et == "cola":
            self.draw_sauce_packet(r, (88, 153, 255), (198, 222, 255), "C")
        elif et == "olive":
            self.draw_sauce_packet(r, (96, 198, 118), (190, 237, 196), "+")

        pygame.draw.rect(self.screen, (30, 30, 45), r, 2, border_radius=8)

    def draw_hud(self):
        if not self.player:
            return
        p = self.player
        pygame.draw.rect(self.screen, (255, 255, 255, 180), (16, 16, 430, 110), border_radius=12)
        self.screen.blit(self.font.render(f"Дистанция: {int(p.distance)} м", True, TEXT), (28, 24))
        self.screen.blit(self.font.render(f"Монеты: {p.coins}", True, TEXT), (28, 56))
        self.screen.blit(self.font.render(f"Сочность: {p.hp}/{p.max_hp}", True, TEXT), (28, 88))

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
            w = s.get_width() + 24
            pygame.draw.rect(self.screen, color, (x, 20, w, 30), border_radius=14)
            self.screen.blit(s, (x + 12, 26))
            x += w + 8

    def draw_game_over(self):
        if not self.player:
            return
        lines = [
            "ПОЙМАНЫ! Но побег почти удался.",
            f"Дистанция: {int(self.player.distance)} м",
            f"Монеты за забег: {self.player.coins}",
            f"Счет: {self.player.score}",
            "ENTER — еще один забег, ESC — в меню",
        ]
        box = pygame.Rect(WIDTH // 2 - 330, HEIGHT // 2 - 180, 660, 320)
        pygame.draw.rect(self.screen, (255, 255, 255), box, border_radius=18)
        pygame.draw.rect(self.screen, (160, 160, 180), box, 3, border_radius=18)
        for i, line in enumerate(lines):
            font = self.big_font if i == 0 else self.font
            txt = font.render(line, True, TEXT)
            self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, box.y + 36 + i * 56))
