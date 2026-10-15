## 注意事项

- 每次改动完成后，都必须创建一个对应的 Git commit，以便后续追踪和回滚。
- 每次改动后，都必须编写或更新相关测试，并在交付给用户前，确保所有测试和验证全部通过。
- 开发软件及工具不要安装到C盘，可以统一安装到 D:\DevTools 

## 目录结构

Dramora 是视频 / AI 短剧相关项目的统一仓库，每个项目自包含在独立子目录中：

- `MoneyPrinterTurbo/` — 每日 AI 短视频生产项目（MoneyPrinterTurbo 本地免费链路）
  - `MoneyPrinterTurbo/` — 上游开源项目源码。官方 `.git` 已移除，由本仓库统一管理；上游有较大更新时再手动同步改动过来。
  - `mpt_materials/` — 素材与编排脚本：`walk/`（健康类素材）、`tech/`（科技类素材）、`emotion/`（情感类素材）、`daily_gen.ps1`（批量生成编排脚本，UTF-8 BOM 编码）、`topics_健康.txt`（健康选题轮换清单）、`daily/YYYY-MM-DD/`（按日文案与 manifest）
  - `mpt_videos/` — 成片按日期归档：`YYYY-MM-DD/类别_标题.mp4`（生成产物，不提交到 git）
  - `实测运行手册.md` — 本机实测运行手册
