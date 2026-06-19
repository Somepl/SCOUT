# SCOUT 系统说明书

**版本**: v1.0  
**最后更新**: 2026-06-14

---

## 一、项目目标

### 1.1 核心定位
SCOUT 是一个面向 A 股中长线投资者的行情态势感知系统。在影响股市的消息被大众获知之前，捕获信号、分析验证、给出预判，并持续跟踪优化。

### 1.2 用户画像
- 投资新手，上班族，无法实时盯盘
- 使用性能一般的笔记本
- 偏好中长期投资（非短线）
- 需要易懂、可执行的参考建议

### 1.3 核心需求
| 需求 | 说明 | 实现方式 |
|------|------|---------|
| 提前捕获信号 | 在消息广泛传播前获取 | 多信息源定时采集 |
| 验证真实性 | 判断消息可信度 | AI逻辑推理 + 多源交叉验证 |
| 给出预判建议 | 利好/利空判断 + 投资建议 | AI分析引擎 |
| 跟踪优化 | 复盘预判准确性 | 跟踪数据库 + 复盘脚本 |

### 1.4 设计原则
- **完全免费** — 零成本运行
- **本地优先** — 数据存本地，不依赖第三方服务
- **灵活切换** — AI API 支持任意兼容 OpenAI 格式的服务商
- **可复盘** — 每条预判可追溯、可评价，持续改进

---

## 二、技术栈

### 2.1 核心依赖

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.14+ | 主开发语言 |
| requests | 2.31+ | HTTP 网络请求 |
| beautifulsoup4 | 4.12+ | HTML 页面解析 |
| lxml | 5.0+ | 高性能 XML/HTML 解析 |
| openai | 1.0+ | AI API 调用（兼容任意 OpenAI 格式） |
| SQLite | 内置 | 本地数据存储 |

### 2.2 AI 模型

| 模型 | 提供商 | 费用 | 说明 |
|------|--------|------|------|
| Qwen/Qwen2.5-7B-Instruct | 硅基流动 | ¥0 | 永久免费，默认使用 |
| THUDM/glm-4-9b-chat | 硅基流动 | ¥0 | 备选免费模型 |
| deepseek-chat | DeepSeek | ~¥1/月 | 付费升级选项 |
| gpt-4o-mini | OpenAI | ~$0.15/月 | 需科学上网 |

### 2.3 部署环境

| 环境 | 说明 |
|------|------|
| 操作系统 | Windows（当前），跨平台兼容 |
| 调度方式 | Windows 任务计划程序 |
| 推送服务 | ServerChan（免费，可选） |

---

## 三、系统架构

### 3.1 架构总图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          SCOUT 系统架构图                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Signal     │  │   Capture    │  │ Observation  │  │    Track     │ │
│  │   情报采集    │→│   数据处理    │→│  +Understand  │→│   输出复盘    │ │
│  │              │  │              │  │   AI分析引擎   │  │              │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │                 │         │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐ │
│  │ collector.py │  │  utils.py    │  │ analyzer.py  │  │ reporter.py  │ │
│  │              │  │  去重        │  │  调用AI API  │  │  CLI简报     │ │
│  │  4个信息源   │  │  分类        │  │  解析结果    │  │  notifier.py │ │
│  │              │  │              │  │  生成结构化  │  │  微信推送    │ │
│  └──────────────┘  └──────────────┘  └──────┬───────┘  │  review.py   │ │
│                                              │          │  复盘系统    │ │
│                                              ▼          └──────┬───────┘ │
│                                     ┌──────────────────┐       │        │
│                                     │  storage.py      │◄──────┘        │
│                                     │  SQLite 数据库    │               │
│                                     │  messages        │               │
│                                     │  analysis        │               │
│                                     │  tracking        │               │
│                                     └──────────────────┘               │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流转

