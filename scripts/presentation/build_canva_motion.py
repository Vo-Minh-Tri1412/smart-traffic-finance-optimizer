"""Render deterministic, silent algorithm visualizations for the Canva deck.

The clips illustrate process order only. They contain no measured traffic
volume, economic benefit, model performance, or actual map coordinates.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Giay_to" / "presentation_assets" / "diagrams"
WIDTH, HEIGHT = 900, 620
FPS, SECONDS = 12, 6
INK = "#29343B"
MUTED = "#62727C"
SKY = "#73C7EB"
SKY2 = "#BFEAF9"
PALE = "#ECF9FD"
WHITE = "#FFFFFF"
WARM = "#F5D6AF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def centered(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    message: str,
    size: int = 25,
    bold: bool = False,
    fill: str = INK,
) -> None:
    draw.text(xy, message, font=font(size, bold), fill=fill, anchor="mm")


def arrow(
    draw: ImageDraw.ImageDraw,
    a: tuple[int, int],
    b: tuple[int, int],
    color: str = INK,
    width: int = 4,
) -> None:
    draw.line([a, b], fill=color, width=width)
    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    length = 13
    for delta in (-0.55, 0.55):
        p = (
            int(b[0] - length * math.cos(angle + delta)),
            int(b[1] - length * math.sin(angle + delta)),
        )
        draw.line([p, b], fill=color, width=width)


def scene() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), PALE)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, 884, 604), radius=30, fill=WHITE, outline=SKY2, width=3)
    return image, draw


def car(draw: ImageDraw.ImageDraw, x: int, y: int, fill: str = SKY) -> None:
    draw.rounded_rectangle(
        (x - 31, y - 14, x + 31, y + 14), radius=11, fill=fill, outline=INK, width=3
    )
    for offset in (-18, 18):
        draw.ellipse((x + offset - 6, y + 12, x + offset + 6, y + 24), fill=INK)


def rl_frame(frame: int) -> Image.Image:
    image, draw = scene()
    t = frame / FPS
    stage = min(int(t / 1.5), 3)
    names = ["Quan sát", "Đề xuất", "Kiểm tra an toàn", "Đo kết quả"]
    centered(draw, (450, 77), "Một vòng quyết định của đèn", 31, True)

    points = [(135, 180), (765, 180), (765, 465), (135, 465)]
    labels = ["1", "2", "3", "4"]
    for i, (x, y) in enumerate(points):
        active = i == stage
        draw.ellipse(
            (x - 43, y - 43, x + 43, y + 43),
            fill=SKY2 if active else WHITE,
            outline=SKY if active else INK,
            width=5 if active else 3,
        )
        centered(draw, (x, y - 1), labels[i], 28, True)
        offset = -73 if i < 2 else 73
        centered(draw, (x, y + offset), names[i], 23, active, INK if active else MUTED)
    arrow(draw, (190, 180), (700, 180))
    arrow(draw, (765, 235), (765, 407))
    arrow(draw, (705, 465), (195, 465))
    arrow(draw, (135, 407), (135, 235))

    draw.ellipse((327, 202, 573, 448), fill=PALE, outline=SKY, width=4)
    draw.line((346, 325, 554, 325), fill=SKY2, width=40)
    draw.line((450, 221, 450, 429), fill=SKY2, width=40)
    draw.line((346, 325, 554, 325), fill=INK, width=3)
    draw.line((450, 221, 450, 429), fill=INK, width=3)
    motion = int(95 * (t % 1.5) / 1.5)
    car(draw, 375 + motion, 305)
    car(draw, 510 - motion // 2, 344, WHITE)
    draw.rounded_rectangle((469, 225, 501, 305), radius=12, fill=WHITE, outline=INK, width=3)
    draw.ellipse((479, 235, 491, 247), fill=WARM if stage < 2 else WHITE, outline=INK, width=2)
    draw.ellipse((479, 258, 491, 270), fill=SKY if stage >= 2 else WHITE, outline=INK, width=2)
    draw.ellipse((479, 281, 491, 293), fill=WHITE, outline=INK, width=2)
    centered(draw, (450, 559), names[stage], 26, True)
    return image


def qubo_frame(frame: int) -> Image.Image:
    image, draw = scene()
    t = frame / FPS
    stage = min(int(t / 1.5), 3)
    names = ["Hồ sơ tuyến", "Tạo hệ số", "Giải bài toán nhỏ", "Chạy lại SUMO"]
    centered(draw, (450, 73), "Từ dữ liệu đến danh mục kiểm tra", 30, True)
    centers = [115, 335, 560, 785]
    draw.line((115, 312, 785, 312), fill=SKY2, width=18)
    arrow(draw, (115, 312), (785, 312))
    for i, x in enumerate(centers):
        active = i == stage
        draw.ellipse(
            (x - 67, 245, x + 67, 379),
            fill=PALE if active else WHITE,
            outline=SKY if active else INK,
            width=5 if active else 3,
        )
        centered(draw, (x, 430), names[i], 23, active, INK if active else MUTED)

    # Source document: evidence-bearing OD profile, without invented values.
    draw.rounded_rectangle((78, 275, 153, 350), radius=7, fill=WHITE, outline=INK, width=3)
    for y, width in [(292, 49), (312, 39), (332, 54)]:
        draw.line((89, y, 89 + width, y), fill=SKY if y == 292 else INK, width=3)
    # QUBO coefficient matrix.
    for row in range(2):
        for col in range(2):
            x, y = 306 + col * 31, 283 + row * 31
            draw.rounded_rectangle(
                (x, y, x + 23, y + 23),
                radius=4,
                fill=SKY2 if row == col else WHITE,
                outline=INK,
                width=2,
            )
    # Exact small-problem search tree.
    draw.line((560, 281, 560, 309), fill=INK, width=3)
    draw.line((560, 309, 530, 341), fill=INK, width=3)
    draw.line((560, 309, 590, 341), fill=INK, width=3)
    for x in (530, 590):
        draw.ellipse((x - 8, 333, x + 8, 349), fill=SKY2, outline=INK, width=2)
    # Same SUMO map used for checking the chosen portfolio.
    draw.line((742, 312, 828, 312), fill=SKY2, width=20)
    draw.line((785, 269, 785, 355), fill=SKY2, width=20)
    draw.line((742, 312, 828, 312), fill=INK, width=2)
    draw.line((785, 269, 785, 355), fill=INK, width=2)
    car(draw, 773 + int(19 * math.sin(2 * math.pi * t / 6)), 295)
    draw.line((106, 510, 795, 510), fill=SKY, width=4)
    centered(draw, (450, 552), "Hệ số tác động trên map vẫn cần được đo", 22, False, MUTED)
    return image


def encode(name: str, render) -> None:
    output = OUT / name
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WIDTH}x{HEIGHT}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(output),
    ]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        assert process.stdin is not None
        for frame in range(FPS * SECONDS):
            image = render(frame)
            if frame == 0:
                image.save(output.with_suffix(".poster.png"))
            process.stdin.write(image.tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError(f"ffmpeg failed for {name}")
    print(output)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    encode("slide07-rl-control-loop.mp4", rl_frame)
    encode("slide10-qubo-stack.mp4", qubo_frame)
