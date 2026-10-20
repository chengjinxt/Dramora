# -*- coding: utf-8 -*-
"""把海报/剧照图片转成 1080x1920 竖屏动态片段（档3）。

效果：原图居中完整显示，背景用同一张图放大虚化填充，两者合成后
整体做缓慢推近（Ken Burns 式），避免静态图片的死板感。

用法:
  python make_poster_clip.py --image poster.jpg --out poster_clip.mp4 --duration 8
"""
import argparse
import os
import subprocess
import sys

FFMPEG_CANDIDATES = ["ffmpeg", r"D:\DevTools\FFmpeg\bin\ffmpeg.exe"]
W, H, FPS = 1080, 1920, 30


def find_ffmpeg():
    for c in FFMPEG_CANDIDATES:
        try:
            subprocess.run([c, "-version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description="海报/剧照图片转竖屏动态片段")
    ap.add_argument("--image", required=True, help="图片路径（jpg/png/webp）")
    ap.add_argument("--out", required=True, help="输出 mp4 路径")
    ap.add_argument("--duration", type=int, default=8, help="时长秒，默认 8")
    args = ap.parse_args()

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ffmpeg not found", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.image):
        print("image not found: %s" % args.image, file=sys.stderr)
        sys.exit(1)

    frames = args.duration * FPS
    # zoompan: z 每帧递增（zoom 变量是上一帧缩放值），总增幅约 0.12
    inc = 0.12 / frames
    filt = (
        "[0:v]split=2[a][b];"
        "[a]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,gblur=sigma=40[bg];"
        "[b]scale=%d:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[comp];"
        "[comp]zoompan=z='min(zoom+%.6f,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d=%d:s=%dx%d:fps=%d,format=yuv420p[v]"
        % (W, H, W, H, W - 80, inc, frames, W, H, FPS)
    )
    cmd = [ffmpeg, "-y", "-i", args.image,
           "-filter_complex", filt, "-map", "[v]",
           "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
           "-an", args.out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        sys.exit(1)
    print(os.path.abspath(args.out))


if __name__ == "__main__":
    main()
