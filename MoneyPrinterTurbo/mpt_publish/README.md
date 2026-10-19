# mpt_publish — 视频号自动发布

每天生成的 4 条视频，按类别自动发布到 4 个视频号。

## 账号与类别映射（accounts.json）

| 类别 | 账号代号 | 话题标签 |
|------|----------|----------|
| 健康 | health | #健康 |
| 科技 | tech | #科技 |
| 情感 | emotion | #情感 |
| 影视 | movie | #影视解说 |

描述格式：`标题 #标签`（去掉文件名中的 `类别_` 前缀）。
例：`健康_熬夜的代价，身体比你先知道.mp4` → `熬夜的代价，身体比你先知道 #健康`

## 首次使用：扫码登录（每个账号一次）

```powershell
cd E:\PerSourceCodeStore\github\chengjinxt\Dramora\MoneyPrinterTurbo\mpt_publish
..\MoneyPrinterTurbo\.venv\Scripts\python.exe login.py --account health
..\MoneyPrinterTurbo\.venv\Scripts\python.exe login.py --account tech
..\MoneyPrinterTurbo\.venv\Scripts\python.exe login.py --account emotion
..\MoneyPrinterTurbo\.venv\Scripts\python.exe login.py --account movie
```

打开有头浏览器显示二维码，用微信扫码。登录态存到 `storage/<代号>.json`
（已 gitignore，绝不提交）。

## 每日发布

```powershell
..\MoneyPrinterTurbo\.venv\Scripts\python.exe publish.py --date 2026-10-20
```

扫描 `mpt_videos/<date>/` 下 mp4，按类别路由到对应账号发布。
已发布的不重复发（publish_log.json 记录状态，也已 gitignore）。

## 补发

某账号没扫码时，其视频记为 `need_login` 并跳过，不阻塞其他账号。
扫码后补发：

```powershell
..\MoneyPrinterTurbo\.venv\Scripts\python.exe publish.py --retry
```

## 技术说明

- Playwright + 本机 Chrome，操作视频号助手网页版（channels.weixin.qq.com）
- 视频号无官方发布 API，只能网页自动化
- 登录态过期时 publish.py 会检测到并标记 need_login，重新跑 login.py 即可
