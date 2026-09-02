"""
THE DANCING DEMON - a Pygame recreation
Original TRS-80 Color Computer program (c) 1979, 1986 by Leo Christopherson,
published by PowerSoft Products. This is a modern reinterpretation: same
mechanics (musical score editor, dance routine editor, synced playback,
save/load, preset shows), rebuilt from scratch in Python.
"""

import os
import sys

import pygame

from data import PRESET_SHOWS, INTRO_JIG, REST_LETTER
from audio import ToneBank
from dancer import Dancer
from player import play_show
import editor

WIDTH, HEIGHT = 800, 480
SAVES_DIR = os.path.join(os.path.dirname(__file__), "saves")


def default_beat_seconds(speed_factor: int) -> float:
    # Original: 1 (very fast) .. 255 (very slow), default ~35.
    # Map that range onto a musically sane 0.08s .. 0.9s beat duration.
    speed_factor = max(1, min(255, speed_factor))
    return 0.08 + (speed_factor / 255) * 0.82


def title_screen(screen, clock, font, big_font):
    tone_bank = ToneBank(0.18)
    dancer = Dancer()
    t = 0.0
    jig = INTRO_JIG
    beat_len = 0.35
    idx = 0
    beat_timer = 0.0
    entry = None

    from data import ROUTINE_TABLE

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt
        beat_timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                return

        if entry is None or beat_timer >= beat_len:
            beat_timer = 0.0
            letter = jig[idx % len(jig)]
            entry = ROUTINE_TABLE[letter]
            dancer.start_move(entry[2], entry[3])
            idx += 1

        progress = min(1.0, beat_timer / beat_len)
        dancer.update(progress)

        screen.fill((15, 12, 30))
        dancer.draw(screen, progress)

        lines = [
            ("PowerSoft Products", 100),
            ("presents", 140),
            ("THE DANCING DEMON", 190),
            ("Program by Leo Christopherson", 230),
            ("Copyright 1979, 1986  -  Python/Pygame recreation", 255),
            ("Press any key to continue...", 400),
        ]
        for text, y in lines:
            surf = big_font.render(text, True, (255, 220, 90)) if y == 190 else font.render(text, True, (230, 230, 230))
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))

        pygame.display.flip()


def menu_screen(screen, font, big_font, state):
    options = [
        "1) Enter a new musical score",
        "2) Enter a new dance routine",
        "3) Play the current show",
        "4) Save the current show to disk",
        "5) Load a show from disk",
        "6) Play a preset show",
        "7) Set speed / performances",
        "8) End program",
    ]
    screen.fill((20, 18, 40))
    title = big_font.render("DANCING DEMON - MAIN MENU", True, (255, 210, 60))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 30))

    y = 100
    for opt in options:
        surf = font.render(opt, True, (240, 240, 240))
        screen.blit(surf, (80, y))
        y += 40

    status = [
        f"Musical score length: {len(state['music'])} notes",
        f"Dance routine length: {len(state['dance'])} moves",
        f"Speed factor: {state['speed']}   Performances: {state['performances']}",
    ]
    y = 420 - 20 * (len(status))
    y = 400
    for s in status:
        surf = font.render(s, True, (170, 210, 255))
        screen.blit(surf, (80, y))
        y += 22

    pygame.display.flip()


def prompt_number(screen, font, big_font, prompt, default, min_v, max_v):
    text = ""
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if text == "":
                        return default
                    try:
                        val = int(text)
                        if min_v <= val <= max_v:
                            return val
                    except ValueError:
                        pass
                    text = ""
                elif event.key == pygame.K_BACKSPACE:
                    text = text[:-1]
                elif event.unicode.isdigit():
                    text += event.unicode

        screen.fill((15, 15, 30))
        p1 = font.render(prompt, True, (255, 255, 255))
        p2 = font.render(f"(default {default})  Enter value: {text}", True, (200, 200, 220))
        screen.blit(p1, (40, 180))
        screen.blit(p2, (40, 220))
        pygame.display.flip()


