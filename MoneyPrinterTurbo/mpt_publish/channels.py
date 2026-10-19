# -*- coding: utf-8 -*-
"""视频号助手（channels.weixin.qq.com）Playwright 发布器。

登录态：每个账号一份 storage state（cookies + localStorage），由 login.py
扫码登录后保存。发布时加载对应 state，无需再次扫码。
"""
import logging
import os
import time

from playwright.sync_api import sync_playwright

logger = logging.getLogger("channels")

PLATFORM_HOME = "https://channels.weixin.qq.com/platform"
POST_CREATE_URL = "https://channels.weixin.qq.com/platform/post/create"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


class ChannelsPublisher:
    def __init__(self, storage_path, headless=True):
        self.storage_path = storage_path
        self.headless = headless
        self._pw = None
        self._browser = None
        self._ctx = None
        self._page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        launch_kw = {"headless": self.headless}
        # 用本机 Chrome：指纹更接近真人，免去下载 Chromium
        if os.path.exists(CHROME_PATH):
            launch_kw["executable_path"] = CHROME_PATH
            launch_kw["args"] = ["--disable-blink-features=AutomationControlled"]
        self._browser = self._pw.chromium.launch(**launch_kw)
        ctx_kw = {}
        if os.path.exists(self.storage_path):
            ctx_kw["storage_state"] = self.storage_path
        self._ctx = self._browser.new_context(**ctx_kw)
        self._page = self._ctx.new_page()
        return self

    def __exit__(self, *args):
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()

    # ---------- 登录状态 ----------
    def is_logged_in(self, timeout=15000):
        """访问平台首页，判断是否已登录（未登录会跳到扫码页）。"""
        page = self._page
        page.goto(PLATFORM_HOME, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        url = page.url
        # 未登录：URL 含 login / qrcode，或页面出现扫码提示
        if "login" in url or "qrcode" in url:
            return False
        try:
            # 登录页通常有"微信扫码登录"文字；主页有左侧导航"内容管理"
            if page.get_by_text("微信扫码登录").count() > 0:
                return False
            if page.get_by_text("内容管理").count() > 0:
                return True
        except Exception:
            pass
        # 兜底：URL 仍在 platform 下即视为已登录
        return "channels.weixin.qq.com/platform" in url

    def check_login_state(self):
        """不刷新页面，只看当前状态（扫码等待轮询用，避免刷掉二维码）。

        返回: "qrcode"（还在扫码页）/ "select"（已扫码，出现选择视频号框）
              / "in"（已进入某视频号主页）/ "unknown"
        """
        page = self._page
        try:
            url = page.url
            if "login" in url or "qrcode" in url:
                return "qrcode"
            if page.get_by_text("选择视频号登录").count() > 0:
                return "select"
            if page.get_by_text("微信扫码登录").count() > 0:
                return "qrcode"
            if page.get_by_text("内容管理").count() > 0:
                return "in"
        except Exception:
            pass
        return "unknown"

    def save_storage(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        self._ctx.storage_state(path=self.storage_path)
        logger.info("登录态已保存: %s", self.storage_path)

    # ---------- 发布 ----------
    def publish_video(self, video_path, description, timeout_ms=600000):
        """上传视频、填描述、点发布。返回 True/False。"""
        page = self._page
        logger.info("打开发布页: %s", os.path.basename(video_path))
        page.goto(POST_CREATE_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # 1) 上传视频：找 file input（参考视频中为点击"+"区域触发的文件选择）
        uploaded = False
        for sel in [
            'input[type="file"][accept*="video"]',
            'input[type="file"]',
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.set_input_files(video_path)
                    uploaded = True
                    logger.info("已选择视频文件")
                    break
            except Exception as e:
                logger.debug("selector %s 失败: %s", sel, e)
        if not uploaded:
            logger.error("未找到视频上传入口")
            return False

        # 2) 等上传/转码完成：进度条消失且出现"发表"可点
        #    参考视频中上传时有百分比进度；转码完成后描述区可编辑
        try:
            page.wait_for_function(
                """() => {
                    const t = document.body.innerText;
                    // 上传中通常显示 xx% ；完成后消失
                    return !/%\\s*$/.test(t.split('\\n').find(l => /\\d+%/.test(l)) || '');
                }""",
                timeout=timeout_ms,
            )
        except Exception as e:
            logger.warning("等待上传完成超时: %s", e)
        page.wait_for_timeout(3000)

        # 3) 填描述
        filled = False
        for sel in [
            'textarea[placeholder*="描述"]',
            'textarea[placeholder*="说点什么"]',
            "textarea",
        ]:
            try:
                ta = page.locator(sel).first
                if ta.count() > 0 and ta.is_visible():
                    ta.click()
                    ta.fill(description)
                    filled = True
                    logger.info("已填写描述")
                    break
            except Exception as e:
                logger.debug("描述框 %s 失败: %s", sel, e)
        if not filled:
            logger.error("未找到描述输入框")
            return False

        # 4) 点发表
        published = False
        for sel in [
            'button:has-text("发表")',
            '[role="button"]:has-text("发表")',
        ]:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                    btn.click()
                    published = True
                    logger.info("已点击发表")
                    break
            except Exception as e:
                logger.debug("发表按钮 %s 失败: %s", sel, e)
        if not published:
            logger.error("未找到发表按钮")
            return False

        # 5) 确认：等待发表成功提示或跳到视频管理页
        page.wait_for_timeout(5000)
        try:
            page.wait_for_function(
                """() => {
                    const t = document.body.innerText;
                    return t.includes('发表成功') || t.includes('发布成功')
                        || window.location.href.includes('/post/list');
                }""",
                timeout=60000,
            )
            logger.info("发表成功确认")
            return True
        except Exception:
            # 没等到明确成功信号，截屏留证，视为未知
            shot = os.path.join(os.path.dirname(video_path), "publish_result.png")
            try:
                page.screenshot(path=shot)
                logger.warning("未确认发表成功，已截屏: %s", shot)
            except Exception:
                pass
            return False
