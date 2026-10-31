# wechat-sales-copilot

给**你自己的 Mac 版个人微信**用的销售副驾，做成 Claude Code 技能包。

它把通讯录整理成一张潜客表，用你的口吻给每个人单独起草消息，你批准过的才会发，按真人节奏一条一条发出去，再告诉你谁回了。
它像人一样**从外面**操作官方的 Mac 版微信：截屏后用苹果系统自带的文字识别读屏幕，用模拟键盘鼠标操作。
不 hook、不注入、不重签名、不模拟协议、不解密微信数据库。

[English](README.md)

> **状态：v0.1，早期版本。**在 Mac 版微信 4.1.13 和 4.1.15 的**英文界面**上用过。**中文界面**（4.1.15）上发消息、
> 搜索、文件传输助手已实测；通讯录导出和名片读取还没测（界面文字表在 `wxmac/ui_strings.py`，欢迎反馈实际看到的字样）。
> 只支持 macOS 13 及以上。

## 能做什么

| 技能 | 你说 | 它做 |
|---|---|---|
| `wechat-setup` | 「帮我装好微信技能」「微信体检」 | 编译工具、查权限、写人设、调窗口、给文件传输助手发测试 |
| `wechat-contacts` | 「我微信里谁可能是客户？」 | 翻「通讯录管理」逐行读，给每人分类（潜客、客户、投资人……A/B/C 级），打开重点潜客的名片补信息，导出 Excel。只读。 |
| `wechat-outreach` | 「给加了没聊过的人都介绍一下我」 | 挑出该发的人，逐人起草，你批准，后台按节奏一条一条发 |
| `wechat-send` | 「把 deck 发给 Wren」 | 给一个会话发一条文字、图片或文件，屏幕上逐步核对，先演练 |
| `wechat-inbox` | 「谁回我了？」 | 从 macOS 通知记录里读微信通知；不点开会话，未读标记不动 |
| `wechat-ops` | 「微信窗口不对」 | 窗口、锁屏、掉线、微信升级之后 |

起草和分类默认由 Claude Code 自己来做，不需要 API key：脚本写出任务文件，Claude 写草稿，脚本再读回去。
要无人值守时，可以在 `config.toml` 里改成直接调 Anthropic API。

## 一条消息是怎么发出去的

1. 等你离开键盘 30 秒；锁屏就不动。
2. 把微信调到前面，搜名字，**只点聊天分区下的结果**（绝不点「网络搜索结果」）。
3. 聊天标题必须是**这个人**：同名的群一律不发。
4. 粘贴正文，点「发送」，再回读聊天区确认字已经在上面；然后发可选的图片或文件。
5. 还原你的剪贴板和你正在用的 App，结果记进台账。

任何一步对不上，都在点发送之前停下。在真号上踩过的坑（文字识别认错字、会话弹成小窗、「发送」按钮被读成「① Send」、
网络搜索里的同名结果……）都写在 [docs/pitfalls.md](docs/pitfalls.md)。

## 默认值偏保守

| 设置 | 默认 |
|---|---|
| 每天上限 | 40 条 |
| 每条间隔 | 60–180 秒，每 15–25 条歇 5–15 分钟 |
| 时段 | 09:00–21:00 |
| 批准 | 每条草稿都要你批准才能发 |
| 对象 | 只发个人，一次一个；不发群 |
| 不重复 | 每次发送前查台账，崩溃重启后也一样 |
| 退订 | 回复里出现「别再发」「stop」等词，永久不再发 |
| 微信警告 | 出现针对你账号的任何警告，暂停 24 小时 |

全部在 `config.example.toml` 里。

## 安装

在 Claude Code（2.1.275 以上）里一步装好：

```
/plugin install wechat-sales-copilot --marketplace Canlah-AI/wechat-sales-copilot
```

然后跟 Claude 说「帮我装好微信技能」。手动安装：

```bash
git clone https://github.com/Canlah-AI/wechat-sales-copilot && cd wechat-sales-copilot
./install.sh                 # 编译 bin/wxctl 和 bin/ocr（需要 Xcode 命令行工具），需要 Python 3.11+
python3 -m wxmac.doctor      # 告诉你缺哪个权限、哪项设置
```

然后在「系统设置 → 隐私与安全性」里给你的终端 App 打开**辅助功能**和**录屏**，想读回复的话再开**完全磁盘访问**。
在 `~/Library/Application Support/wechat-sales-copilot/config.toml` 里填好 `[persona]`。


## 正确用法

- **只用在你自己的号上，只发给认识你的人。**这是用来跟进你已有的联系人，不是给陌生人或买来的名单发消息。
- **微信条款禁止自动化操作**，不管 App 有没有被改动。风险落在你自己的账号上，而且发给不常联系的人的相似消息越多，风险越大。日上限要低。
- **尊重退订**，第一条消息说清你是谁。
- **当地法律由你自己负责。**比如新加坡《垃圾邮件控制法》覆盖即时消息，一天 100 条以上相似消息就算批量；
  给联系人分类打分也适用个人信息保护法（PDPA、PIPL）。以上不是法律意见。
- **数据只在你的 Mac 上。**通讯录、草稿、台账和截图都在 `~/Library/Application Support/wechat-sales-copilot/`。
  用 API 起草时，列出的联系人字段会发给 Anthropic；默认模式下会进你自己的 Claude Code 会话。见 [docs/privacy.md](docs/privacy.md)。

## 前人工作

不注入地驱动 Mac 版微信并不新鲜，本项目借鉴了这些项目的思路：

- [zbvxbb622-code/wechat-mcp-friend-automation](https://github.com/zbvxbb622-code/wechat-mcp-friend-automation)：
  Mac 上的 MCP，按 Excel 名单加好友，带工作时段、冷却、去重、单实例锁和熔断。
- [harrylabsj/wechat-social-assistant](https://github.com/harrylabsj/wechat-social-assistant)：截屏识别抓联系人，
  大模型打标签，按分群写个性化草稿，由人批准。
- [BiboyQG/WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP)：通过 macOS 辅助功能读消息、回消息。
- [cluic/wxauto](https://github.com/cluic/wxauto)：Windows 上的微信界面自动化。

本项目补上的是整条链路：从整本通讯录到分好级的潜客，到批准过的一对一草稿，到有节奏、绝不重复、认退订的发送器，
再把回复对回台账；全部做成技能。

## 路线图

1. **回复副驾**：按意向给回复分类，从你自己发过的消息里学口吻起草回复，在手机上批准，走同样的核对发出。
2. **跟进**：N 天没回补一句短的，最多两三次，对方一回或说不要就停。
3. **客户档案和每日「今天跟进谁」清单**，有兴趣的人附上预约链接。

不打算做：朋友圈自动点赞评论、读微信数据库、微调「数字分身」。

## 免责声明

本项目与腾讯无关，未获腾讯认可或授权。「微信」「WeChat」「Weixin」是腾讯的商标。
按 Apache License 2.0 原样提供，使用后果由使用者自负。
