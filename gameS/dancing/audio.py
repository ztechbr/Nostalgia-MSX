"""Simple tone synthesizer standing in for the TRS-80's single-voice square
wave sound generator."""

import numpy as np
import pygame

from data import NOTE_LETTERS, note_frequency

SAMPLE_RATE = 44100


def _square_wave(freq, duration, volume=0.35):
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    wave = np.sign(np.sin(2 * np.pi * freq * t))
    # short fade in/out to avoid clicks
    fade = max(1, int(SAMPLE_RATE * 0.01))
    envelope = np.ones(n_samples)
    envelope[:fade] = np.linspace(0, 1, fade)
    envelope[-fade:] = np.linspace(1, 0, fade)
    wave = (wave * envelope * volume * 32767).astype(np.int16)
    stereo = np.column_stack([wave, wave])
    return np.ascontiguousarray(stereo)


class ToneBank:
    """Pre-renders one Sound per note letter at a fixed beat duration."""

    def __init__(self, beat_seconds: float):
        self.beat_seconds = beat_seconds
        self._sounds = {}
        for letter in NOTE_LETTERS:
            freq = note_frequency(letter)
            arr = _square_wave(freq, beat_seconds)
            self._sounds[letter] = pygame.sndarray.make_sound(arr)

    def play(self, letter: str):
        letter = letter.upper()
        sound = self._sounds.get(letter)
        if sound is not None:
            sound.play()
