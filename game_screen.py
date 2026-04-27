import math
import os
import random
from pathlib import Path
from datetime import datetime, timezone

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
    draw_glass_panel,
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
        self.intro_timer = 0.0
        self.recent_hits: list[float] = []
        self.chaser_timer = 0.0
        self.chaser_x = -260.0
        self.chaser_progress = 0.0
        self.chaser_cooldown = 0.0
        self.player_name = "Игрок"
        self.sausage_sprites = self.load_sausage_sprites()

    def cleanup_sprite_frame(self, frame: pygame.Surface) -> pygame.Surface:
        cleaned = frame.convert_alpha()
        w, h = cleaned.get_size()
        for y in range(h):
            for x in range(w):
                r, g, b, a = cleaned.get_at((x, y))
                if a == 0:
                    continue
                if r > 226 and g > 226 and b > 226 and max(r, g, b) - min(r, g, b) < 22:
                    cleaned.set_at((x, y), (r, g, b, 0))
        bounds = cleaned.get_bounding_rect(min_alpha=1)
        if bounds.w > 0 and bounds.h > 0:
            cleaned = cleaned.subsurface(bounds).copy()
        return cleaned

    def extract_frames_from_sheet(self, sheet: pygame.Surface, expected_frames: int = 6) -> list[pygame.Surface]:
        cleaned_sheet = self.cleanup_sprite_frame(sheet)
        w, h = cleaned_sheet.get_size()
        active_columns: list[bool] = []
        for x in range(w):
            has_opaque = False
            for y in range(h):
                if cleaned_sheet.get_at((x, y))[3] > 0:
                    has_opaque = True
                    break
            active_columns.append(has_opaque)

        segments: list[tuple[int, int]] = []
        start = None
        for x, active in enumerate(active_columns):
            if active and start is None:
                start = x
            elif not active and start is not None:
                if x - start >= 4:
                    segments.append((start, x))
                start = None
        if start is not None and w - start >= 4:
            segments.append((start, w))

        frames: list[pygame.Surface] = []
        if len(segments) >= expected_frames:
            segments = segments[:expected_frames]
            for sx, ex in segments:
                part = pygame.Surface((ex - sx, h), pygame.SRCALPHA)
                part.blit(cleaned_sheet, (0, 0), pygame.Rect(sx, 0, ex - sx, h))
                frames.append(self.cleanup_sprite_frame(part))
            return frames

        frame_w = max(1, w // expected_frames)
        for i in range(expected_frames):
            left = i * frame_w
            right = w if i == expected_frames - 1 else min(w, (i + 1) * frame_w)
            part = pygame.Surface((right - left, h), pygame.SRCALPHA)
            part.blit(cleaned_sheet, (0, 0), pygame.Rect(left, 0, right - left, h))
            frames.append(self.cleanup_sprite_frame(part))
        return frames

    def load_sausage_sprites(self) -> dict[str, list[pygame.Surface]]:
        sprite_map: dict[str, list[pygame.Surface]] = {}
        asset_roots = {
            "Классическая": ("classic", "klass", "класс", "3"),
            "Охотничья": ("hunter", "hunt", "охот", "2"),
            "Баварская": ("bavarian", "bavar", "бавар", "1"),
        }
        fallback_order = ["Баварская", "Охотничья", "Классическая"]
        generic_sprite_sheets: list[str] = []
        if os.path.isdir("assets"):
            for path in Path("assets").glob("*.png"):
                lower = path.stem.lower()
                if any(token in lower for token in ("bg", "background", "store", "shelf", "фон")):
                    continue
                try:
                    img = pygame.image.load(str(path))
                except pygame.error:
                    continue
                w, h = img.get_size()
                if h <= 420 and w >= h * 4.5:
                    generic_sprite_sheets.append(str(path))
        generic_sprite_sheets.sort()

        for name, aliases in asset_roots.items():
            try:
                frames: list[pygame.Surface] = []
                folder_candidates = [
                    f"assets/sausage_{aliases[0]}",
                    f"assets/{aliases[0]}",
                    f"assets/{aliases[-1]}",
                ]
                sheet_candidates = [
                    f"assets/sausage_{aliases[0]}.png",
                    f"assets/{aliases[0]}.png",
                    f"assets/{aliases[-1]}.png",
                ]

                for path in Path("assets").glob("*.png"):
                    lower = path.stem.lower()
                    if any(alias in lower for alias in aliases):
                        sheet_candidates.insert(0, str(path))

                if name in fallback_order:
                    idx = fallback_order.index(name)
                    if idx < len(generic_sprite_sheets):
                        sheet_candidates.append(generic_sprite_sheets[idx])
                for path in Path("assets").glob("*"):
                    if path.is_dir():
                        lower = path.name.lower()
                        if any(alias in lower for alias in aliases):
                            folder_candidates.insert(0, str(path))

                folder_path = next((p for p in folder_candidates if os.path.isdir(p)), None)
                sheet_path = next((p for p in sheet_candidates if os.path.exists(p)), None)
                if folder_path:
                    for i in range(1, 7):
                        frame_path = os.path.join(folder_path, f"{i}.png")
                        if os.path.exists(frame_path):
                            loaded = pygame.image.load(frame_path).convert_alpha()
                            frames.append(self.cleanup_sprite_frame(loaded))

                if len(frames) == 6:
                    sprite_map[name] = frames
                    continue

                if not sheet_path:
                    continue
                sheet = pygame.image.load(sheet_path).convert_alpha()
                if sheet.get_height() > 420:
                    continue
                frames = self.extract_frames_from_sheet(sheet, expected_frames=6)
                sprite_map[name] = frames
            except pygame.error:
                continue
        return sprite_map

    def start_run(self, sausage_index: int, player_name: str = "Игрок"):
        sausage = SAUSAGE_TYPES[sausage_index]
        self.player = Player(sausage, extra_life=self.save["upgrades"]["hp"])
        self.entities = []
        self.spawn_timer = 1.2
        self.powerup_timer = 3.0
        self.world_speed = self.base_speed + self.save["upgrades"]["speed"] * 28
        self.difficulty = 1.0
        self.state = "running"
        self.intro_timer = 3.5
        self.recent_hits = []
        self.chaser_timer = 0.0
        self.chaser_x = -260.0
        self.chaser_progress = 0.0
        self.chaser_cooldown = 0.0
        self.player_name = player_name.strip() or "Игрок"

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
        if ent.etype == "hanging_sign" and p.sliding:
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
            self.register_hit()
            if ent in self.entities:
                self.entities.remove(ent)
            if p.hp <= 0:
                self.end_run()

    def register_hit(self):
        now = pygame.time.get_ticks() / 1000.0
        self.recent_hits = [t for t in self.recent_hits if now - t <= 3.0]
        self.recent_hits.append(now)
        if len(self.recent_hits) >= 2:
            if self.chaser_timer <= 0:
                self.chaser_x = -260.0
                self.chaser_progress = 0.0
            self.chaser_timer = max(self.chaser_timer, 3.2)

    def end_run(self):
        if not self.player:
            return
        money_gain = self.player.coins + int(self.player.distance // 120)
        self.save["money"] += money_gain
        self.save["best_distance"] = max(self.save["best_distance"], int(self.player.distance))
        board = self.save.setdefault("leaderboard", [])
        board.append(
            {
                "name": self.player_name,
                "score": self.player.score,
            }
        )
        board.sort(key=lambda row: row.get("score", 0), reverse=True)
        self.save["leaderboard"] = board[:7]
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
        self.intro_timer = max(0.0, self.intro_timer - dt)
        self.chaser_timer = max(0.0, self.chaser_timer - dt)
        self.chaser_cooldown = max(0.0, self.chaser_cooldown - dt)
        if self.chaser_timer > 0:
            self.chaser_progress = min(1.0, self.chaser_progress + dt * 1.6)
            target = p.x - 160 + math.sin(pygame.time.get_ticks() * 0.006) * 8
            eased = 1.0 - (1.0 - self.chaser_progress) ** 3
            desired_x = -220 + (target + 220) * eased
            self.chaser_x += (desired_x - self.chaser_x) * min(1.0, dt * 7.5)
            self.chaser_cooldown = 0.8
        elif self.chaser_cooldown > 0 or self.chaser_x > -300:
            retreat_target = -320
            self.chaser_x += (retreat_target - self.chaser_x) * min(1.0, dt * 3.2)

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
            self.draw_chaser()
            self.draw_hud()
            if self.intro_timer > 0:
                self.draw_intro_leaderboard()
        else:
            self.draw_game_over()

    def draw_chaser(self):
        if (self.chaser_timer <= 0 and self.chaser_cooldown <= 0 and self.chaser_x <= -305) or not self.player:
            return
        lane_y = LANES_Y[self.player.target_lane]
        x = int(self.chaser_x)
        y = int(lane_y - 90)

        sausage_rect = pygame.Rect(x + 62, y + 50, 46, 20)
        pygame.draw.ellipse(self.screen, (215, 95, 72), sausage_rect)
        pygame.draw.ellipse(self.screen, (255, 230, 190), sausage_rect.inflate(-18, -9))

        pygame.draw.circle(self.screen, (255, 218, 180), (x + 38, y + 20), 15)
        pygame.draw.rect(self.screen, (66, 120, 220), (x + 18, y + 36, 42, 44), border_radius=10)
        leg_phase = math.sin(pygame.time.get_ticks() * 0.02)
        pygame.draw.line(self.screen, (40, 50, 70), (x + 30, y + 78), (x + 22, y + 98 + int(leg_phase * 4)), 5)
        pygame.draw.line(self.screen, (40, 50, 70), (x + 48, y + 78), (x + 58, y + 98 - int(leg_phase * 4)), 5)
        pygame.draw.line(self.screen, (255, 218, 180), (x + 54, y + 44), (x + 74, y + 58), 5)
        pygame.draw.line(self.screen, (255, 218, 180), (x + 52, y + 48), (x + 70, y + 64), 4)
        text = self.small_font.render("Отдай сосиску!", True, (40, 40, 40))
        self.screen.blit(text, (x - 8, y - 24))

    def draw_intro_leaderboard(self):
        panel = pygame.Rect(WIDTH // 2 - 260, 94, 520, 264)
        draw_glass_panel(self.screen, panel, fill=(255, 255, 255, 228), border=(170, 170, 190), radius=16)

        title = self.font.render("Таблица лидеров перед забегом", True, TEXT)
        self.screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 14))
        rows = self.save.get("leaderboard", [])[:5]
        if not rows:
            hint = self.small_font.render("Пока пусто — этот забег задаст планку!", True, (80, 80, 105))
            self.screen.blit(hint, (panel.centerx - hint.get_width() // 2, panel.y + 88))
        else:
            for i, row in enumerate(rows):
                line = f"{i + 1}. {row.get('name', 'Игрок')} — счёт {row.get('score', 0)}"
                txt = self.small_font.render(line, True, TEXT)
                self.screen.blit(txt, (panel.x + 26, panel.y + 68 + i * 34))

        countdown = self.small_font.render(f"Старт через: {self.intro_timer:.1f}с", True, (90, 90, 120))
        self.screen.blit(countdown, (panel.centerx - countdown.get_width() // 2, panel.bottom - 34))

    def draw_player(self):
        if not self.player:
            return
        p = self.player
        body_rect = p.rect
        if p.invuln_timer > 0:
            self.invuln_flash = not self.invuln_flash
            if not self.invuln_flash:
                return
        run_t = pygame.time.get_ticks() * 0.018
        bob = int(math.sin(run_t) * 3)
        body_rect = body_rect.move(0, bob)

        frames = self.sausage_sprites.get(p.sausage.name, [])
        if frames:
            frame = frames[int(pygame.time.get_ticks() * 0.015) % len(frames)]
            scaled = pygame.transform.smoothscale(frame, (body_rect.w + 24, body_rect.h + 30))
            self.screen.blit(scaled, (body_rect.x - 12, body_rect.y - 18))
            pygame.draw.ellipse(self.screen, (120, 120, 145), (body_rect.centerx - 28, LANES_Y[p.target_lane] - 4, 56, 12))
            return

        pygame.draw.ellipse(self.screen, (96, 46, 40), body_rect.inflate(8, 8))
        pygame.draw.ellipse(self.screen, p.sausage.color, body_rect)
        if p.sausage.name == "Охотничья":
            pygame.draw.ellipse(self.screen, (190, 35, 42), body_rect.inflate(-18, -14), 3)
        if p.sausage.name == "Баварская":
            for i in range(4):
                sx = body_rect.x + 20 + i * 15
                pygame.draw.line(self.screen, (170, 62, 30), (sx, body_rect.y + 10), (sx + 8, body_rect.bottom - 8), 3)
        pygame.draw.ellipse(self.screen, (250, 220, 180), body_rect.inflate(-30, -18), 3)
        pygame.draw.ellipse(self.screen, (255, 245, 225), (body_rect.x + 8, body_rect.y + 6, 42, 12))

        eye_y = body_rect.y + 14
        pygame.draw.circle(self.screen, WHITE, (body_rect.x + 26, eye_y), 6)
        pygame.draw.circle(self.screen, WHITE, (body_rect.x + 52, eye_y), 6)
        pygame.draw.circle(self.screen, (0, 0, 0), (body_rect.x + 26, eye_y), 2)
        pygame.draw.circle(self.screen, (0, 0, 0), (body_rect.x + 52, eye_y), 2)
        pygame.draw.arc(self.screen, (70, 20, 20), (body_rect.x + 26, body_rect.y + 16, 28, 14), math.pi * 0.1, math.pi * 0.9, 2)
        leg_a = int(math.sin(run_t) * 9)
        leg_b = int(math.sin(run_t + math.pi) * 9)
        pygame.draw.line(self.screen, (72, 28, 22), (body_rect.x + 26, body_rect.bottom - 2), (body_rect.x + 14 + leg_a, body_rect.bottom + 14), 5)
        pygame.draw.line(self.screen, (72, 28, 22), (body_rect.x + 44, body_rect.bottom - 2), (body_rect.x + 58 + leg_b, body_rect.bottom + 14), 5)
        pygame.draw.line(self.screen, (72, 28, 22), (body_rect.x + 62, body_rect.bottom - 2), (body_rect.x + 74 - leg_a, body_rect.bottom + 14), 5)
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
        hud_rect = pygame.Rect(16, 16, 430, 110)
        draw_glass_panel(self.screen, hud_rect, fill=(255, 255, 255, 208), border=(170, 184, 220), radius=12)
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
            tag_rect = pygame.Rect(x, 20, w, 30)
            draw_glass_panel(self.screen, tag_rect, fill=(*color, 230), border=(96, 108, 138), radius=14)
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
        draw_glass_panel(self.screen, box, fill=(255, 255, 255, 232), border=(160, 160, 180), radius=18)
        for i, line in enumerate(lines):
            font = self.big_font if i == 0 else self.font
            txt = font.render(line, True, TEXT)
            self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, box.y + 36 + i * 56))