```
[信息源] ──HTTP──→ [collector.py] ──List[dict]──→ [utils.dedup] ──→ [analyzer.py]
                                                                          │
                                          [SQLite] ◄── [storage.py] ◄────┤
                                              │                           │
                                              ▼                           │
                                     [reporter.py] ──→ CLI输出 + 文件存档   │
                                              │                           │
                                              ▼                           │
                                     [notifier.py] ──→ 微信推送            │
                                              │                           │
                                              ▼                           │
                                     [review.py]  ◄── 读取数据库进行复盘    │
```

### 3.3 SCOUT 命名释义

| 字母 | 英文 | 对应层 | 功能 |
|------|------|--------|------|
| S | Signal | 情报采集 | 从4个信息源捕获早期信号 |
| C | Capture | 数据处理 | 去重、提取、归档 |
| O | Observation | 市场观察 | 持续监视多维度信息 |
| U | Understanding | 深度理解 | AI分析验证，评估影响 |
| T | Track | 跟踪优化 | 输出报告 + 复盘迭代 |

---

## 四、模块详解

### 4.1 collector.py — 情报采集模块

**职责**：定时从各信息源抓取最新财经消息。

**输入**：`config.py` 中的 `NEWS_SOURCES` 配置  
**输出**：`List[Dict]`，每条包含 title/content/source/url/publish_time/category  
**支持的信息源**：

| 源名称 | 解析器 | URL |
|--------|--------|-----|
| 东方财富要闻 | `parse_eastmoney` | `https://finance.eastmoney.com/a/czqyw.html` |
| 新浪财经头条 | `parse_sina` | `https://finance.sina.com.cn/` |
| 同花顺要闻 | `parse_10jqka` | `https://www.10jqka.com.cn/` |
| 证券时报 | `parse_stcn` | `https://www.stcn.com/` |

**关键函数**：
- `fetch_url(url)` — 通用 HTTP 请求，带 User-Agent
- `collect_from_source(source_config)` — 采集单个信息源
- `collect_all(sources)` — 采集所有配置的信息源

### 4.2 analyzer.py — AI 分析引擎

**职责**：调用云端 AI API 分析每条消息，生成结构化投资判断。

**输入**：消息标题、来源、内容  
**输出**：结构化分析结果

**分析输出字段**：

| 字段 | 类型 | 可选值 |
|------|------|--------|
| event_type | str | 政策利好/政策利空/行业利好/行业利空/公司利好/公司利空/外围市场/中性消息 |
| confidence | str | 高/中/低 |
| reason | str | 判断理由 |
| affected_sectors | list | 影响的行业板块 |
| affected_concept | list | 影响的概念题材 |
| impact_level | str | 重大/中等/轻微 |
| time_horizon | str | 短期/中期/长期 |
| market_sentiment | str | 利好/利空/中性 |
| advice | str | 买入/观望/卖出/关注 |
| advice_reason | str | 建议理由 |

**处理流程**：
```
原始文本 → 构造 prompt → 调用 AI API → 接收响应 → 解析为结构化数据 → 返回
```

**错误处理**：
- AI API 调用失败时自动重试 2 次
- JSON 解析失败时启用 KV 格式回退解析
- 所有异常有默认值兜底

### 4.3 reporter.py — 报告生成模块

**职责**：将分析结果格式化为可读的简报文本。

**输出形式**：
- CLI 终端输出
- 文本文件存档 (`data/reports/report_YYYYMMDD.txt`)
- 微信推送摘要文本

**报告结构**：
```
优先关注信号（可信度高 + 影响大）
值得关注信号（可信度中）
一般信息（可信度低）
综合研判（利好/利空统计 + 操作建议统计 + 市场判断）
```

### 4.4 notifier.py — 微信推送模块

**职责**：通过 ServerChan 服务将简报推送到微信。

**触发条件**：`config.py` 中 `PUSH_WECHAT = True` 且 `SERVER_CHAN_KEY` 已配置

**API 调用**：`POST https://sctapi.ftqq.com/{SENDKEY}.send`

### 4.5 storage.py — 数据存储模块

**职责**：使用 SQLite 存储消息、分析结果和复盘记录。

**数据库表结构**：

