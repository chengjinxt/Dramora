# -*- coding: utf-8 -*-
"""素材池相关性打分（档2）：按关键词对 clip_tags.json 打分排序。

用法:
  python score_materials.py --pool tech --keywords 笔记本电脑,AI,芯片,办公 --count 10 \
      --materials-root E:\\...\\mpt_materials

规则:
  - 关键词命中标签 +3/个，命中描述 +2/个（子串双向匹配，如关键词“电脑”命中标签“笔记本电脑”）；
  - 12 天内用过的（usage.json）直接排除；排除后不够 count 时，按分数补回（仍按分数序）；
  - 排序：分数降序，其次上次使用日期升序（越久没用越优先，未用过最优先）。
标准输出：JSON 数组（绝对路径，按优先级排序）。
"""
import argparse
import json
import os
from datetime import date, timedelta

EXCLUDE_DAYS = 12


def score_clip(keywords, tags, desc):
    s = 0
    for kw in keywords:
        if not kw:
            continue
        for t in tags:
            if kw in t or t in kw:
                s += 3
                break
        if kw in desc:
            s += 2
    return s


def main():
    ap = argparse.ArgumentParser(description="素材池相关性打分")
    ap.add_argument("--pool", required=True, help="素材池名 walk/tech/emotion/movie")
    ap.add_argument("--keywords", required=True, help="逗号分隔的中文关键词（标题+文案提炼）")
    ap.add_argument("--count", type=int, default=10, help="返回条数，默认 10")
    ap.add_argument("--materials-root", required=True, help="mpt_materials 目录")
    args = ap.parse_args()

    with open(os.path.join(args.materials_root, "clip_tags.json"), encoding="utf-8-sig") as f:
        all_tags = json.load(f)
    usage = {}
    up = os.path.join(args.materials_root, "usage.json")
    if os.path.exists(up):
        with open(up, encoding="utf-8-sig") as f:
            usage = json.load(f)

    pool_tags = all_tags.get(args.pool, {})
    pool_usage = usage.get(args.pool, {})
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    cutoff = (date.today() - timedelta(days=EXCLUDE_DAYS)).isoformat()

    rows = []
    for fname, meta in pool_tags.items():
        last = pool_usage.get(fname, "")
        rows.append({
            "file": fname,
            "score": score_clip(keywords, meta.get("tags", []), meta.get("desc", "")),
            "last": last,
            "fresh": (not last) or (last < cutoff),
        })
    rows.sort(key=lambda r: (-r["score"], r["last"] or "0000-00-00"))

    picked = [r for r in rows if r["fresh"]][:args.count]
    if len(picked) < args.count:
        picked_names = {r["file"] for r in picked}
        picked += [r for r in rows if r["file"] not in picked_names][:args.count - len(picked)]

    pool_dir = os.path.join(args.materials_root, args.pool)
    print(json.dumps([os.path.join(pool_dir, r["file"]) for r in picked], ensure_ascii=False))


if __name__ == "__main__":
    main()
