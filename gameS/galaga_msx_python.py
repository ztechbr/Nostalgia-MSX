"""Functional Python port/recreation of the uploaded MSX Galaga loader/binaries.

Reverse-engineering facts preserved from the original files:
- MSX BIN load range: 0x9000..0xD020
- stage loader entry: 0xD000
- GALAGA1 copies 0x4000 bytes to 0x4000
- GALAGA2 copies 0x4000 bytes to 0x8000 and jumps through (0x4002)
- assembled game entry: 0x4017
- infinite-lives loader patch 0x9152 maps to assembled address 0x8152

The original game code is Z80/MSX-hardware-specific. This module recreates the
playable behavior in pure Python/Tkinter at the MSX logical resolution 256x192,
without requiring third-party packages.
"""
from __future__ import annotations

import math
import random
import tkinter as tk
from dataclasses import dataclass, field

W, H = 256, 192
SCALE = 3
FPS = 60
DT_MS = 1000 // FPS

# MSX-ish palette, represented with normal RGB strings for Tkinter.
BLACK = "#000000"
WHITE = "#ffffff"
RED = "#d94444"
DARK_RED = "#8d3030"
BLUE = "#4e70d8"
LIGHT_BLUE = "#75b7ff"
GREEN = "#52b84b"
YELLOW = "#e7d84b"
CYAN = "#63d5d8"
MAGENTA = "#c65bc7"
ORANGE = "#e89143"
GRAY = "#aaaaaa"


@dataclass
class Bullet:
    x: float
    y: float
    vy: float
    owner: str
    alive: bool = True


@dataclass
class Enemy:
    x: float
    y: float
    home_x: float
    home_y: float
    kind: str
    hp: int = 1
    alive: bool = True
    diving: bool = False
    dive_t: float = 0.0
    phase: float = 0.0
    fire_cooldown: int = 0

    @property
    def points(self) -> int:
        return {"bee": 50, "butterfly": 80, "boss": 150}.get(self.kind, 50)


@dataclass
class Player:
    x: float = W / 2
    y: float = H - 20
    lives: int = 3
    invulnerable: int = 0
    cooldown: int = 0