def choose_preset(screen, font, big_font):
    idx = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_UP:
                    idx = (idx - 1) % len(PRESET_SHOWS)
                if event.key == pygame.K_DOWN:
                    idx = (idx + 1) % len(PRESET_SHOWS)
                if event.key == pygame.K_RETURN:
                    return PRESET_SHOWS[idx]

        screen.fill((15, 15, 30))
        title = big_font.render("CHOOSE A PRESET SHOW", True, (255, 210, 60))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))
        y = 130
        for i, show in enumerate(PRESET_SHOWS):
            color = (255, 255, 0) if i == idx else (220, 220, 220)
            surf = font.render(f"{'>' if i == idx else ' '} {show['name']}  ({len(show['dance'])} moves)", True, color)
            screen.blit(surf, (80, y))
            y += 36
        hint = font.render("UP/DOWN to choose, ENTER to play, ESC to cancel", True, (170, 170, 190))
        screen.blit(hint, (80, y + 20))
        pygame.display.flip()


def save_show(state):
    os.makedirs(SAVES_DIR, exist_ok=True)
    name = state.get("save_name") or "show1"
    path = os.path.join(SAVES_DIR, f"{name}.txt")
    with open(path, "w") as f:
        f.write(state["dance"] + "\n")
        f.write(state["music"] + "\n")
    return path


def load_show(name):
    path = os.path.join(SAVES_DIR, f"{name}.txt")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        lines = f.read().splitlines()
    dance = lines[0] if len(lines) > 0 else ""
    music = lines[1] if len(lines) > 1 else ""
    return dance, music


def text_prompt(screen, font, prompt, default=""):
    text = default
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    return text
                if event.key == pygame.K_BACKSPACE:
                    text = text[:-1]
                elif event.unicode.isprintable():
                    text += event.unicode

        screen.fill((15, 15, 30))
        p1 = font.render(prompt, True, (255, 255, 255))
        p2 = font.render(text + "_", True, (200, 220, 255))
        screen.blit(p1, (40, 180))
        screen.blit(p2, (40, 220))
        pygame.display.flip()


def main():
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("The Dancing Demon")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 20)
    big_font = pygame.font.SysFont("consolas", 32, bold=True)

    state = {
        "music": "",
        "dance": "",
        "speed": 35,
        "performances": 1,
        "save_name": "show1",
    }

    title_screen(screen, clock, font, big_font)

    while True:
        menu_screen(screen, font, big_font, state)

        choice = None
        while choice is None:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if event.type == pygame.KEYDOWN:
                    if pygame.K_1 <= event.key <= pygame.K_8:
                        choice = event.key - pygame.K_0
            clock.tick(60)

        if choice == 1:
            state["music"] = editor.enter_musical_score(screen, clock, font, big_font, state["music"])
        elif choice == 2:
            state["dance"] = editor.enter_dance_routine(screen, clock, font, big_font, state["dance"])
        elif choice == 3:
            if state["dance"]:
                beat_seconds = default_beat_seconds(state["speed"])
                tone_bank = ToneBank(beat_seconds)
                music = state["music"] or REST_LETTER
                play_show(screen, clock, font, state["dance"], music, beat_seconds, tone_bank, state["performances"])
        elif choice == 4:
            name = text_prompt(screen, font, "Enter a name for this show:", state["save_name"])
            if name:
                state["save_name"] = name
                path = save_show(state)
                flash_message(screen, font, f"Saved to {path}")
        elif choice == 5:
            name = text_prompt(screen, font, "Enter the name of the show to load:", state["save_name"])
            if name:
                result = load_show(name)
                if result:
                    state["dance"], state["music"] = result
                    state["save_name"] = name
                    flash_message(screen, font, "Loaded!")
                else:
                    flash_message(screen, font, f"No saved show named '{name}' found.")
        elif choice == 6:
            show = choose_preset(screen, font, big_font)
            if show:
                beat_seconds = default_beat_seconds(state["speed"])
                tone_bank = ToneBank(beat_seconds)
                play_show(screen, clock, font, show["dance"], show["music"], beat_seconds, tone_bank, 1)
        elif choice == 7:
            state["speed"] = prompt_number(
                screen, font, big_font,
                "Enter a speed factor from 1 (very fast) to 255 (very slow):",
                state["speed"], 1, 255,
            )
            state["performances"] = prompt_number(
                screen, font, big_font,
                "Enter number of performances:",
                state["performances"], 1, 99,
            )
        elif choice == 8:
            pygame.quit()
            sys.exit(0)


def flash_message(screen, font, message, seconds=1.2):
    clock = pygame.time.Clock()
    elapsed = 0
    while elapsed < seconds:
        dt = clock.tick(60) / 1000.0
        elapsed += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
        screen.fill((15, 15, 30))
        surf = font.render(message, True, (255, 255, 150))
        screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT // 2))
        pygame.display.flip()


if __name__ == "__main__":
    main()
