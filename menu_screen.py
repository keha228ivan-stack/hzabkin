import pygame

from common import HEIGHT, TEXT, WIDTH, SAUSAGE_TYPES, draw_background, save_progress


class MenuScreen:
    def __init__(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font], save_data: dict):
        self.screen = screen
        self.font = fonts["font"]
        self.big_font = fonts["big"]
        self.small_font = fonts["small"]
        self.save = save_data
        self.selected_sausage = 0
        self.player_name = self.save.get("player_name", "")
        self.name_error_timer = 0.0
        self.show_leaderboard = False
        self.name_max_len = 16

    def buy_upgrade(self, name: str):
        lvl = self.save["upgrades"][name]
        cost = 30 + lvl * 35
        if self.save["money"] >= cost and lvl < 5:
            self.save["money"] -= cost
            self.save["upgrades"][name] += 1
            save_progress(self.save)

    def handle_event(self, event: pygame.event.Event):
        action = None
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_l, pygame.K_TAB):
                self.show_leaderboard = not self.show_leaderboard
                return None
            if self.show_leaderboard and event.key == pygame.K_ESCAPE:
                self.show_leaderboard = False
                return None
            if self.show_leaderboard:
                return None

            if event.key in (pygame.K_a, pygame.K_LEFT):
                self.selected_sausage = max(0, self.selected_sausage - 1)
            if event.key in (pygame.K_d, pygame.K_RIGHT):
                self.selected_sausage = min(len(SAUSAGE_TYPES) - 1, self.selected_sausage + 1)
            if event.key == pygame.K_RETURN:
                if self.player_name.strip():
                    self.save["player_name"] = self.player_name.strip()
                    save_progress(self.save)
                    action = "start"
                else:
                    self.name_error_timer = 2.2
            if event.key == pygame.K_h:
                self.buy_upgrade("hp")
            if event.key == pygame.K_s:
                self.buy_upgrade("speed")
            if event.key == pygame.K_c:
                self.buy_upgrade("coin_bonus")
            if event.key == pygame.K_BACKSPACE:
                self.player_name = self.player_name[:-1]
            elif event.unicode and event.unicode.isprintable() and len(self.player_name) < self.name_max_len:
                self.player_name += event.unicode
        return action

    def update(self, dt: float):
        self.name_error_timer = max(0.0, self.name_error_timer - dt)

    def draw(self, t: float):
        draw_background(self.screen, t)
        if self.show_leaderboard:
            self.draw_leaderboard()
            return

        title = self.big_font.render("Забег Сосисек: Побег из Супермаркета", True, TEXT)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 26))

        subtitle = self.font.render("Выбери сосиску (A/D или ←/→), ENTER — старт", True, TEXT)
        self.screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 90))

        name_box = pygame.Rect(WIDTH // 2 - 220, 130, 440, 48)
        pygame.draw.rect(self.screen, (255, 255, 255), name_box, border_radius=10)
        pygame.draw.rect(self.screen, (140, 140, 170), name_box, 2, border_radius=10)
        prompt = self.small_font.render("Имя игрока:", True, (60, 60, 80))
        self.screen.blit(prompt, (name_box.x + 12, name_box.y + 12))
        shown_name = self.player_name
        while shown_name and self.font.size(shown_name)[0] > 260:
            shown_name = shown_name[1:]
        name_text = self.font.render(shown_name if shown_name else "введи имя...", True, TEXT if shown_name else (135, 135, 155))
        self.screen.blit(name_text, (name_box.x + 150, name_box.y + 7))
        if self.name_error_timer > 0:
            warn = self.small_font.render("Сначала представься, бро 😎", True, (200, 50, 60))
            self.screen.blit(warn, (WIDTH // 2 - warn.get_width() // 2, 182))

        for i, sausage in enumerate(SAUSAGE_TYPES):
            x = 180 + i * 330
            y = 190
            card = pygame.Rect(x, y, 280, 220)
            color = (255, 250, 230) if i == self.selected_sausage else (245, 245, 245)
            pygame.draw.rect(self.screen, color, card, border_radius=16)
            pygame.draw.rect(self.screen, (120, 120, 140), card, 2, border_radius=16)

            pygame.draw.ellipse(self.screen, sausage.color, (x + 70, y + 70, 140, 50))
            name = self.font.render(f"{i + 1}. {sausage.name}", True, TEXT)
            ability = self.small_font.render(sausage.ability, True, (70, 70, 90))
            self.screen.blit(name, (x + 20, y + 14))
            self.screen.blit(ability, (x + 20, y + 160))

        up = self.save["upgrades"]
        info = [
            f"Бюджет: {self.save['money']} монет",
            f"Рекорд: {self.save['best_distance']} м",
            f"H: Жизни ({up['hp']}/5), цена {30 + up['hp'] * 35}",
            f"S: Скорость ({up['speed']}/5), цена {30 + up['speed'] * 35}",
            f"C: Бонус монет ({up['coin_bonus']}/5), цена {30 + up['coin_bonus'] * 35}",
            "L или TAB: открыть экран лидерборда",
            "Выбор сосиски: A/D или ←/→",
            "Управление: W/S (или ←/→), ↑ прыжок, ↓ подкат, свайпы поддерживаются",
        ]

        panel = pygame.Rect(130, 488, WIDTH - 260, 200)
        pygame.draw.rect(self.screen, (252, 253, 255), panel, border_radius=12)
        pygame.draw.rect(self.screen, (185, 190, 210), panel, 2, border_radius=12)

        for i, row in enumerate(info):
            text = self.small_font.render(row, True, TEXT)
            self.screen.blit(text, (150, 500 + i * 23))

    def draw_leaderboard(self):
        title = self.big_font.render("ЛИДЕРБОРД", True, TEXT)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 62))
        sub = self.small_font.render("ESC / L / TAB — назад в меню", True, (80, 80, 100))
        self.screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 118))

        panel = pygame.Rect(WIDTH // 2 - 320, 160, 640, 420)
        pygame.draw.rect(self.screen, (255, 255, 255), panel, border_radius=16)
        pygame.draw.rect(self.screen, (170, 170, 190), panel, 2, border_radius=16)

        headers = self.font.render("Топ игроков", True, TEXT)
        self.screen.blit(headers, (panel.centerx - headers.get_width() // 2, panel.y + 20))
        rows = self.save.get("leaderboard", [])[:10]
        if not rows:
            empty = self.small_font.render("Пока пусто. Запусти забег и поставь первый рекорд!", True, (90, 90, 110))
            self.screen.blit(empty, (panel.centerx - empty.get_width() // 2, panel.y + 92))
            return

        for i, row in enumerate(rows):
            place = self.small_font.render(f"{i + 1}.", True, TEXT)
            name = self.small_font.render(row.get("name", "Игрок"), True, TEXT)
            score = self.small_font.render(f"{row.get('score', 0)}", True, TEXT)
            y = panel.y + 84 + i * 30
            self.screen.blit(place, (panel.x + 34, y))
            self.screen.blit(name, (panel.x + 84, y))
            self.screen.blit(score, (panel.right - 110, y))
