"""
FROGER / Frogger - port do MSX-BASIC para Python/Tkinter
========================================================

Origem:
    froger.bas - programa MSX-BASIC tokenizado, criado por OSYMER
    para MSX Extra.

Este port reproduz a lógica observada no BASIC original:
- resolução lógica 256x192
- sapo movendo-se lateralmente
- salto acionado por botão/espaço
- meteoritos
- inimigos no solo
- oxigênio
- vidas
- score
- níveis
- nave de resgate quando o oxigênio baixa
- padrões de sprite reconstruídos a partir dos DATA originais

Não utiliza ROM, BIOS ou emulador MSX.

Requisitos:
    Python 3 com Tkinter

Execução:
    python froger_msx_python.py

Controles:
    Esquerda: seta esquerda / A
    Direita:  seta direita  / D
    Salto:    espaço / Z
    Pausa:    P
    Reinicia: R
    Sai:      Esc
"""

from __future__ import annotations

import math
import random
import time
import tkinter as tk
from dataclasses import dataclass


LOGICAL_W = 256
LOGICAL_H = 192
SCALE = 3
FPS = 60

# Paleta aproximada MSX/TMS9918.
MSX = {
    0: "#000000",
    1: "#000000",
    2: "#3EB849",
    3: "#74D07D",
    4: "#5955E0",
    5: "#8076F1",
    6: "#B95E51",
    7: "#65DBEF",
    8: "#DB6559",
    9: "#FF897D",
    10: "#CCC35E",
    11: "#DED087",
    12: "#3AA241",
    13: "#B766B5",
    14: "#CCCCCC",
    15: "#FFFFFF",
}


# DATA 1770..1860 do BASIC original.
# 0 e 1: sprites 8x8
# 2..8: sprites 16x16
# 10: sprite 8x8 (ícone de vida)
SPRITE_DATA = [
    # sprite 0
    24,52,126,187,247,94,44,24,
    # sprite 1
    36,152,40,112,10,128,8,0,

    # sprite 2
    0,0,0,4,10,15,31,15,7,11,16,32,16,8,4,28,
    0,0,0,32,80,240,248,240,224,208,8,4,8,16,32,56,

    # sprite 3
    4,10,15,31,15,7,11,8,8,8,8,4,4,4,4,28,
    32,80,240,248,240,224,208,16,16,16,16,32,32,32,32,56,

    # sprite 4
    48,8,4,2,1,19,29,19,1,7,11,11,11,11,9,16,
    12,16,32,64,128,200,184,200,128,224,208,208,208,208,144,8,

    # sprite 5
    3,4,8,8,16,16,16,16,63,127,223,53,31,47,64,128,
    192,32,16,16,8,8,8,8,252,254,251,172,248,244,2,1,

    # sprite 6
    0,3,15,29,55,127,238,196,68,36,20,12,4,2,2,2,
    0,192,240,184,236,254,119,35,34,36,40,48,32,64,64,64,

    # sprite 7
    3,15,63,63,111,127,255,255,0,0,3,15,63,63,15,3,
    192,240,252,252,254,254,255,255,63,255,254,254,252,252,240,192,

    # sprite 8
    3,15,63,63,111,127,255,255,0,255,127,127,63,63,15,3,
    192,240,252,252,254,254,255,255,63,255,254,254,252,252,240,192,

    # sprite 10
    36,90,255,126,60,66,36,102,
]


def decode_8x8(data: list[int]) -> list[list[int]]:
    return [[1 if b & (0x80 >> x) else 0 for x in range(8)] for b in data]


def decode_16x16(data: list[int]) -> list[list[int]]:
    """
    TMS9918 16x16 sprite layout:
      bytes 0..7   top-left
      bytes 8..15  bottom-left
      bytes 16..23 top-right
      bytes 24..31 bottom-right
    """
    grid = [[0] * 16 for _ in range(16)]
    chunks = [data[0:8], data[8:16], data[16:24], data[24:32]]
    origins = [(0, 0), (0, 8), (8, 0), (8, 8)]
    for chunk, (ox, oy) in zip(chunks, origins):
        block = decode_8x8(chunk)
        for y in range(8):
            for x in range(8):
                grid[oy + y][ox + x] = block[y][x]
    return grid


def build_patterns() -> dict[int, list[list[int]]]:
    p: dict[int, list[list[int]]] = {}
    i = 0

    p[0] = decode_8x8(SPRITE_DATA[i:i+8]); i += 8
    p[1] = decode_8x8(SPRITE_DATA[i:i+8]); i += 8

    for n in range(2, 9):
        p[n] = decode_16x16(SPRITE_DATA[i:i+32])
        i += 32

    p[10] = decode_8x8(SPRITE_DATA[i:i+8])
    return p


