# -*- coding: utf-8 -*-
"""视频号账号首次扫码登录工具。

用法: python login.py --account health
  打开有头浏览器显示登录二维码，用户用微信扫码确认后，
  登录态保存到 storage/<account>.json，以后 publish.py 自动使用。

每个视频号（健康/科技/情感/影视）各跑一次。
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from channels import ChannelsPublisher, PLATFORM_HOME

BASE = os.path.dirname(os.path.abspath(__file__))


def load_accounts():
    with open(os.path.join(BASE, "accounts.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="视频号扫码登录（首次）")
    ap.add_argument("--account", required=True,
                    help="账号代号：health / tech / emotion / movie")
    ap.add_argument("--timeout", type=int, default=300,
                    help="等待扫码秒数，默认 300")
    args = ap.parse_args()

    accounts = load_accounts()
    valid = {v["account"] for v in accounts.values() if isinstance(v, dict)}
    if args.account not in valid:
        print(f"未知账号 {args.account}，可选：{sorted(valid)}")
        sys.exit(1)

    storage_path = os.path.join(BASE, "storage", f"{args.account}.json")
    if os.path.exists(storage_path):
        print(f"该账号已有登录态 {storage_path}，将覆盖重新登录。")

    print("=" * 50)
    print(f"正在打开浏览器，请用微信扫码登录【{args.account}】对应的视频号")
    print(f"等待 {args.timeout} 秒，扫码完成后自动保存")
    print("=" * 50)

    with ChannelsPublisher(storage_path, headless=False) as pub:
        page = pub._page
        page.goto(PLATFORM_HOME, wait_until="domcontentloaded", timeout=30000)
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            if pub.is_logged_in():
                pub.save_storage()
                print("登录成功，登录态已保存，以后可自动发布。")
                return
            time.sleep(3)
        print("超时未扫码，未保存。请重新运行 login.py。")
        sys.exit(2)


if __name__ == "__main__":
    main()
