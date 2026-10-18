# -*- coding: utf-8 -*-
"""生成频道风格（黄底黑字圆角条，参考成进学堂字幕条）的标题卡 PNG。
用法: python make_title_card.py --title "标题文字" --output title.png
画布 1080x1920 透明底，黄色圆角条居中，黑色粗体字。
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
YELLOW = (255, 230, 0, 255)   # 亮黄，贴近频道字幕条
BLACK = (0, 0, 0, 255)
MAX_TEXT_W = 920              # 文字最大宽度
FONT_SIZE_START = 72
FONT_SIZE_MIN = 40
PAD_X = 44                    # 条内左右留白
PAD_Y = 30                    # 条内上下留白
RADIUS = 30                   # 圆角半径

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


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
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

    # 字号自适应：从大到小直到放进 MAX_TEXT_W
    size = FONT_SIZE_START
    font = ImageFont.truetype(font_path, size)
    tw, th = text_size(draw, title, font)
    while tw > MAX_TEXT_W and size > FONT_SIZE_MIN:
        size -= 4
        font = ImageFont.truetype(font_path, size)
        tw, th = text_size(draw, title, font)

    bar_w = tw + PAD_X * 2
    bar_h = th + PAD_Y * 2
    x0 = (W - bar_w) // 2
    y0 = (H - bar_h) // 2
    x1 = x0 + bar_w
    y1 = y0 + bar_h

    draw.rounded_rectangle([x0, y0, x1, y1], radius=RADIUS, fill=YELLOW)
    # 文字在条内居中（用 anchor 避免基线偏移）
    draw.text((W // 2, H // 2), title, font=font, fill=BLACK, anchor="mm")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    img.save(args.output, "PNG")
    print("saved %s (font=%s size=%d)" % (args.output, os.path.basename(font_path), size))


if __name__ == "__main__":
    main()
