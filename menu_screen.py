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

    def buy_upgrade(self, name: str):
        lvl = self.save["upgrades"][name]
        cost = 30 + lvl * 35
        if self.save["money"] >= cost and lvl < 5:
            self.save["money"] -= cost
            self.save["upgrades"][name] += 1
            save_progress(self.save)

    def handle_event(self, event: pygame.event.Event):
        start_run = False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.selected_sausage = event.key - pygame.K_1
            if event.key == pygame.K_RETURN:
                start_run = True
            if event.key == pygame.K_h:
                self.buy_upgrade("hp")
            if event.key == pygame.K_s:
                self.buy_upgrade("speed")
            if event.key == pygame.K_c:
                self.buy_upgrade("coin_bonus")
        return start_run

    def draw(self, t: float):
        draw_background(self.screen, t)

        title = self.big_font.render("Забег Сосисек: Побег из Супермаркета", True, TEXT)
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 42))

        subtitle = self.font.render("Выбери сосиску (1-3), ENTER — старт", True, TEXT)
        self.screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 108))

        for i, sausage in enumerate(SAUSAGE_TYPES):
            x = 180 + i * 330
            y = 200
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
            "Управление: W/S (или ←/→), ↑ прыжок, ↓ подкат, свайпы поддерживаются",
        ]

        panel = pygame.Rect(120, 470, WIDTH - 240, 200)
        pygame.draw.rect(self.screen, (252, 253, 255), panel, border_radius=12)
        pygame.draw.rect(self.screen, (185, 190, 210), panel, 2, border_radius=12)

        for i, row in enumerate(info):
            text = self.small_font.render(row, True, TEXT)
            self.screen.blit(text, (140, 492 + i * 28))
