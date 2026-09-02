"""On-screen note / routine entry, modeled on the original's key-based entry:
press a letter key to append an entry, BACKSPACE erases the last one,
SPACE previews the score/routine so far, CLEAR (Delete key) starts over,
ENTER finishes.
"""

import pygame

from data import MAX_NOTES, MAX_ROUTINE, NOTE_LETTERS, ROUTINE_TABLE, REST_LETTER

TEXT_COLOR = (255, 255, 255)
DIM_COLOR = (170, 170, 190)
BG = (15, 15, 30)


def _wrap(text, width=60):
    lines = []
    for i in range(0, len(text), width):
        lines.append(text[i:i + width])
    return lines or [""]


def enter_musical_score(screen, clock, font, big_font, existing: str = "") -> str:
    valid_keys = set(NOTE_LETTERS) | {REST_LETTER}
    return _enter_letters(
        screen, clock, font, big_font,
        existing=existing,
        valid_keys=valid_keys,
        max_len=MAX_NOTES,
        title="ENTER MUSICAL SCORE",
        subtitle="A-Y = notes C1..C3 chromatic, Z = rest. SPACE previews, ENTER finishes, BACKSPACE erases, DEL clears.",
        preview_kind="music",
    )


def enter_dance_routine(screen, clock, font, big_font, existing: str = "") -> str:
    valid_keys = set(ROUTINE_TABLE.keys())
    return _enter_letters(
        screen, clock, font, big_font,
        existing=existing,
        valid_keys=valid_keys,
        max_len=MAX_ROUTINE,
        title="ENTER DANCE ROUTINE",
        subtitle="A-Z = dance moves (see help). SPACE previews, ENTER finishes, BACKSPACE erases, DEL clears.",
        preview_kind="dance",
    )


def _enter_letters(screen, clock, font, big_font, existing, valid_keys, max_len, title, subtitle, preview_kind):
    from player import play_show
    from audio import ToneBank

    text = existing
    tone_bank = None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return text
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    return text
                if event.key == pygame.K_BACKSPACE:
                    text = text[:-1]
                elif event.key == pygame.K_DELETE:
                    text = ""
                elif event.key == pygame.K_SPACE:
                    if text:
                        if tone_bank is None:
                            tone_bank = ToneBank(0.22)
                        if preview_kind == "music":
                            play_show(screen, clock, font, "A" * len(text), text, 0.22, tone_bank, repeats=1)
                        else:
                            play_show(screen, clock, font, text, "Z", 0.22, tone_bank, repeats=1)
                else:
                    ch = event.unicode.upper()
                    if ch in valid_keys and len(text) < max_len:
                        text += ch

        screen.fill(BG)
        title_surf = big_font.render(title, True, (255, 210, 60))
        screen.blit(title_surf, (screen.get_width() // 2 - title_surf.get_width() // 2, 40))

        sub_surf = font.render(subtitle, True, DIM_COLOR)
        screen.blit(sub_surf, (40, 100))

        count_surf = font.render(f"{len(text)} / {max_len} entries", True, DIM_COLOR)
        screen.blit(count_surf, (40, 130))

        y = 180
        for line in _wrap(text, 60):
            line_surf = font.render(line, True, TEXT_COLOR)
            screen.blit(line_surf, (40, y))
            y += 30

        pygame.display.flip()
        clock.tick(60)
