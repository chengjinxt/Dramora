# -*- coding: utf-8 -*-
"""每日视频自动发布到视频号。

用法:
  python publish.py --date 2026-10-20
      发布 mpt_videos/2026-10-20/ 下全部 mp4，按文件名类别前缀
      （健康_/科技_/情感_/影视_）路由到 accounts.json 对应的视频号。
      描述 = 去掉类别前缀的标题 + " " + hashtag
      例：健康_熬夜的代价，身体比你先知道.mp4
          -> "熬夜的代价，身体比你先知道 #健康"

  python publish.py --retry
      补发：重试 publish_log.json 里未成功的条目。

首次某账号未登录（没扫过码）时，该账号视频记为 need_login 并跳过，
不阻塞其他账号；用户扫码后用 --retry 补发。
"""
import argparse
import glob
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from channels import ChannelsPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("publish")

BASE = os.path.dirname(os.path.abspath(__file__))
MPT_ROOT = os.path.dirname(BASE)  # MoneyPrinterTurbo/
VIDEOS_ROOT = os.path.join(MPT_ROOT, "mpt_videos")
LOG_PATH = os.path.join(BASE, "publish_log.json")


def load_accounts():
    with open(os.path.join(BASE, "accounts.json"), encoding="utf-8") as f:
        return json.load(f)


def load_log():
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_log(log):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def parse_video(filename):
    """健康_标题.mp4 -> (类别, 标题)。"""
    stem = os.path.splitext(os.path.basename(filename))[0]
    if "_" in stem:
        cat, title = stem.split("_", 1)
        return cat, title
    return None, stem


def build_description(title, hashtag):
    return f"{title} {hashtag}".strip()


def publish_one(video_path, category, accounts):
    cfg = accounts.get(category)
    if not cfg:
        return False, f"accounts.json 未配置类别 {category}"
    storage_path = os.path.join(BASE, "storage", f"{cfg['account']}.json")
    title = parse_video(video_path)[1]
    description = build_description(title, cfg.get("hashtag", ""))

    with ChannelsPublisher(storage_path, headless=True) as pub:
        if not pub.is_logged_in():
            return None, "need_login"  # 特殊标记：需扫码
        ok = pub.publish_video(video_path, description)
        return ok, None if ok else "publish_failed"


def run_date(date_str):
    accounts = load_accounts()
    log = load_log()
    day_dir = os.path.join(VIDEOS_ROOT, date_str)
    videos = sorted(glob.glob(os.path.join(day_dir, "*.mp4")))
    if not videos:
        print(f"{day_dir} 下没有 mp4")
        return

    summary = []
    for vp in videos:
        if log.get(vp, {}).get("status") == "published":
            summary.append(f"跳过已发布: {os.path.basename(vp)}")
            continue
        category, _ = parse_video(vp)
        try:
            ok, err = publish_one(vp, category, accounts)
        except Exception as e:
            ok, err = False, f"exception: {e}"
        entry = {
            "status": "published" if ok else ("need_login" if err == "need_login" else "failed"),
            "account": (accounts.get(category) or {}).get("account"),
            "time": datetime.now().isoformat(timespec="seconds"),
            "error": err,
        }
        log[vp] = entry
        save_log(log)
        summary.append(
            f"{'成功' if ok else '失败(' + str(err) + ')'}: {os.path.basename(vp)}"
        )
        logger.info(summary[-1])

    print("\n".join(summary))
    need_login = [k for k, v in log.items() if v.get("status") == "need_login"]
    if need_login:
        print(f"\n{len(need_login)} 条待扫码后补发：先 python login.py --account <代号>，再 python publish.py --retry")


def run_retry():
    accounts = load_accounts()
    log = load_log()
    pending = {k: v for k, v in log.items()
               if v.get("status") in ("failed", "need_login") and os.path.exists(k)}
    if not pending:
        print("没有待补发的视频")
        return
    print(f"待补发 {len(pending)} 条")
    for vp in sorted(pending):
        category, _ = parse_video(vp)
        try:
            ok, err = publish_one(vp, category, accounts)
        except Exception as e:
            ok, err = False, f"exception: {e}"
        log[vp] = {
            "status": "published" if ok else ("need_login" if err == "need_login" else "failed"),
            "account": (accounts.get(category) or {}).get("account"),
            "time": datetime.now().isoformat(timespec="seconds"),
            "error": err,
        }
        save_log(log)
        print(f"{'成功' if ok else '失败(' + str(err) + ')'}: {os.path.basename(vp)}")


def run_single(video_path):
    accounts = load_accounts()
    log = load_log()
    if not os.path.exists(video_path):
        print(f"文件不存在: {video_path}")
        return
    category, _ = parse_video(video_path)
    try:
        ok, err = publish_one(video_path, category, accounts)
    except Exception as e:
        ok, err = False, f"exception: {e}"
    log[video_path] = {
        "status": "published" if ok else ("need_login" if err == "need_login" else "failed"),
        "account": (accounts.get(category) or {}).get("account"),
        "time": datetime.now().isoformat(timespec="seconds"),
        "error": err,
    }
    save_log(log)
    print(f"{'成功' if ok else '失败(' + str(err) + ')'}: {os.path.basename(video_path)}")


def main():
    ap = argparse.ArgumentParser(description="视频号自动发布")
    ap.add_argument("--date", help="发布哪天目录 YYYY-MM-DD，默认今天")
    ap.add_argument("--retry", action="store_true", help="补发失败/待扫码条目")
    ap.add_argument("--file", help="只发单个视频文件（测试用），传完整路径")
    args = ap.parse_args()

    if args.retry:
        run_retry()
    elif args.file:
        run_single(args.file)
    else:
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        run_date(date_str)


if __name__ == "__main__":
    main()
