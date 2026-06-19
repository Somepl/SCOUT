# SCOUT - 行情态势感知系统

**Signal Capture, Observation, Understanding & Track**

侦察兵系统，比市场更早一步发现信号。

---

## 系统简介

SCOUT 是一个面向 A 股中长线投资者的情报分析系统。它每天自动从多个财经信息源采集新闻，调用 AI 分析每条消息的影响，生成投资建议简报，并支持后续的预判复盘。

### 核心流程

```
采集情报 → AI 分析 → 可信度评估 → 投资建议 → 简报推送 → 跟踪复盘
```

### 特点

- **完全免费**：使用硅基流动永久免费模型，零成本运行
- **自动运行**：每天早 8 点自动采集分析，上班前就能看到简报
- **多源验证**：东方财富 + 新浪财经 + 同花顺 + 证券时报 4 个来源
- **可信度标注**：每条消息标注高/中/低可信度，你自己判断
- **可复盘**：记录每条预判，后续跟踪准确性，不断优化

---

## 项目结构

```
scout/
├── main.py            主程序入口（每天运行这个）
├── config.py          配置文件（你主要改这个）
├── collector.py       信息采集模块（4个信息源）
├── analyzer.py        AI 分析引擎（调用硅基流动 API）
├── reporter.py        报告生成模块
├── notifier.py        微信推送模块（ServerChan）
├── storage.py         数据存储模块（SQLite）
├── review.py          预判复盘脚本
├── utils.py           工具函数
├── run_scout.ps1      自动运行脚本
├── requirements.txt   Python 依赖
├── README.md          本文件
└── data/              数据目录
    ├── scout.db       SQLite 数据库
    └── reports/       每日简报存档
```

---

## 快速开始

### 1. 安装 Python

从 https://www.python.org/downloads/ 下载安装，安装时勾选 `Add Python to PATH`。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 获取免费 API Key

1. 打开 https://cloud.siliconflow.cn 注册账号
2. 左侧菜单 → API 密钥 → 新建 API 密钥
3. 复制以 `sk-` 开头的 Key

### 4. 配置

编辑 `config.py`，填入你的 API Key：

```python
AI_API_KEY = "sk-你的key"        # 刚复制的 Key
AI_BASE_URL = "https://api.siliconflow.cn/v1"
AI_MODEL = "Qwen/Qwen2.5-7B-Instruct"  # 永久免费模型
```

### 5. 运行

```bash
python -X utf8 main.py
```

### 6. （可选）设置每天自动运行

Windows 任务计划程序已配置好，每天早上 8:00 自动运行。也可以在 `config.py` 中修改 `RUN_TIME`。

---

## 配置说明

`config.py` 中可配置的项目：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `AI_API_KEY` | AI API 密钥 | 需自行填写 |
| `AI_BASE_URL` | API 地址 | `https://api.siliconflow.cn/v1` |
| `AI_MODEL` | 模型名称 | `Qwen/Qwen2.5-7B-Instruct` |
| `MAX_NEWS` | 每天分析的消息数 | `20` |
| `PUSH_WECHAT` | 是否开启微信推送 | `False` |
| `SERVER_CHAN_KEY` | ServerChan 密钥 | `""` |

### 切换 AI 模型

支持所有兼容 OpenAI 格式的 API，只需改三个变量：

```python
# 切换示例
# --- 硅基流动（免费）---
AI_API_KEY = "sk-xxx"
AI_MODEL = "Qwen/Qwen2.5-7B-Instruct"
AI_BASE_URL = "https://api.siliconflow.cn/v1"

# --- DeepSeek（约 ¥1/月）---
AI_API_KEY = "sk-xxx"
AI_MODEL = "deepseek-chat"
AI_BASE_URL = "https://api.deepseek.com/v1"
```

### 开启微信推送

1. 打开 https://sct.ftqq.com/ 用 GitHub 登录
2. 复制 SendKey
3. 在 `config.py` 中设置：
```python
PUSH_WECHAT = True
SERVER_CHAN_KEY = "你的SendKey"
```

---

## 使用指南

### 每天查看简报

每天早上 8 点自动运行后，简报保存在 `data/reports/` 目录下，或推送微信。

```
==========================================================
   [SCOUT] 每日情报简报
   2026-06-14
==========================================================

  !! 优先关注信号（3条）
----------------------------------------------------------
  [+] 碳酸锂重拾涨势！供求紧张 2026年储能或成为锂电池第一增长引擎
     来源: 东方财富  可信度: 高
     影响板块: 锂电池
     建议: 买入 - 碳酸锂价格上涨反映行业需求旺盛
```

### 预判复盘

定期运行复盘脚本，回顾之前预判的准确性：

```bash
python -X utf8 review.py
```

系统会逐条展示历史分析记录，让你评价"正确/部分正确/错误"，并统计准确率。

---

## 信息源

| 来源 | 类型 | 说明 |
|------|------|------|
| 东方财富要闻 | 财经新闻 | 综合财经资讯 |
| 新浪财经头条 | 财经新闻 | 全面财经报道 |
| 同花顺要闻 | 证券资讯 | A 股市场快讯 |
| 证券时报 | 证券资讯 | 权威证券媒体 |

---

## 费用

| 项目 | 费用 | 说明 |
|------|------|------|
| AI 分析 | ¥0 | 硅基流动永久免费模型 |
| 信息采集 | ¥0 | 公开网页 |
| 存储 | ¥0 | 本地 SQLite |
| 定时 | ¥0 | Windows 自带任务计划 |
| 推送 | ¥0 | ServerChan 免费版 |

**总计：¥0/月**

---

## 风险提示

- 本系统仅供参考，**不构成投资建议**
- 系统使用公开信息，不涉及内幕交易
- AI 分析存在局限性，投资决策需自行判断
- 股市有风险，入市需谨慎

---

## 后续方向

- [ ] 接入北向资金、融资融券等资金面数据
- [ ] Web 可视化看板
- [ ] 自动复盘优化算法
- [ ] 加入技术面指标辅助判断