```sql
messages
├── id          INTEGER PRIMARY KEY
├── title       TEXT            -- 消息标题
├── content     TEXT            -- 消息内容
├── source      TEXT            -- 来源
├── url         TEXT            -- 原文链接
├── publish_time TEXT           -- 发布时间
└── collected_time TEXT         -- 采集时间

analysis
├── id              INTEGER PRIMARY KEY
├── message_id      INTEGER     -- 关联消息ID
├── event_type      TEXT        -- 事件类型
├── confidence      TEXT        -- 可信度
├── affected_sectors TEXT       -- 影响板块(JSON数组)
├── affected_concept TEXT       -- 影响概念(JSON数组)
├── impact_level    TEXT        -- 影响程度
├── time_horizon    TEXT        -- 时间跨度
├── market_sentiment TEXT       -- 市场情绪
├── advice          TEXT        -- 投资建议
├── advice_reason   TEXT        -- 建议理由
├── reason          TEXT        -- 判断理由
├── analysis_raw    TEXT        -- AI原始结果(JSON)
├── report_date     TEXT        -- 报告日期
└── created_time    TEXT        -- 创建时间

tracking
├── id              INTEGER PRIMARY KEY
├── analysis_id     INTEGER     -- 关联分析ID
├── actual_outcome  TEXT        -- 实际结果
├── outcome_detail  TEXT        -- 备注
└── reviewed_at     TEXT        -- 复盘时间
```

### 4.6 review.py — 预判复盘脚本

**职责**：交互式复盘，逐条回顾预判准确性。

**用法**：`python -X utf8 review.py`

**流程**：
```
显示历史统计 → 逐条展示未复盘记录 → 用户评价(正确/部分正确/错误)
    → 可选备注 → 保存 → 显示更新后统计
```

### 4.7 utils.py — 工具函数模块

| 函数 | 说明 |
|------|------|
| `md5_hash(text)` | 生成 MD5 哈希（用于去重） |
| `ensure_dir(path)` | 确保目录存在 |
| `now_str()` | 获取当前时间字符串 |
| `today_str()` | 获取今天日期字符串 |
| `deduplicate(news_list)` | 基于标题和内容去重 |

---

## 五、目录结构

```
scout/
│
├── main.py               主程序入口（9步全链路）
├── config.py             配置文件（用户主要修改此文件）
├── collector.py          情报采集模块（4个信息源）
├── analyzer.py           AI分析引擎（新闻+个股仪表盘）
├── market.py             行情技术分析（MA/MACD/RSI/评分）
├── reporter.py           报告生成（简报+个股+资金面+微信摘要）
├── screener.py           热点筛选（板块映射+AI推荐）
├── strategist.py         狙击清单（仓位分配+交易计划）
├── capital.py            资金面数据（北向资金+融资融券）
├── notifier.py           微信推送（ServerChan）
├── storage.py            数据存储（SQLite）
├── review.py             预判复盘脚本
├── utils.py              工具函数
├── app.py                Web可视化看板（Flask）
│
├── templates/            HTML模板
│   ├── base.html         基础模板（导航+样式）
│   ├── index.html        仪表盘首页
│   ├── news.html         新闻分析列表
│   ├── stocks.html       个股仪表盘
│   ├── capital.html      资金面
│   └── history.html      历史简报
│
├── run_scout.ps1         Windows自动运行脚本
├── requirements.txt      Python依赖清单
│
├── README.md             用户使用说明
├── AGENTS.md             AI上下文记录（用于恢复对话）
├── ARCHITECTURE.md       本文件（项目说明书）
│
└── data/                 数据目录
    ├── scout.db          SQLite数据库
    └── reports/          每日简报文本存档
```

---

## 六、开发规范

### 6.1 代码规范
- 使用 `print(..., flush=True)` 确保实时输出
- 异常处理使用 try/except，避免程序中断
- 所有文件路径使用 `os.path.join` 拼接，保证跨平台兼容
- 配置文件（config.py）中不包含业务逻辑
- 主程序（main.py）只做流程编排，不处理具体逻辑

