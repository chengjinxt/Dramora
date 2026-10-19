# -*- coding: utf-8 -*-
"""视频号账号首次扫码登录工具。

用法: python login.py --account health
  打开有头浏览器显示登录二维码，用户用微信扫码确认后，
  脚本列出该微信下的视频号，用户按编号选择要绑定的那一个，
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


def find_channel_items(page):
    """在选择视频号页面找候选项，返回 [(name, locator), ...]。"""
    items = []
    # 策略1：找“进入/管理”类按钮，其容器即为一个视频号条目
    for btn_text in ["进入视频号", "去管理", "进入", "切换"]:
        try:
            btns = page.get_by_text(btn_text, exact=False).all()
            for b in btns:
                try:
                    if not b.is_visible():
                        continue
                    # 取按钮的祖先容器文本作为名称
                    container = b.locator("xpath=ancestor::*[self::li or self::div][.//img][1]")
                    name = ""
                    if container.count() > 0:
                        name = container.first.inner_text().strip().split("\n")[0]
                    if not name:
                        name = b.inner_text().strip()
                    items.append((name or btn_text, b))
                except Exception:
                    continue
        except Exception:
            continue
        if items:
            break
    # 策略2：找带头像的选择卡片
    if not items:
        try:
            cards = page.locator("div:has(img)").all()
            seen = set()
            for c in cards:
                try:
                    if not c.is_visible():
                        continue
                    t = c.inner_text().strip()
                    if t and len(t) < 60 and t not in seen:
                        seen.add(t)
                        items.append((t.split("\n")[0], c))
                except Exception:
                    continue
        except Exception:
            pass
    # 去重（按名称）
    uniq, seen_names = [], set()
    for name, loc in items:
        if name not in seen_names:
            seen_names.add(name)
            uniq.append((name, loc))
    return uniq


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
        deadline = time.time() + args.timeout
        logged_in = False
        while time.time() < deadline:
            if pub.is_logged_in():
                logged_in = True
                break
            time.sleep(3)
        if not logged_in:
            print("超时未扫码，未保存。请重新运行 login.py。")
            sys.exit(2)

        print("扫码成功，等页面加载完（多视频号选择框要过一会儿才出来）...")
        time.sleep(12)

        items = find_channel_items(page)
        if len(items) > 1:
            print("=" * 60)
            print("检测到该微信下有 %d 个视频号，请选择要绑定的：" % len(items))
            for i, (name, _) in enumerate(items, 1):
                print("  %d. %s" % (i, name))
            print("=" * 60)
            choice = 0
            while choice < 1 or choice > len(items):
                try:
                    choice = int(input("请输入编号 [1-%d]：" % len(items)).strip())
                except (ValueError, EOFError):
                    choice = 0
            name, loc = items[choice - 1]
            print("正在进入【%s】..." % name)
            try:
                loc.click()
            except Exception as e:
                print("自动点击失败（%s），请在浏览器里手动点选该视频号后按回车。" % e)
                try:
                    input("手动选好后按回车...")
                except EOFError:
                    pass
            time.sleep(5)
        elif len(items) == 1:
            print("只检测到 1 个视频号【%s】，直接进入。" % items[0][0])
            try:
                items[0][1].click()
                time.sleep(5)
            except Exception:
                pass
        else:
            print("未自动识别到视频号选择框，请在浏览器里确认已进入正确的账号主页，")
            try:
                input("确认后按回车...")
            except EOFError:
                pass

        pub.save_storage()
        print("登录态已保存，以后可自动发布。")


if __name__ == "__main__":
    main()
