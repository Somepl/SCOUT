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
10. 策略回测 — 新增backtest.py模块，支持多持仓周期回测、胜率/收益率/最大回撤统计
11. 量化评分模型 — 新增quant_model.py模块，LightGBM 61维特征替代固定规则评分

## 技术栈
- Python 3.14+
- requests / beautifulsoup4 / lxml（数据采集 + 行情API直连）
- openai（AI API 调用，兼容任意OpenAI格式的API）
- SQLite（本地存储）
- numpy / pandas / scipy（数值计算 + 特征工程）
- lightgbm（量化评分模型，61维特征）
- flask（Web可视化看板）
- ServerChan（微信推送）

## 项目结构
- `main.py` — 主程序入口（11步全链路：采集→分析→存储→筛选→行情→资金→回测→推送）
- `config.py` — 配置文件（API Key、信息源、推送设置、筛选配置、USE_ML_SCORING）
- `collector.py` — 采集器（4个信息源）
- `market.py` — 行情数据模块（新浪API获取实时行情+60日K线+技术指标+规则评分+量化集成）
- `analyzer.py` — AI分析引擎（新闻分析 + 个股交易决策仪表盘）
- `reporter.py` — 报告生成（新闻简报 + 个股仪表盘 + 资金面 + 微信摘要 + 市场光信号）
- `screener.py` — 热点板块发现 + 自动筛选候选股票（板块映射表 + AI推荐）
- `strategist.py` — 狙击清单 + 仓位分配 + 交易计划生成
- `capital.py` — 资金面数据（北向资金、融资融券余额、沪深港通十大成交）
- `notifier.py` — 微信推送（ServerChan）
- `storage.py` — SQLite数据库（含stock_analysis表 + 回测接口）
- `review.py` — 预判复盘脚本
- `backtest.py` — 策略回测引擎（多持仓周期 + 止损 -5%）
- `quant_model.py` — LightGBM 量化评分模型（61维特征 + 训练 + 推理）
- `utils.py` — 工具函数
- `app.py` — Flask Web可视化看板（6个路由）
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
- MAX_SCREENED_STOCKS：5（每日最多分析个股数）
- USE_ML_SCORING：True（启用LightGBM量化评分）
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

## 当前局限
- 同花顺解析器 SSL EOF 错误，暂无可采集数据
- GitHub push 网络不通，commit 仅本地保存
- 量化模型仅 3 只股票 × 180 天训练数据，泛化不足
- 回测因历史买入信号不足，暂无可交易记录

## 存档指令
- 用户要求每次对话结束前（或修改重要代码后）执行 git add -A && git commit -m "描述" && git push origin main
- GitHub 远程仓库: https://github.com/Somepl/SCOUT.git (main分支)
- 直接覆盖推送，不新建分支

## 后续可改进方向
| 方向 | 优先级 | 说明 |
|------|--------|------|
| 扩充量化训练数据 | 高 | 从3只→30+股票，更长历史周期 |
| 量化模型自动重训练 | 中 | 每周/月自动增量训练 |
| 切换更强AI模型 | 中 | DeepSeek / GPT-4o-mini（¥1-2/月） |
| 自动复盘追踪 | 中 | 系统自动跟踪预判后续走势 |
| 接入英文信息源 | 低 | Reuters / Bloomberg |
| 修复同花顺解析器 | 中 | SSL 握手问题或换备用源 |
| Web看板远程部署 | 低 | 云服务器或 NAS |
| SSH/代理解决Git推送 | 低 | 更换网络环境 |