### 6.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | 小写 + 下划线 | `collector.py`, `run_scout.ps1` |
| 类名 | 大驼峰 | `ScoutStorage` |
| 函数名 | 小写 + 下划线 | `collect_all()`, `parse_eastmoney()` |
| 变量名 | 小写 + 下划线 | `news_list`, `report_date` |

### 6.3 配置管理
- 用户可修改项全部集中在 `config.py`
- API Key 不硬编码在代码中
- 信息源增删改只需修改 `config.py` 中的 `NEWS_SOURCES`
- AI 模型切换只需修改 `config.py` 中的三行配置

### 6.4 错误处理规范
- 网络请求异常：捕获后打印错误信息，返回 `None`
- AI API 异常：重试 2 次，仍失败则返回默认值
- 文件写入异常：确保目录存在后重试
- 数据库异常：事务回滚，不丢失已有数据

### 6.5 数据安全
- API Key 仅存在于 `config.py`，不提交版本管理
- 所有数据存储在本地 SQLite，不自动上传
- AI 分析时上传消息文本到云端（必要的数据传输）
- 微信推送通过 ServerChan HTTPS 加密传输

---

## 七、当前阶段任务

### 7.1 状态说明

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1: MVP | ✅ 已完成 | 核心链路跑通 |
| Phase 2: 增强 | ✅ 已完成 | 推送 + 复盘 + 更多源 |
| Phase 3: 进阶 | ✅ 已完成 | 资金面、热点筛选、狙击清单、Web看板 |
| Phase 4: 优化 | 📋 待规划 | 自动复盘、更强模型、多语言源 |

### 7.2 Phase 1 — MVP（已完成）

- [x] 采集模块：2个信息源
- [x] 分析模块：调用免费AI API分析
- [x] 去重模块：MD5去重
- [x] 报告模块：CLI输出 + 文件存档
- [x] 存储模块：SQLite建表与写入
- [x] 配置模块：API Key、信息源配置
- [x] 自动运行：Windows任务计划程序设置
- [x] GBK编码兼容：移除emoji，适配Windows控制台

### 7.3 Phase 2 — 增强功能（已完成）

- [x] 微信推送模块：notifier.py + ServerChan
- [x] 预判复盘系统：review.py + tracking表
- [x] 扩充信息源：同花顺 + 证券时报（共4个）
- [x] 项目文档：README.md + AGENTS.md + ARCHITECTURE.md
- [x] AI提示词优化：KV格式输出 + 中文标点清洗

### 7.4 Phase 3 — 进阶功能（已完成）

- [x] 资金面数据模块：capital.py（北向资金、融资融券、沪深港通）
- [x] 热点筛选模块：screener.py（板块映射表 + AI推荐股票）
- [x] 狙击清单模块：strategist.py（交易计划、仓位分配、止损止盈）
- [x] Web可视化看板：app.py + templates/（Flask仪表盘）
- [x] 个股技术分析：market.py（MA/MACD/RSI/量价/支撑阻力/评分）

### 7.5 Phase 4 — 待规划功能

| 功能 | 优先级 | 预估难度 | 说明 |
|------|--------|---------|------|
| 自动复盘 | 中 | 高 | 自动追踪预判后续走势，无需手动评价 |
| 更强AI模型 | 低 | 低 | 切换到DeepSeek（约¥1-2/月） |
| 英文信息源 | 低 | 中 | 接入英文财经新闻 |
| 策略回测 | 低 | 高 | 回测狙击清单的历史表现 |

### 7.6 运行方式

```bash
# 全量运行（采集→分析→推送）
python -X utf8 main.py

# 启动Web看板
python -X utf8 app.py
# 访问 http://127.0.0.1:5000

# 复盘
python -X utf8 review.py
```

