"""Generate the DeskMate pixel-art T-Rex animations.

Build-time tool only. The application plays the produced GIFs with QMovie and never
imports Pillow, so Pillow stays out of the runtime dependencies.

    python tools/make_character_gifs.py

Outputs, for each action:
    assets/character/<action>.gif             30x30 looping GIF, transparent background
    assets/character/frames/<action>/NN.png   the individual frames
    assets/character/preview_<action>.png     8x nearest-neighbour sheet for review
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

SIZE = 30
SCALE = 8
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "character"

# Palette. Index 0 is reserved for transparency.
PALETTE: dict[str, tuple[int, int, int]] = {
    ".": (0, 0, 0),          # transparent
    "K": (26, 58, 42),       # outline / dark green
    "G": (94, 196, 108),     # body
    "D": (58, 148, 84),      # shade
    "L": (198, 240, 168),    # belly / light
    "W": (255, 255, 255),    # eye white, teeth
    "E": (20, 28, 24),       # pupil
    "P": (247, 154, 176),    # cheek
    "Y": (255, 214, 92),     # accent (zzz, sparkle)
}
ORDER = list(PALETTE)
INDEX = {ch: i for i, ch in enumerate(ORDER)}
FLAT: list[int] = []
for ch in ORDER:
    FLAT.extend(PALETTE[ch])
FLAT.extend([0] * (768 - len(FLAT)))


class Canvas:
    """A tiny fixed-size character grid."""

    def __init__(self) -> None:
        self.rows = [["." for _ in range(SIZE)] for _ in range(SIZE)]

    def blit(self, art: list[str], dx: int = 0, dy: int = 0) -> None:
        """Draw non-'.' characters of an ASCII block at an offset."""
        for y, line in enumerate(art):
            for x, ch in enumerate(line):
                if ch == ".":
                    continue
                px, py = x + dx, y + dy
                if 0 <= px < SIZE and 0 <= py < SIZE:
                    self.rows[py][px] = ch

    def to_image(self) -> Image.Image:
        img = Image.new("P", (SIZE, SIZE), 0)
        img.putpalette(FLAT)
        img.putdata([INDEX[ch] for row in self.rows for ch in row])
        return img


# --------------------------------------------------------------------------- art
# Head + neck + torso + tail, without legs or arm. Facing right.
# Rows 0-21; legs are composited from row 20 downwards.
BODY = [
    "..............................",
    "..............................",
    "................KKKKKKK.......",
    "..............KKGGGGGGGKK.....",
    ".............KGGGGGGGGGGGK....",
    ".............KGGGGGGGGGGGGK...",
    "............KGGGGGWWGGGGGGK...",
    "............KGGGGGWEGGGGGGKK..",
    "............KGGGGGWWGGGGGGGK..",
    "............KGGGGGGGGGPGGGGK..",
    "............KGGGGGGGGGGGGGGK..",
    "............KGGGGGGGGWWWWWKK..",
    "...........KKGGGGGGGGKKKKKK...",
    ".........KKKGGGGGGGGGGKK......",
    ".......KKGGGGGGGGGGGGGK.......",
    ".....KKGGGGGGGGGGGGGGGK.......",
    "...KKGGGGGGGGGGGGGGGGGGK......",
    "..KGGGGGGGGGGGGGGGGGGGGK......",
    "......KKKKGGGGGGGGGGGGGK......",
    "..........KGGGGGGGGGGGGK......",
    "...........KGGGGGGGGGGK.......",
    "............KKKKKKKKKK........",
]

# Tail tip, split out of BODY so it can wag without redrawing the torso.
TAIL_TIP = [
    "KGGGG",
    "KGGKK",
    ".KK..",
]
TAIL_AT = (1, 18)

# Belly highlight, drawn after the body so it sits on the lower front edge.
BELLY = [
    "LLLLLLL.",
    ".LLLLLL.",
    "..LLLL..",
]

# Tiny forelimb, solid so it never reads as a hole. Sits on the chest outline.
ARM = [
    "KKK",
    "KGK",
    ".KK",
]

LEG_W = 14          # width of every leg block
LEG_H = 8           # height of every leg block


def _leg_block(back: tuple[int, int], front: tuple[int, int]) -> list[str]:
    """Build one leg block from (x_offset, length) for the back and front legs.

    Legs are three pixels wide (outline, fill, outline) with a four pixel foot, so
    they stay readable at 30x30 where a one pixel limb disappears.
    """
    grid = [["." for _ in range(LEG_W)] for _ in range(LEG_H)]

    def draw(x: int, length: int) -> None:
        length = max(2, min(length, LEG_H - 1))
        for y in range(length):
            for dx, ch in ((0, "K"), (1, "G"), (2, "G"), (3, "K")):
                px = x + dx
                if 0 <= px < LEG_W:
                    grid[y][px] = ch
        foot = length
        if foot < LEG_H:
            for dx, ch in ((0, "K"), (1, "G"), (2, "G"), (3, "G"), (4, "K")):
                px = x + dx
                if 0 <= px < LEG_W:
                    grid[foot][px] = ch
        if foot + 1 < LEG_H:
            for dx in range(5):
                px = x + dx
                if 0 <= px < LEG_W:
                    grid[foot + 1][px] = "K"

    draw(*back)
    draw(*front)
    return ["".join(row) for row in grid]


LEGS_STAND = _leg_block(back=(1, 5), front=(6, 5))
LEGS_RUN_A = _leg_block(back=(0, 6), front=(7, 4))
LEGS_RUN_B = _leg_block(back=(2, 5), front=(6, 5))
LEGS_RUN_C = _leg_block(back=(4, 4), front=(7, 6))
LEGS_RUN_D = _leg_block(back=(1, 4), front=(6, 6))

LEGS_SIT = [
    "..............",
    "...KK.........",
    "..KGGKK.......",
    "..KGGGGKK.....",
    ".KGGGGGGGKK...",
    ".KGGGGGGGGGK..",
    ".KKKKKKKKKKK..",
    "..............",
]

LEGS_SLEEP = [
    "..............",
    "..............",
    "..............",
    "...KKKKKKK....",
    "..KGGGGGGGKK..",
    "..KKKKKKKKKK..",
    "..............",
    "..............",
]

ZZZ_SMALL = ["YYY", "..Y", ".Y.", "Y..", "YYY"]


def eye_closed_patch() -> list[str]:
    """A closed, slightly curved eye replacing the open one."""
    return ["GGG", "KKK", "GGG"]


# --------------------------------------------------------------------- animations
BELLY_AT = (13, 17)     # where the belly highlight sits on the torso
ARM_AT = (21, 16)       # forelimb sits on the chest outline
LEGS_AT_X = 11          # legs attach under the torso (cols 12-21)
LEGS_AT_Y = 20


def _base(canvas: Canvas, dx: int, dy: int, legs, *, arm: bool = True,
          belly: bool = True, closed_eye: bool = False, tail_dy: int = 0) -> None:
    """Compose body, tail, belly, legs and arm at one offset."""
    canvas.blit(BODY, dx=dx, dy=dy)
    canvas.blit(TAIL_TIP, dx=TAIL_AT[0] + dx, dy=TAIL_AT[1] + dy + tail_dy)
    if belly:
        canvas.blit(BELLY, dx=BELLY_AT[0] + dx, dy=BELLY_AT[1] + dy)
    if legs is not None:
        canvas.blit(legs, dx=LEGS_AT_X + dx, dy=LEGS_AT_Y + dy)
    if arm:
        canvas.blit(ARM, dx=ARM_AT[0] + dx, dy=ARM_AT[1] + dy)
    if closed_eye:
        canvas.blit(eye_closed_patch(), dx=18 + dx, dy=6 + dy)


def frame_running(step: int, total: int) -> Canvas:
    """Legs cycle through four poses while the body bobs and leans."""
    canvas = Canvas()
    bob = (0, -1, -1, 0, 0, -1, -1, 0, 0, 0)[step % 10]
    lean = (0, 1, 1, 1, 0, 1, 1, 1, 0, 0)[step % 10]
    poses = (LEGS_RUN_A, LEGS_RUN_B, LEGS_RUN_C, LEGS_RUN_D)
    wag = (0, -1, -1, 0, 1, 1, 0, -1, 0, 1)[step % 10]
    _base(canvas, lean, bob, poses[step % len(poses)], tail_dy=wag)
    if step % 2 == 0:
        canvas.blit([".Y.", "Y.Y"], dx=0, dy=19 + bob)
    return canvas


def frame_sitting(step: int, total: int) -> Canvas:
    """Seated idle: slow breathing plus an occasional blink."""
    canvas = Canvas()
    breathe = (0, 0, 1, 1, 1, 1, 1, 0, 0, 0)[step % 10]
    wag = (0, -1, -1, 0, 0, 1, 1, 0, -1, 0)[step % 10]
    _base(canvas, 0, 1 + breathe, LEGS_SIT, closed_eye=step in (4, 5), tail_dy=wag)
    return canvas


def frame_sleeping(step: int, total: int) -> Canvas:
    """Lying down with closed eyes and a rising Zzz.

    dy is kept small: the tucked-leg block reaches row 28, so a larger drop would
    clip the sprite against the bottom of the 30x30 canvas.
    """
    canvas = Canvas()
    breathe = 1 if math.sin(step / total * math.tau) > 0 else 0
    dy = 2 + breathe
    wag = (0, 0, 1, 1, 0, 0, -1, -1, 0, 0)[step % 10]
    _base(canvas, 0, dy, LEGS_SLEEP, arm=False, closed_eye=True, tail_dy=wag)
    rise = int(step * 0.8)
    canvas.blit(ZZZ_SMALL, dx=26, dy=max(0, 8 - rise))
    return canvas


def frame_break(step: int, total: int) -> Canvas:
    """Break prompt: hop and wave with a bright accent above the head."""
    canvas = Canvas()
    hop = (0, -1, -2, -3, -2, -1, 0, 0, -1, 0)[step % 10]
    wave = step % 4 < 2
    wag = (0, -1, -1, 0, 1, 1, 0, -1, 1, 0)[step % 10]
    canvas.blit(BODY, dy=hop)
    canvas.blit(TAIL_TIP, dx=TAIL_AT[0], dy=TAIL_AT[1] + hop + wag)
    canvas.blit(BELLY, dx=BELLY_AT[0], dy=BELLY_AT[1] + hop)
    canvas.blit(LEGS_STAND, dx=LEGS_AT_X, dy=LEGS_AT_Y + hop)
    canvas.blit(ARM, dx=ARM_AT[0], dy=ARM_AT[1] - (2 if wave else 0) + hop)
    if wave:
        canvas.blit(["Y", "Y", "Y", ".", "Y"], dx=28, dy=max(0, 2 + hop))
    else:
        canvas.blit([".Y.", "YYY", ".Y."], dx=27, dy=max(0, 3 + hop))
    return canvas


ACTIONS: dict[str, tuple] = {
    "running": (frame_running, 10, 90),
    "sitting": (frame_sitting, 10, 160),
    "sleeping": (frame_sleeping, 10, 200),
    "break": (frame_break, 10, 110),
}


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (maker, count, duration_ms) in ACTIONS.items():
        frames = [maker(step, count).to_image() for step in range(count)]

        frame_dir = OUT / "frames" / name
        frame_dir.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(frames):
            frame.save(frame_dir / f"{index:02d}.png", transparency=0)

        frames[0].save(
            OUT / f"{name}.gif",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            transparency=0,
            disposal=2,
            optimize=False,
        )

        sheet = Image.new("RGBA", (SIZE * count * SCALE, SIZE * SCALE), (24, 28, 38, 255))
        for index, frame in enumerate(frames):
            big = frame.convert("RGBA").resize(
                (SIZE * SCALE, SIZE * SCALE), Image.Resampling.NEAREST
            )
            sheet.paste(big, (index * SIZE * SCALE, 0), big)
        sheet.save(OUT / f"preview_{name}.png")
        print(f"{name}: {count} frames, {duration_ms} ms/frame")


if __name__ == "__main__":
    build()
