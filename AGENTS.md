# SCOUT - 项目说明

## 项目概述
SCOUT (Signal Capture, Observation, Understanding & Track) 是一个面向 A 股中长线投资者的行情态势感知系统。每天自动采集财经新闻，AI分析后生成投资建议简报。

## 用户信息
- 投资经验：小白
- 投资周期：中长期（非短线，因上班无法盯盘）
- 目标市场：A股（沪深）
- Python水平：会一点点基础
- 硬件：性能一般的笔记本
- 需求：比市场更早捕获信号 → 验证真实性 → 给出预判建议 → 跟踪优化

## 核心设计决策
- 系统名：SCOUT（用户最终选择）
- AI引擎：硅基流动（SiliconFlow）免费模型，¥0/月
- 验证策略：标出可信度（高/中/低），由用户自己判断
- 汇报频率：每天早上一次综合简报
- 部署方式：本地脚本 + 云端AI API（后续可扩展Web）
- 信息验证：多源交叉验证 + AI逻辑判断两者都要
- API设计：支持灵活切换任意兼容OpenAI格式的API（config.py中改三行）

## 已完成的改进（按用户要求的顺序）
1. 微信推送 — 已添加ServerChan推送模块（notifier.py），需用户自行配置Key
2. 预判复盘 — 已创建复盘脚本（review.py），可逐条回顾预判准确性
3. 更多信息源 — 已从2个扩展到4个（东方财富、新浪财经、同花顺、证券时报）
4. 代码健壮性 — 解析器加固、analyzer bug修复、flush统一、存储异常隔离
5. 个股技术分析 — 新增market.py模块，支持自选股行情获取+技术指标+规则评分（参考daily_stock_analysis设计）
6. 资金面数据 — 新增capital.py模块，采集北向资金流向、融资融券余额、沪深港通数据
7. 热点筛选 — 新增screener.py模块，基于新闻分析自动发现热点板块并推荐相关个股
8. 狙击清单 — 新增strategist.py模块，生成可执行的交易计划（买点/止损/仓位分配）
9. Web仪表盘 — 新增app.py + templates/，Flask Web可视化看板

## 技术栈
- Python 3.14+
- requests / beautifulsoup4 / lxml（数据采集 + 行情API直连）
- openai（AI API 调用，兼容任意OpenAI格式的API）
- SQLite（本地存储）

## 项目结构
- `main.py` — 主程序入口（9步全链路：采集→分析→存储→资金面→狙击清单→推送）
- `config.py` — 配置文件（API Key、信息源、推送设置、筛选配置）
- `collector.py` — 采集器（4个信息源）
- `market.py` — 行情数据模块（新浪API获取实时行情+60日K线+技术指标）
- `analyzer.py` — AI分析引擎（新闻分析 + 个股交易决策仪表盘）
- `reporter.py` — 报告生成（新闻简报 + 个股仪表盘 + 资金面 + 微信摘要）
- `screener.py` — 热点板块发现 + 自动筛选候选股票（板块映射表 + AI推荐）
- `strategist.py` — 狙击清单 + 仓位分配 + 交易计划生成
- `capital.py` — 资金面数据（北向资金、融资融券余额）
- `notifier.py` — 微信推送（ServerChan）
- `storage.py` — SQLite数据库
- `review.py` — 预判复盘脚本
- `backtest.py` — 策略回测引擎（验证历史买入建议的有效性）
- `utils.py` — 工具函数
- `app.py` — Flask Web可视化看板
- `templates/` — HTML模板（base/index/news/stocks/capital/history）

## 运行方式
手动运行：
```bash
cd C:\Users\23100\Documents\Private Project\scout
python -X utf8 main.py
```

复盘：
```bash
python -X utf8 review.py
```

自动运行：Windows任务计划程序每天早8:00执行 run_scout.ps1

## 关键配置项（config.py）
- AI_API_KEY：硅基流动 API Key（当前已配置）
- AI_MODEL：Qwen/Qwen2.5-7B-Instruct（永久免费）
- MAX_NEWS：20（每天分析条数，可调）
- PUSH_WECHAT：微信推送开关（默认False）
- SERVER_CHAN_KEY：ServerChan密钥（需用户自行获取）

## 当前信息源（4个）
1. 东方财富要闻 — 解析器: eastmoney
2. 新浪财经头条 — 解析器: sina
3. 同花顺要闻 — 解析器: 10jqka
4. 证券时报 — 解析器: stcn

## 注意事项
- 全程免费运行（硅基流动免费模型）
- 数据存储在 data/scout.db（SQLite）
- 每日简报保存在 data/reports/ 目录
- 所有分析仅供参考，不构成投资建议
- 使用公开信息，不涉及内幕交易

## 存档指令
- 用户要求每次对话结束前（或修改重要代码后）执行 git add -A && git commit -m "描述" && git push origin main
- GitHub 远程仓库: https://github.com/Somepl/SCOUT.git (main分支)
- 直接覆盖推送，不新建分支

## 后续可改进方向
- 自动复盘优化算法权重
- 更强AI模型（如DeepSeek切换）
- 接入英文财经新闻源
- 策略回测系统