### 7.7 已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| 7B模型分析深度有限 | 分析可能不够深入 | ⚠️ 已知限制，升级模型可改善 |
| 网页结构变化导致解析失效 | 部分信息源可能突然无数据 | ⚠️ 需定期维护解析器 |
| 新浪财经返回较多低质内容 | 包含非财经链接 | ⚠️ 已做基础过滤，可进一步优化 |

---

## 八、部署说明

### 8.1 环境要求
- Python 3.11+
- Windows 10/11（当前平台）
- 网络连接（数据采集 + AI API）

### 8.2 安装步骤
```bash
pip install -r requirements.txt
```

### 8.3 配置
编辑 `config.py`，填写：
1. `AI_API_KEY` — 硅基流动或其它 AI API 密钥
2. 按需修改 `NEWS_SOURCES`、`MAX_NEWS` 等参数

### 8.4 运行
```bash
# 手动运行
python -X utf8 main.py

# 复盘
python -X utf8 review.py
```

### 8.5 自动调度
Windows 任务计划程序已配置 **SCOUT每日情报** 任务，每天 08:00 执行。

---

## 九、费用明细

| 项目 | 费用 | 说明 |
|------|------|------|
| AI API | ¥0 | 硅基流动永久免费模型 |
| 信息采集 | ¥0 | 公开网页 |
| 数据存储 | ¥0 | 本地 SQLite |
| 任务调度 | ¥0 | Windows 自带 |
| 微信推送 | ¥0 | ServerChan 免费版 |
| **总计** | **¥0/月** | |

---

## 十、风险提示

1. **分析仅供参考**：AI 分析存在局限性，不构成投资建议
2. **信息合规**：仅使用公开信息，不涉及内幕交易
3. **信息源变化**：网站改版可能导致解析失败
4. **网络依赖**：需要稳定的互联网连接
5. **数据隐私**：消息文本会发送到 AI API 服务商进行分析

| 模块 | 职责 | 当前状态 |
|------|------|---------|
| `fetch_url` | 通用网络请求 | ✅ 完成 |
| `parse_eastmoney` | 解析东方财富 | ✅ 完成 |
| `parse_sina` | 解析新浪财经 | ✅ 完成 |
| `parse_10jqka` | 解析同花顺 | ✅ 完成 |
| `parse_stcn` | 解析证券时报 | ✅ 完成 |
| `parse_rss` | 通用RSS解析 | ✅ 完成 |

### Capture 层 — 数据处理 (utils.py)

| 函数 | 职责 |
|------|------|
| `deduplicate` | MD5去重，同一事件不重复分析 |
| `ensure_dir` | 自动创建目录 |

### Observation + Understanding 层 — AI分析 (analyzer.py)

| 函数 | 职责 |
|------|------|
| `get_client` | 初始化AI客户端 |
| `analyze_single_news` | 逐条调用AI分析 |
| `analyze_news_batch` | 批量分析（控制并发） |
| `_parse_kv_output` | 解析AI返回的文本格式为结构化数据 |

AI分析返回的字段：
- event_type — 事件类型（政策利好/利空、行业利好/利空等）
- confidence — 可信度（高/中/低）
- reason — 判断理由
- affected_sectors — 影响的行业板块
- market_sentiment — 市场情绪（利好/利空/中性）
- advice — 投资建议（买入/观望/卖出/关注）
- advice_reason — 建议理由

### Track 层 — 输出与复盘 (reporter.py + notifier.py + review.py)

| 模块 | 输出形式 | 触发方式 |
|------|---------|---------|
| `reporter.py` | CLI命令行简报 | main.py自动调用 |
| `notifier.py` | 微信推送 | main.py自动调用（需配置） |
| `review.py` | 交互式复盘 | 手动运行 |

### 数据存储 (storage.py)

```
数据库: data/scout.db
表:
├── messages      — 原始消息
├── analysis      — AI分析结果
└── tracking      — 复盘跟踪记录

文件存档: data/reports/
└── report_YYYYMMDD.txt — 每日简报文本
```

## 三、数据流转

