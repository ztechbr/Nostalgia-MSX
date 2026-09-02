"""Playback engine: steps through a dance routine string beat-by-beat while
looping the musical score underneath it, exactly like the original -
"the musical score will continue repeating until the dance routine is
finished".
"""

import pygame

from data import ROUTINE_TABLE, REST_LETTER
from dancer import Dancer

BG_TOP = (18, 18, 40)
BG_BOTTOM = (60, 30, 70)


def _draw_background(surface):
    h = surface.get_height()
    for y in range(h):
        t = y / h
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))
    pygame.draw.rect(surface, (25, 20, 30), (0, 415, surface.get_width(), 60))
    pygame.draw.line(surface, (255, 215, 0), (0, 415), (surface.get_width(), 415), 2)


def play_show(screen, clock, font, dance: str, music: str, beat_seconds: float, tone_bank, repeats: int = 1):
    """Runs the animation loop. Returns False if the user quit the app,
    True if the show finished (or was skipped with SPACE)."""
    dancer = Dancer()
    music = music or REST_LETTER
    music_i = 0

    for _ in range(max(1, repeats)):
        for letter in dance:
            entry = ROUTINE_TABLE.get(letter.upper())
            if entry is None:
                continue
            label, beats, kind, direction = entry
            dancer.start_move(kind, direction)
            duration = beats * beat_seconds
            elapsed = 0.0
            beats_played = 0

            # play the note for the first beat of this move immediately
            tone_bank.play(music[music_i % len(music)])
            music_i += 1

            while elapsed < duration:
                dt = clock.tick(60) / 1000.0
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return False
                    if event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_SPACE, pygame.K_ESCAPE):
                            return True

                elapsed += dt
                progress = min(1.0, elapsed / duration)
                dancer.update(progress)

                # fire remaining beats within a long move (e.g. STEP #7 = 4 beats)
                whole_beats = int(elapsed / beat_seconds)
                while beats_played < whole_beats and beats_played < beats - 1:
                    beats_played += 1
                    tone_bank.play(music[music_i % len(music)])
                    music_i += 1

                _draw_background(screen)
                dancer.draw(screen, progress, label)
                info = font.render(f"Now dancing: {label}", True, (255, 255, 255))
                screen.blit(info, (20, 20))
                hint = font.render("SPACE/ESC: stop show", True, (200, 200, 200))
                screen.blit(hint, (20, 50))
                pygame.display.flip()
    return True