PATTERNS = build_patterns()


@dataclass
class RectObj:
    x: float
    y: float
    w: int
    h: int

    def overlaps(self, other: "RectObj", margin: int = 2) -> bool:
        return (
            self.x + self.w - margin > other.x + margin
            and self.x + margin < other.x + other.w - margin
            and self.y + self.h - margin > other.y + margin
            and self.y + margin < other.y + other.h - margin
        )


class FroggerMSX:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FROGER - MSX BASIC port")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=LOGICAL_W * SCALE,
            height=LOGICAL_H * SCALE,
            bg="black",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.keys: set[str] = set()
        self.jump_pressed = False
        self.paused = False
        self.game_over = False

        root.bind("<KeyPress>", self.key_down)
        root.bind("<KeyRelease>", self.key_up)

        self.stars = [
            (random.randint(8, 247), random.randint(13, 134), random.choice([14, 15]))
            for _ in range(25)
        ]

        self.new_game()
        self.last = time.perf_counter()
        self.acc = 0.0
        self.loop()

    def new_game(self):
        # BASIC 1730 / 760
        self.score = 0
        self.level = 1
        self.lives = 3                  # B = 3, plus current frog
        self.frog_x = 100.0
        self.ground_y = 150.0
        self.frog_y = self.ground_y
        self.jump_velocity = 0.0
        self.jumping = False

        self.speed = 3.0                # MY
        self.oxygen = 171.0             # S from 241 down to 70
        self.oxygen_tick = 0

        self.meteor_x = random.randint(1, 225)
        self.meteor_y = 10.0
        self.meteor_frame = 0

        self.enemy_offset = 0.0         # M
        self.enemy_count = 1            # L
        self.ship_x = random.randint(1, 225)
        self.ship_y = 10.0              # U
        self.ship_visible = False
        self.ship_done = False          # UB

        self.respawn_timer = 0
        self.invulnerable = 0
        self.message = ""
        self.message_timer = 0
        self.game_over = False

    def key_down(self, event):
        key = event.keysym.lower()
        self.keys.add(key)

        if key in ("space", "z") and not self.jump_pressed:
            self.jump_pressed = True
            self.start_jump()

        elif key == "p":
            self.paused = not self.paused
        elif key == "r":
            self.new_game()
        elif key == "escape":
            self.root.destroy()

        if self.game_over and key in ("return", "space"):
            self.new_game()

    def key_up(self, event):
        key = event.keysym.lower()
        self.keys.discard(key)
        if key in ("space", "z"):
            self.jump_pressed = False

    def start_jump(self):
        # BASIC 410: P=-4, K=1, Q=150
        if not self.jumping and not self.game_over and self.respawn_timer <= 0:
            self.jumping = True
            self.jump_velocity = -4.0

    def player_rect(self) -> RectObj:
        return RectObj(self.frog_x, self.frog_y, 16, 16)

    def meteor_rect(self) -> RectObj:
        return RectObj(self.meteor_x, self.meteor_y, 8, 8)

    def ship_rect(self) -> RectObj:
        return RectObj(self.ship_x, self.ship_y, 16, 16)

    def enemy_positions(self):
        # BASIC:
        # M, M-95, M-190
        xs = [self.enemy_offset, self.enemy_offset - 95, self.enemy_offset - 190]
        return xs[:self.enemy_count]

    def consume_meteor(self):
        self.score += 10
        self.meteor_y = 10
        self.meteor_x = random.randint(1, 225)
        self.message = "+10"
        self.message_timer = 35

    def lose_frog(self, reason=""):
        if self.invulnerable > 0 or self.respawn_timer > 0 or self.game_over:
            return

        self.lives -= 1
        self.message = reason or "RANA CONGELADA"
        self.message_timer = 70

        if self.lives < 0:
            self.game_over = True
            return

        # BASIC resets oxygen and rescue state after death.
        self.oxygen = 171
        self.ship_y = 10
        self.ship_visible = False
        self.ship_done = False
        self.jumping = False
        self.frog_y = 150
        self.respawn_timer = 70
        self.invulnerable = 120

    def board_ship(self):
        # Approximation faithful to BASIC 1130..1500.
        self.message = "NIVEL SUPERADO"
        self.message_timer = 90
        self.level += 1
        self.score += 50

        if self.enemy_count < 3:
            self.enemy_count += 1

        self.speed = min(6, self.speed + 1)
        self.oxygen = 171
        self.enemy_offset = 0
        self.meteor_y = 10
        self.ship_y = 10
        self.ship_visible = False
        self.ship_done = False
        self.frog_x = self.ship_x
        self.frog_y = 150
        self.jumping = False
        self.invulnerable = 90

    def update(self):
        if self.paused or self.game_over:
            return

        if self.message_timer > 0:
            self.message_timer -= 1

        if self.invulnerable > 0:
            self.invulnerable -= 1

        if self.respawn_timer > 0:
            self.respawn_timer -= 1
            if self.respawn_timer == 0:
                # BASIC resurrection lets player move during descent.
                self.frog_x = 120
                self.frog_y = 150
            return

        # BASIC 250 / 270
        if "left" in self.keys or "a" in self.keys:
            self.frog_x -= self.speed
        if "right" in self.keys or "d" in self.keys:
            self.frog_x += self.speed
        self.frog_x = max(3, min(239, self.frog_x))

        # Salto BASIC 420..450.
        if self.jumping:
            self.frog_y += self.jump_velocity
            if self.frog_y <= 106:
                self.frog_y = 106
                self.jump_velocity = 4
            elif self.frog_y >= 150:
                self.frog_y = 150
                self.jumping = False
                self.jump_velocity = 0

        # Oxigênio BASIC 260. Original decrementava a cada ~3 ciclos.
        self.oxygen_tick += 1
        if self.oxygen_tick >= 3:
            self.oxygen_tick = 0
            self.oxygen -= 1

        if self.oxygen <= 0:
            self.lose_frog("SEM OXIGENO")
            return

        # Meteorito BASIC 350..370.
        self.meteor_y += 2
        self.meteor_frame ^= 1
        if self.meteor_y > 123:
            self.meteor_y = 10
            self.meteor_x = random.randint(1, 225)

        # Extraterrestres BASIC 310..340.
        self.enemy_offset += self.speed
        if self.enemy_offset > 285:
            self.enemy_offset -= 285

        # Nave aparece quando oxigênio está abaixo de aproximadamente 40/171.
        # BASIC: IF S<110 AND N=10 THEN GOSUB 940
        if self.oxygen < 40 and self.meteor_y <= 12 and not self.ship_done:
            self.ship_visible = True

        if self.ship_visible:
            self.ship_y += 2
            if self.ship_y > 117:
                self.ship_done = True
                self.ship_visible = False

        pr = self.player_rect()

        # Meteor collision is useful only during high jump, matching the
        # original ON SPRITE handler's Q<135 branch.
        if pr.overlaps(self.meteor_rect(), margin=1):
            if self.frog_y < 135:
                self.consume_meteor()
            else:
                self.lose_frog("IMPACTO")
                return

        # Ship capture, original condition U>10 AND Q<135.
        if self.ship_visible and self.frog_y < 135:
            if pr.overlaps(self.ship_rect(), margin=1):
                self.board_ship()
                return

        # Ground aliens freeze the frog.
        for ex in self.enemy_positions():
            ex_mod = ex % 285
            if -20 < ex_mod < 256:
                er = RectObj(ex_mod, 150, 16, 16)
                if pr.overlaps(er):
                    self.lose_frog("RANA CONGELADA")
                    return

    def sx(self, x):
        return int(x * SCALE)

    def sy(self, y):
        return int(y * SCALE)

    def draw_pixel(self, x, y, color):
        self.canvas.create_rectangle(
            self.sx(x), self.sy(y),
            self.sx(x + 1), self.sy(y + 1),
            fill=MSX.get(color, "white"),
            outline=""
        )

    def draw_sprite(self, pattern: int, x: float, y: float, color: int):
        grid = PATTERNS.get(pattern)
        if not grid:
            return

        # Blink when invulnerable.
        if pattern in (2, 3) and self.invulnerable and (self.invulnerable // 5) % 2:
            return

        c = MSX.get(color, "#fff")
        py = int(y)
        px = int(x)
        for yy, row in enumerate(grid):
            for xx, bit in enumerate(row):
                if bit:
                    self.canvas.create_rectangle(
                        self.sx(px + xx),
                        self.sy(py + yy),
                        self.sx(px + xx + 1),
                        self.sy(py + yy + 1),
                        fill=c,
                        outline=""
                    )

    def draw_background(self):
        self.canvas.create_rectangle(
            0, 0, LOGICAL_W*SCALE, LOGICAL_H*SCALE,
            fill=MSX[1], outline=""
        )

        # Stars from BASIC 2040..2060.
        for x, y, col in self.stars:
            self.canvas.create_oval(
                self.sx(x-1), self.sy(y-1),
                self.sx(x+1), self.sy(y+1),
                outline=MSX[col]
            )

        # Planets approximating BASIC 2070..2080.
        self.canvas.create_oval(
            self.sx(197), self.sy(32), self.sx(223), self.sy(58),
            fill=MSX[11], outline=MSX[11]
        )
        self.canvas.create_oval(
            self.sx(194), self.sy(29), self.sx(226), self.sy(61),
            outline=MSX[6], width=max(1, SCALE)
        )
        self.canvas.create_oval(
            self.sx(22), self.sy(92), self.sx(38), self.sy(108),
            fill=MSX[5], outline=MSX[5]
        )

        # Ground/alien planet surface, inspired by DATA 1740..1760.
        points = [
            (0, 148), (30, 145), (65, 150), (100, 143),
            (135, 151), (170, 146), (205, 153), (255, 148),
            (255, 180), (0, 180)
        ]
        flat = []
        for x, y in points:
            flat.extend([self.sx(x), self.sy(y)])
        self.canvas.create_polygon(flat, fill="#17203a", outline=MSX[4])

    def draw_hud(self):
        # Top bar
        self.canvas.create_rectangle(
            self.sx(0), self.sy(0), self.sx(255), self.sy(9),
            fill=MSX[1], outline=""
        )
        self.canvas.create_line(
            self.sx(0), self.sy(10), self.sx(245), self.sy(10),
            fill=MSX[15]
        )

        self.canvas.create_text(
            self.sx(100), self.sy(1),
            anchor="nw",
            text=f"SCORE {self.score}   NIVEL {self.level}",
            fill=MSX[15],
            font=("Courier New", 7*SCALE//2, "bold")
        )

        # Life icons
        for i in range(max(0, self.lives)):
            self.draw_sprite(10, 20 + i*10, 0, 12)

        # Oxygen area
        self.canvas.create_rectangle(
            self.sx(0), self.sy(180), self.sx(255), self.sy(191),
            fill=MSX[1], outline=""
        )
        self.canvas.create_text(
            self.sx(13), self.sy(181),
            anchor="nw", text="OXIGENO",
            fill=MSX[12],
            font=("Courier New", 7*SCALE//2, "bold")
        )
        self.canvas.create_line(
            self.sx(70), self.sy(185),
            self.sx(240), self.sy(185),
            fill=MSX[14]
        )
        self.canvas.create_line(
            self.sx(70), self.sy(187),
            self.sx(240), self.sy(187),
            fill=MSX[15]
        )

        end = 70 + max(0, min(170, int(self.oxygen)))
        self.canvas.create_line(
            self.sx(70), self.sy(186),
            self.sx(end), self.sy(186),
            fill=MSX[12],
            width=max(1, SCALE)
        )

    def draw(self):
        self.canvas.delete("all")
        self.draw_background()
        self.draw_hud()

        if self.respawn_timer > 0:
            # Simple resurrection descent inspired by lines 800..930.
            t = 1 - self.respawn_timer / 70
            y = 11 + 139 * t
            self.draw_sprite(10, self.frog_x, y, 12)
        else:
            # Meteorito
            self.draw_sprite(self.meteor_frame, self.meteor_x, self.meteor_y, 15)

            # Nave
            if self.ship_visible:
                self.draw_sprite(5, self.ship_x, self.ship_y, 13)

            # Inimigos
            for ex in self.enemy_positions():
                ex_mod = ex % 285
                if -20 < ex_mod < 256:
                    self.draw_sprite(4, ex_mod, 150, 4)

            # Frog
            self.draw_sprite(3 if self.jumping else 2,
                             self.frog_x, self.frog_y, 12)

        if self.message_timer > 0:
            self.canvas.create_text(
                self.sx(128), self.sy(88),
                text=self.message,
                fill=MSX[15],
                font=("Courier New", 9*SCALE//2, "bold"),
                anchor="center"
            )

        if self.paused:
            self.overlay("PAUSA\nP PARA CONTINUAR")
        elif self.game_over:
            self.overlay(
                f"FINAL DEL JUEGO\nSCORE {self.score}\n\n"
                "ENTER OU ESPACO: NOVA PARTIDA"
            )

    def overlay(self, text):
        self.canvas.create_rectangle(
            self.sx(28), self.sy(60),
            self.sx(228), self.sy(126),
            fill=MSX[1], outline=MSX[15], width=2
        )
        self.canvas.create_text(
            self.sx(128), self.sy(93),
            text=text,
            fill=MSX[15],
            justify="center",
            font=("Courier New", 8*SCALE//2, "bold")
        )

    def loop(self):
        now = time.perf_counter()
        dt = now - self.last
        self.last = now
        self.acc += dt

        fixed = 1 / FPS
        while self.acc >= fixed:
            self.update()
            self.acc -= fixed

        self.draw()
        self.root.after(8, self.loop)


def main():
    root = tk.Tk()
    FroggerMSX(root)
    root.mainloop()


if __name__ == "__main__":
    main()