```
原始网页HTML
    │
    ▼
collector.py → List[dict] → {title, content, source, url, time}
    │
    ▼
utils.deduplicate → 去重
    │
    ▼
analyzer.analyze_news_batch → 调用AI API
    │
    ├─→ 成功 → 结构化分析结果
    └─→ 失败 → 默认中性结果（含错误信息）
    │
    ▼
storage.save_analysis_batch → 写入SQLite
    │
    ▼
reporter.build_report → 格式化文本
    │
    ├─→ print_report → CLI输出
    ├─→ 保存到 data/reports/ → 文件存档
    └─→ notifier.push_wechat → 微信推送
```

## 四、开发路线图

### Phase 1 — MVP ✅ 已完成

- [x] 2个信息源（东方财富、新浪财经）
- [x] AI分析引擎（硅基流动免费模型）
- [x] 去重处理
- [x] 每日简报生成
- [x] SQLite存储
- [x] Windows定时任务

### Phase 2 — 增强功能 ✅ 已完成

- [x] 微信推送模块 (notifier.py)
- [x] 预判复盘系统 (review.py)
- [x] 扩充到4个信息源（新增同花顺、证券时报）
- [x] 项目文档 (README.md + AGENTS.md)

### Phase 3 — 可继续开发

- [ ] **资金面数据接入**：北向资金、融资融券、龙虎榜
- [ ] **Web看板**：用Flask/FastAPI搭简单的网页仪表盘
- [ ] **自动复盘**：系统自动追踪预判后续走势，无需手动评价
- [ ] **更强AI模型**：切换到DeepSeek等更强模型（约¥1-2/月）
- [ ] **技术面指标**：K线、MACD、RSI等辅助判断
- [ ] **多语言支持**：接入英文财经新闻源

## 五、配置体系

```
config.py
├── AI API配置
│   ├── AI_API_KEY      # API密钥
│   ├── AI_BASE_URL     # API地址
│   └── AI_MODEL        # 模型名称
├── 信息源配置
│   └── NEWS_SOURCES[]  # 名称/URL/解析器
├── 运行配置
│   ├── MAX_NEWS        # 每天分析条数
│   └── DATA_DIR        # 数据目录
└── 推送配置
    ├── PUSH_WECHAT     # 开关
    └── SERVER_CHAN_KEY # 密钥
```

## 六、部署架构

```
┌──────────────────────────────────┐
│        你的笔记本 (Windows)        │
│                                  │
│  ┌──────────────────────────┐   │
│  │  Python 3.14              │   │
│  │  ├── main.py (每天8点)    │   │
│  │  ├── data/scout.db       │   │
│  │  └── data/reports/       │   │
│  └──────────────────────────┘   │
│                                  │
│  ┌──────────────────────────┐   │
│  │  Windows任务计划程序       │   │
│  │  每天08:00 → run_scout.ps1│   │
│  └──────────────────────────┘   │
└──────────┬───────────────────────┘
           │  HTTPS
           ▼
┌──────────────────────────────────┐
│     硅基流动 API (云端)           │
│  免费模型: Qwen2.5-7B-Instruct   │
└──────────────────────────────────┘
           │  HTTPS (可选)
           ▼
┌──────────────────────────────────┐
│     ServerChan (微信推送)         │
│     选配，需自行注册获取Key       │
└──────────────────────────────────┘
```

## 七、关键指标

| 指标 | 数值 |
|------|------|
| 每日采集消息数 | ~180条 |
| 每日AI分析数 | 20条（可配置） |
| 每日运行时长 | ~5-8分钟 |
| 每月API费用 | ¥0 |
| 信息源数量 | 4个 |
| 数据库大小 | ~几MB/月 |

## 八、风险与限制

1. **AI模型限制**：7B参数模型分析深度有限，重大决策需人工核实
2. **信息源稳定性**：网页结构变化可能导致解析失败，需定期维护
3. **网络依赖**：需要稳定的网络连接进行数据采集和AI调用
4. **法律边界**：仅使用公开信息，不涉及内幕交易
5. **数据隐私**：所有数据存本地，AI调用会上传消息文本到云端
