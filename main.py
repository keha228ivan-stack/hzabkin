import sys

import pygame

from common import FPS, WIDTH, HEIGHT, load_save
from game_screen import GameScreen
from menu_screen import MenuScreen


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Забег Сосисек: Побег из Супермаркета")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = {
            "font": pygame.font.SysFont("arial", 28),
            "big": pygame.font.SysFont("arial", 52, bold=True),
            "small": pygame.font.SysFont("arial", 20),
        }

        save_data = load_save()
        self.menu = MenuScreen(self.screen, self.fonts, save_data)
        self.game = GameScreen(self.screen, self.fonts, save_data)

        self.state = "menu"
        self.touch_start = None

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.touch_start = pygame.Vector2(event.pos)
                if event.type == pygame.MOUSEBUTTONUP and self.touch_start is not None:
                    end = pygame.Vector2(event.pos)
                    d = end - self.touch_start
                    self.game.handle_swipe(d.x, d.y)
                    self.touch_start = None

                if event.type == pygame.KEYDOWN:
                    if self.state == "menu":
                        action = self.menu.handle_event(event)
                        if action == "start":
                            self.game.start_run(self.menu.selected_sausage, self.menu.player_name)
                            self.state = "running"
                    else:
                        action = self.game.handle_keydown(event.key)
                        if action == "menu":
                            self.state = "menu"
                        elif action == "restart":
                            self.game.start_run(self.menu.selected_sausage, self.menu.player_name)
                            self.state = "running"

            if self.state == "menu":
                self.menu.update(dt)
                self.menu.draw(pygame.time.get_ticks() / 1000)
            else:
                self.game.update(dt)
                self.game.draw(pygame.time.get_ticks() / 1000)
                if self.game.state == "game_over":
                    self.state = "game_over"

            pygame.display.flip()


def main():
    App().run()


if __name__ == "__main__":
    main()
