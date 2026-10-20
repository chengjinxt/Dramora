# -*- coding: utf-8 -*-
"""按 Pexels 视频 ID 下载竖屏素材（每日选题定向抓素材用，档1）。

用法:
  python fetch_clips.py --ids 1234567,2345678 --outdir <目录> --prefix topic

下载方式（实测最可靠）：对裸链接 https://www.pexels.com/download/video/<id>/
做 HEAD，跟随重定向拿真实文件地址再下载（带 fps/尺寸参数的链接部分视频 404）。
下载后 ffprobe 校验竖屏，非竖屏删除。已有且 >100KB 的文件跳过。
标准输出最后一行是 JSON 数组：成功的文件绝对路径列表。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

FFPROBE_CANDIDATES = ["ffprobe", r"D:\DevTools\FFmpeg\bin\ffprobe.exe"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def find_ffprobe():
    for c in FFPROBE_CANDIDATES:
        try:
            subprocess.run([c, "-version"], capture_output=True, check=True)
            return c
        except Exception:
            continue
    return None


def real_url(vid):
    req = urllib.request.Request(
        "https://www.pexels.com/download/video/%s/" % vid, method="HEAD", headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl()


def download(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)


def probe_wh(ffprobe, path):
    out = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    parts = out.stdout.strip().split(",")
    if len(parts) >= 2:
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None
    return None


def main():
    ap = argparse.ArgumentParser(description="按 Pexels ID 下载竖屏素材")
    ap.add_argument("--ids", required=True, help="逗号分隔的 Pexels 视频 ID")
    ap.add_argument("--outdir", required=True, help="输出目录")
    ap.add_argument("--prefix", default="topic", help="文件名前缀，默认 topic")
    args = ap.parse_args()

    ffprobe = find_ffprobe()
    os.makedirs(args.outdir, exist_ok=True)
    ok = []
    idx = 1
    for vid in [s.strip() for s in args.ids.split(",") if s.strip()]:
        dest = os.path.join(args.outdir, "%s_%02d.mp4" % (args.prefix, idx))
        idx += 1
        if os.path.exists(dest) and os.path.getsize(dest) > 100 * 1024:
            ok.append(os.path.abspath(dest))
            continue
        try:
            download(real_url(vid), dest)
        except Exception as e:
            print("FAIL %s: %s" % (vid, e), file=sys.stderr)
            if os.path.exists(dest):
                os.remove(dest)
            continue
        if ffprobe:
            wh = probe_wh(ffprobe, dest)
            if not wh or wh[1] <= wh[0]:
                print("FAIL %s: not portrait %s" % (vid, wh), file=sys.stderr)
                os.remove(dest)
                continue
        ok.append(os.path.abspath(dest))
    print(json.dumps(ok, ensure_ascii=False))


if __name__ == "__main__":
    main()
