"""Draws and animates the little dancing figure."""

import math
import pygame

FLOOR_Y = 420
CENTER_X = 400
MOVE_STEP_PX = 28
MAX_OFFSET = 220

SKIN = (255, 214, 170)
SUIT = (220, 60, 60)
OUTLINE = (30, 20, 20)
SHADOW = (40, 40, 40)


class Dancer:
    def __init__(self):
        self.x_offset = 0.0
        self.facing = 0.0       # degrees, 0 = facing viewer
        self.kind = "stand"
        self.direction = 0
        self.impact_flash = 0.0
        self._start_facing = 0.0
        self._start_offset = 0.0

    def start_move(self, kind: str, direction: int):
        self.kind = kind
        self.direction = direction
        self._start_facing = self.facing
        self._start_offset = self.x_offset
        if kind in ("stomp",):
            self.impact_flash = 1.0

    def update(self, progress: float):
        """progress runs 0..1 across the full duration of the current move."""
        if self.kind == "turn":
            self.facing = self._start_facing + self.direction * 90 * progress
        elif self.kind == "move":
            target = self._start_offset + self.direction * MOVE_STEP_PX * 2 * progress
            self.x_offset = max(-MAX_OFFSET, min(MAX_OFFSET, target))
        if self.impact_flash > 0:
            self.impact_flash = max(0.0, self.impact_flash - 0.08)

    def _bob(self, progress):
        return abs(math.sin(progress * math.pi * 3)) * 10

    def _pose_offsets(self, progress):
        """Returns (body_lift, leg_spread, arm_lift, jump_height, spin_deg)."""
        k = self.kind
        if k == "step":
            return self._bob(progress), 10 + 6 * math.sin(progress * math.pi * 4), 8 * math.sin(progress * math.pi * 4), 0, 0
        if k == "squat":
            depth = math.sin(progress * math.pi)
            return -18 * depth, 22, -10 * depth, 0, 0
        if k == "stand":
            return 0, 6, 0, 0, 0
        if k == "stomp":
            return 0, 14, 0, 0, 0
        if k == "turn":
            return 3 * math.sin(progress * math.pi * 2), 8, 0, 0, self.facing
        if k == "move":
            return self._bob(progress), 12, 6 * math.sin(progress * math.pi * 4), 0, self.facing
        if k == "jump":
            h = math.sin(progress * math.pi) * 34
            return 0, 8, 20 * math.sin(progress * math.pi), h, 0
        if k == "spinjump":
            h = math.sin(progress * math.pi) * 40
            spin_sign = -1 if self.direction < 0 else 1
            return 0, 8, 0, h, progress * 360 * spin_sign
        if k == "slowjump":
            h = math.sin(progress * math.pi) * 55
            return 0, 8, 14 * math.sin(progress * math.pi), h, 0
        return 0, 8, 0, 0, 0

    def draw(self, surface, progress: float, label: str = ""):
        body_lift, leg_spread, arm_lift, jump_height, spin_deg = self._pose_offsets(progress)

        cx = CENTER_X + self.x_offset
        base_y = FLOOR_Y - jump_height

        # shadow
        shadow_scale = max(0.3, 1 - jump_height / 80)
        pygame.draw.ellipse(
            surface, SHADOW,
            pygame.Rect(int(cx - 30 * shadow_scale), FLOOR_Y + 8, int(60 * shadow_scale), 14),
        )

        hip_y = base_y - 70 - body_lift
        shoulder_y = hip_y - 45
        head_y = shoulder_y - 22

        angle = math.radians(spin_deg)
        cos_a, sin_a = math.cos(angle), math.sin(angle)

        def rot(dx, dy):
            # simple squash to fake a turntable rotation around the vertical axis
            squash = abs(cos_a)
            return cx + dx * (0.35 + 0.65 * squash) + dy * sin_a * 0.3, hip_y + dy

        leg_l = rot(-leg_spread, 60)
        leg_r = rot(leg_spread, 60)
        hip = (cx, hip_y)
        shoulder = (cx, shoulder_y)
        arm_l = rot(-24, 30 - arm_lift)
        arm_r = rot(24, 30 - arm_lift)
        head_center = (cx, head_y)

        pygame.draw.line(surface, OUTLINE, hip, leg_l, 6)
        pygame.draw.line(surface, OUTLINE, hip, leg_r, 6)
        pygame.draw.line(surface, OUTLINE, hip, shoulder, 8)
        pygame.draw.line(surface, OUTLINE, shoulder, arm_l, 6)
        pygame.draw.line(surface, OUTLINE, shoulder, arm_r, 6)
        pygame.draw.circle(surface, SUIT, (int(cx), int((hip_y + shoulder_y) / 2)), 16)
        pygame.draw.circle(surface, SKIN, (int(head_center[0]), int(head_center[1])), 16)
        pygame.draw.circle(surface, OUTLINE, (int(head_center[0]), int(head_center[1])), 16, 2)

        if self.impact_flash > 0:
            r = int(20 + 30 * (1 - self.impact_flash))
            flash_surf = pygame.Surface((r * 2, r), pygame.SRCALPHA)
            alpha = int(180 * self.impact_flash)
            pygame.draw.ellipse(flash_surf, (255, 230, 120, alpha), flash_surf.get_rect())
            surface.blit(flash_surf, (cx - r, FLOOR_Y - r // 2))

        if label:
            font = pygame.font.SysFont("consolas", 20)
            text = font.render(label, True, (255, 255, 255))
            surface.blit(text, (cx - text.get_width() // 2, head_y - 46))
