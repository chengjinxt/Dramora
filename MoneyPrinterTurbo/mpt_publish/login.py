# -*- coding: utf-8 -*-
"""视频号账号首次扫码登录工具。

用法: python login.py --account health
  打开有头浏览器显示登录二维码，用户用微信扫码确认后，
  等“选择视频号登录”框出来，在浏览器里手动点进正确的视频号，
  回车确认后登录态保存到 storage/<account>.json，以后 publish.py 自动使用。

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
        print("未知账号 %s，可选：%s" % (args.account, sorted(valid)))
        sys.exit(1)

    storage_path = os.path.join(BASE, "storage", "%s.json" % args.account)
    if os.path.exists(storage_path):
        print("该账号已有登录态 %s，本次将覆盖重新登录。" % storage_path)

    print("=" * 60)
    print("正在打开浏览器，请用微信扫码登录【%s】对应的视频号" % args.account)
    print("等待 %d 秒" % args.timeout)
    print("=" * 60)

    with ChannelsPublisher(storage_path, headless=False) as pub:
        page = pub._page
        page.goto(PLATFORM_HOME, wait_until="domcontentloaded", timeout=30000)
        # 轮询只看页面状态，不刷新（刷新会刷掉二维码）
        deadline = time.time() + args.timeout
        scanned = False
        while time.time() < deadline:
            state = pub.check_login_state()
            if state in ("select", "in"):
                scanned = True
                break
            time.sleep(3)
        if not scanned:
            print("超时未扫码，未保存。请重新运行 login.py。")
            sys.exit(2)

        print("扫码成功，等“选择视频号登录”框完全出来（要过一会儿）...")
        time.sleep(8)
        print("=" * 60)
        print("请在浏览器里的“选择视频号登录”框中，手动点进正确的视频号，")
        print("确认进入该视频号的主页后，回到这里按回车，保存登录态。")
        print("=" * 60)
        try:
            input("点选好视频号并进入主页后，按回车...")
        except EOFError:
            pass
        pub.save_storage()
        print("登录态已保存，以后可自动发布。")


if __name__ == "__main__":
    main()
