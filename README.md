# 飞行雪绒应援栈 Fleet Snowfluff

手机远程查看 Claude Code 会话的纯前端 Web 界面。

## 快速开始

```bash
# 安装依赖
pip install flask

# 启动
python server.py
```

手机和电脑连同一 WiFi，打开终端显示的地址即可。

## 端口

| 端口 | 用途 |
|------|------|
| 19877 | Flask Web 界面（手机访问） |

## 集成爱弥斯

详见 [aemeath/INTEGRATION.md](aemeath/INTEGRATION.md)。

## 项目结构

```
fleet-snowfluff/
├── server.py              # Flask 中转服务器
├── templates/
│   ├── index.html         # 单页 Web 应用
│   ├── manifest.json      # PWA 清单
│   └── sw.js              # Service Worker（后台通知）
└── aemeath/
    └── INTEGRATION.md     # 爱弥斯集成指南
```
