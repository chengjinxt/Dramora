# -*- coding: utf-8 -*-
"""生成标题卡 PNG（2026-10-22 改版）。
用法: python make_title_card.py --title "标题文字" --output title.png
画布 1080x1920 透明底。样式按用户给的爆款封面参考：黄色粗体大字 +
黑色描边 + 柔和投影，无底条；与字幕条（黄底黑字）靠形态区分。
长标题自动断成两行（优先在标点处断），字号自适应居中显示。
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
YELLOW = (255, 230, 0, 255)   # 与字幕条同色 #FFE600
BLACK = (0, 0, 0, 255)
MAX_TEXT_W = 980              # 单行文字最大宽度（含描边）
FONT_SIZE_START = 104
FONT_SIZE_MIN = 54
LINE_SPACING = 1.28           # 行距倍数
SPLIT_ABOVE = 10              # 超过这个字数断成两行
PUNCTS = "，。！？；、,.!?;"

FONT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "MoneyPrinterTurbo", "resource", "fonts",
)
# 优先黑体粗体，fallback 顺序
FONT_CANDIDATES = ["MicrosoftYaHeiBold.ttc", "STHeitiMedium.ttc", "MicrosoftYaHeiNormal.ttc"]


def find_font():
    for name in FONT_CANDIDATES:
        p = os.path.join(FONT_DIR, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError("no Chinese font found in %s" % FONT_DIR)


def split_lines(title):
    """长标题断成两行：优先在靠近中点的标点后断开，否则对半断。"""
    if len(title) <= SPLIT_ABOVE:
        return [title]
    best = None
    for i, ch in enumerate(title):
        if ch in PUNCTS and 0 < i < len(title) - 1:
            a, b = title[:i + 1], title[i + 1:]
            score = abs(len(a) - len(b))
            if best is None or score < best[0]:
                best = (score, a, b)
    if best:
        return [best[1], best[2]]
    mid = (len(title) + 1) // 2
    return [title[:mid], title[mid:]]


def line_size(draw, text, font, stroke):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True, help="标题文字")
    ap.add_argument("--output", required=True, help="输出 PNG 路径")
    args = ap.parse_args()

    title = args.title.strip()
    if not title:
        print("empty title", file=sys.stderr)
        sys.exit(1)

    font_path = find_font()
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    lines = split_lines(title)

    # 字号自适应：从大到小，直到每一行都放进 MAX_TEXT_W
    size = FONT_SIZE_START
    while size > FONT_SIZE_MIN:
        font = ImageFont.truetype(font_path, size)
        stroke = max(4, size // 11)
        if all(line_size(draw, ln, font, stroke)[0] <= MAX_TEXT_W for ln in lines):
            break
        size -= 4
    font = ImageFont.truetype(font_path, size)
    stroke = max(4, size // 11)

    sizes = [line_size(draw, ln, font, stroke) for ln in lines]
    line_h = int(size * LINE_SPACING)
    total_h = line_h * (len(lines) - 1) + sizes[-1][1]
    y_top = (H - total_h) // 2

    # 柔和投影层：同字形黑色版向下偏移后高斯模糊
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    for i, ln in enumerate(lines):
        cy = y_top + i * line_h + sizes[i][1] // 2
        sdraw.text((W // 2, cy + 7), ln, font=font, fill=(0, 0, 0, 150),
                   anchor="mm", stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))

    draw = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        cy = y_top + i * line_h + sizes[i][1] // 2
        draw.text((W // 2, cy), ln, font=font, fill=YELLOW, anchor="mm",
                  stroke_width=stroke, stroke_fill=BLACK)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    img.save(args.output, "PNG")
    print("saved %s (font=%s size=%d lines=%d)" % (
        args.output, os.path.basename(font_path), size, len(lines)))


if __name__ == "__main__":
    main()