class GalagaMSX:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("GALAGA! - MSX Python Port")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            self.root,
            width=W * SCALE,
            height=H * SCALE,
            bg=BLACK,
            highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.scale_factor = SCALE

        self.keys: set[str] = set()
        self.state = "title"
        self.infinite_lives = False
        self.player = Player()
        self.bullets: list[Bullet] = []
        self.enemies: list[Enemy] = []
        self.score = 0
        self.high_score = 0
        self.stage = 1
        self.frame = 0
        self.formation_dir = 1
        self.formation_offset = 0.0
        self.message_timer = 0
        self.rng = random.Random(1987)
        self.stars = [
            (self.rng.randrange(W), self.rng.randrange(H), self.rng.choice((1, 1, 1, 2)))
            for _ in range(52)
        ]

        self.root.bind("<KeyPress>", self.on_key_down)
        self.root.bind("<KeyRelease>", self.on_key_up)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def sx(self, value: float) -> int:
        return int(value * SCALE)

    def rect(self, x1, y1, x2, y2, **kwargs):
        return self.canvas.create_rectangle(
            self.sx(x1), self.sx(y1), self.sx(x2), self.sx(y2), **kwargs
        )

    def line(self, *coords, **kwargs):
        return self.canvas.create_line(*[self.sx(v) for v in coords], **kwargs)

    def poly(self, points, **kwargs):
        flat = []
        for x, y in points:
            flat += [self.sx(x), self.sx(y)]
        return self.canvas.create_polygon(*flat, **kwargs)

    def text(self, x, y, text, size=7, fill=WHITE, anchor="center"):
        return self.canvas.create_text(
            self.sx(x),
            self.sx(y),
            text=text,
            fill=fill,
            anchor=anchor,
            font=("Courier New", max(6, size * SCALE // 2), "bold"),
        )

    def on_key_down(self, event):
        key = event.keysym.lower()
        self.keys.add(key)

        if key == "escape":
            self.root.destroy()
            return

        if self.state == "title":
            if key in ("i",):
                self.infinite_lives = not self.infinite_lives
            elif key in ("return", "space"):
                self.start_game()
        elif self.state == "gameover" and key in ("return", "space"):
            self.state = "title"
        elif self.state == "playing" and key == "p":
            self.state = "paused"
        elif self.state == "paused" and key == "p":
            self.state = "playing"

    def on_key_up(self, event):
        self.keys.discard(event.keysym.lower())

    def start_game(self):
        self.player = Player(lives=3)
        self.score = 0
        self.stage = 1
        self.bullets.clear()
        self.spawn_stage()
        self.state = "playing"
        self.message_timer = 90

    def spawn_stage(self):
        self.enemies.clear()
        rows = [
            ("boss", 2, 78, 42, 100),
            ("butterfly", 6, 53, 56, 30),
            ("butterfly", 6, 53, 69, 30),
            ("bee", 8, 39, 83, 25),
            ("bee", 8, 39, 96, 25),
        ]
        for kind, count, start_x, y, step in rows:
            for i in range(count):
                x = start_x + i * step
                hp = 2 if kind == "boss" else 1
                self.enemies.append(
                    Enemy(x=x, y=y, home_x=x, home_y=y, kind=kind, hp=hp, phase=i * 0.7)
                )
        self.formation_dir = 1
        self.formation_offset = 0.0

    def update(self):
        self.frame += 1
        self.update_stars()
        if self.state != "playing":
            return

        if self.message_timer > 0:
            self.message_timer -= 1

        self.update_player()
        self.update_formation()
        self.update_enemies()
        self.update_bullets()
        self.collisions()

        if not any(e.alive for e in self.enemies):
            self.stage += 1
            self.spawn_stage()
            self.message_timer = 100

    def update_stars(self):
        if self.frame % 2:
            return
        moved = []
        for x, y, speed in self.stars:
            y += speed
            if y >= H:
                y = 0
                x = self.rng.randrange(W)
            moved.append((x, y, speed))
        self.stars = moved

    def update_player(self):
        p = self.player
        speed = 2.0
        if "left" in self.keys or "a" in self.keys:
            p.x -= speed
        if "right" in self.keys or "d" in self.keys:
            p.x += speed
        p.x = max(10, min(W - 10, p.x))

        if p.cooldown > 0:
            p.cooldown -= 1
        if p.invulnerable > 0:
            p.invulnerable -= 1

        if ("space" in self.keys or "control_l" in self.keys or "z" in self.keys) and p.cooldown == 0:
            self.bullets.append(Bullet(p.x, p.y - 7, -4.0, "player"))
            p.cooldown = 12

    def update_formation(self):
        self.formation_offset += 0.18 * self.formation_dir
        if abs(self.formation_offset) > 8:
            self.formation_dir *= -1

    def update_enemies(self):
        alive = [e for e in self.enemies if e.alive]
        dive_probability = min(0.0010 + self.stage * 0.00012, 0.003)

        for e in alive:
            if e.fire_cooldown > 0:
                e.fire_cooldown -= 1

            if not e.diving:
                e.x = e.home_x + self.formation_offset
                e.y = e.home_y + math.sin(self.frame * 0.035 + e.phase) * 1.2
                if self.message_timer == 0 and self.rng.random() < dive_probability:
                    e.diving = True
                    e.dive_t = 0.0
            else:
                e.dive_t += 0.027 + self.stage * 0.0007
                t = e.dive_t
                # Galaga-like looping dive, aimed broadly toward the player's region.
                side = -1 if e.home_x < W / 2 else 1
                e.x = e.home_x + side * math.sin(t * math.pi * 2.2) * 48 + (self.player.x - W / 2) * min(t, 1) * 0.22
                e.y = e.home_y + t * 115 + math.sin(t * math.pi * 2) * 25

                if 0.30 < t < 0.95 and e.fire_cooldown == 0 and self.rng.random() < 0.025:
                    dy = self.player.y - e.y
                    dx = self.player.x - e.x
                    mag = max(1.0, math.hypot(dx, dy))
                    self.bullets.append(Bullet(e.x, e.y + 5, 2.1 * dy / mag, "enemy"))
                    # Add a small horizontal component dynamically.
                    self.bullets[-1].vx = 2.1 * dx / mag
                    e.fire_cooldown = 50

                if e.y > H + 20 or t > 1.55:
                    e.diving = False
                    e.dive_t = 0.0
                    e.x, e.y = e.home_x, e.home_y

    def update_bullets(self):
        for b in self.bullets:
            b.y += b.vy
            b.x += getattr(b, "vx", 0.0)
            if b.y < -8 or b.y > H + 8 or b.x < -8 or b.x > W + 8:
                b.alive = False
        self.bullets = [b for b in self.bullets if b.alive]

    @staticmethod
    def hit(ax, ay, bx, by, rx=7, ry=7):
        return abs(ax - bx) <= rx and abs(ay - by) <= ry

    def collisions(self):
        p = self.player
        for b in self.bullets:
            if not b.alive:
                continue
            if b.owner == "player":
                for e in self.enemies:
                    if e.alive and self.hit(b.x, b.y, e.x, e.y, 8, 7):
                        b.alive = False
                        e.hp -= 1
                        if e.hp <= 0:
                            e.alive = False
                            bonus = e.points * (2 if e.diving else 1)
                            self.score += bonus
                            self.high_score = max(self.high_score, self.score)
                        break
            elif p.invulnerable == 0 and self.hit(b.x, b.y, p.x, p.y, 6, 6):
                b.alive = False
                self.kill_player()

        if p.invulnerable == 0:
            for e in self.enemies:
                if e.alive and e.diving and self.hit(e.x, e.y, p.x, p.y, 8, 7):
                    e.alive = False
                    self.kill_player()
                    break

        self.bullets = [b for b in self.bullets if b.alive]

    def kill_player(self):
        if self.player.invulnerable:
            return
        if not self.infinite_lives:
            self.player.lives -= 1
        self.player.invulnerable = 110
        self.player.x = W / 2
        self.bullets = [b for b in self.bullets if b.owner == "player"]
        if self.player.lives <= 0 and not self.infinite_lives:
            self.state = "gameover"

    def draw_starfield(self):
        colors = (WHITE, LIGHT_BLUE, YELLOW, GRAY)
        for i, (x, y, speed) in enumerate(self.stars):
            c = colors[(i + speed) % len(colors)]
            size = 1 if speed == 1 else 1.4
            self.rect(x, y, x + size, y + size, fill=c, outline="")

    def draw_player(self):
        p = self.player
        if p.invulnerable and (p.invulnerable // 5) % 2 == 0:
            return
        x, y = p.x, p.y
        self.poly([(x, y-8), (x-3, y-1), (x-8, y+5), (x-2, y+4), (x, y+7), (x+2, y+4), (x+8, y+5), (x+3, y-1)], fill=WHITE, outline="")
        self.poly([(x, y-6), (x-2, y+2), (x+2, y+2)], fill=RED, outline="")
        self.rect(x-5, y+2, x-3, y+5, fill=BLUE, outline="")
        self.rect(x+3, y+2, x+5, y+5, fill=BLUE, outline="")

    def draw_enemy(self, e: Enemy):
        x, y = e.x, e.y
        if e.kind == "bee":
            self.poly([(x, y-5), (x-6,y-1), (x-4,y+5), (x,y+2), (x+4,y+5), (x+6,y-1)], fill=YELLOW, outline="")
            self.rect(x-2,y-3,x+2,y+1,fill=RED,outline="")
        elif e.kind == "butterfly":
            self.poly([(x,y-5),(x-3,y-1),(x-8,y-4),(x-6,y+4),(x-2,y+2),(x,y+6),(x+2,y+2),(x+6,y+4),(x+8,y-4),(x+3,y-1)], fill=RED, outline="")
            self.rect(x-2,y-3,x+2,y+2,fill=WHITE,outline="")
            self.rect(x-6,y-1,x-4,y+1,fill=BLUE,outline="")
            self.rect(x+4,y-1,x+6,y+1,fill=BLUE,outline="")
        else:
            self.poly([(x,y-6),(x-4,y-3),(x-8,y-5),(x-7,y+3),(x-3,y+5),(x,y+2),(x+3,y+5),(x+7,y+3),(x+8,y-5),(x+4,y-3)], fill=BLUE if e.hp > 1 else RED, outline="")
            self.rect(x-3,y-2,x+3,y+2,fill=WHITE,outline="")
            self.rect(x-1,y-1,x+1,y+1,fill=RED,outline="")

    def draw_hud(self):
        self.text(8, 5, "1UP", 6, RED, "nw")
        self.text(8, 13, f"{self.score:06d}", 6, WHITE, "nw")
        self.text(W/2, 5, "HIGH SCORE", 6, RED)
        self.text(W/2, 13, f"{self.high_score:06d}", 6, WHITE)
        self.text(W-8, 5, f"STAGE {self.stage}", 6, CYAN, "ne")
        lives = "∞" if self.infinite_lives else str(max(0, self.player.lives))
        self.text(8, H-9, f"LIVES {lives}", 6, GREEN, "sw")

    def draw_title(self):
        self.draw_starfield()
        self.text(W/2, 43, "GALAGA!", 20, CYAN)
        self.text(W/2, 62, "MSX PYTHON PORT", 7, WHITE)
        self.text(W/2, 90, "ENTER / SPACE - START", 6, YELLOW)
        self.text(W/2, 104, "I - VIDAS INFINITAS: " + ("SIM" if self.infinite_lives else "NAO"), 6, GREEN if self.infinite_lives else WHITE)
        self.text(W/2, 124, "SETA/A,D - MOVER", 6, WHITE)
        self.text(W/2, 136, "SPACE/Z - TIRO", 6, WHITE)
        self.text(W/2, 148, "P - PAUSA", 6, WHITE)
        self.text(W/2, 172, "Original MSX loader: Top Secret Software, 1987", 5, GRAY)

    def draw(self):
        self.canvas.delete("all")
        if self.state == "title":
            self.draw_title()
            return

        self.draw_starfield()
        self.draw_hud()
        for e in self.enemies:
            if e.alive:
                self.draw_enemy(e)
        for b in self.bullets:
            if b.owner == "player":
                self.rect(b.x-1, b.y-4, b.x+1, b.y+2, fill=WHITE, outline="")
            else:
                self.rect(b.x-1, b.y-1, b.x+1, b.y+2, fill=RED, outline="")
        self.draw_player()

        if self.message_timer > 0:
            self.text(W/2, H/2+12, f"STAGE {self.stage}", 9, CYAN)
        if self.state == "paused":
            self.rect(65, 78, 191, 112, fill=BLACK, outline=WHITE)
            self.text(W/2, 92, "PAUSA", 9, YELLOW)
            self.text(W/2, 104, "P PARA CONTINUAR", 5, WHITE)
        elif self.state == "gameover":
            self.rect(55, 72, 201, 120, fill=BLACK, outline=RED)
            self.text(W/2, 87, "GAME OVER", 11, RED)
            self.text(W/2, 104, "ENTER PARA TITULO", 5, WHITE)

    def tick(self):
        self.update()
        self.draw()
        if self.root.winfo_exists():
            self.root.after(DT_MS, self.tick)

    def run(self):
        self.tick()
        self.root.mainloop()


if __name__ == "__main__":
    GalagaMSX().run()
