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
- AI引擎：DeepSeek V4 Flash（500万免费额度，能力强）
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
11. 量化评分模型 — 新增quant_model.py模块，LightGBM 61维特征替代固定规则评分（已扩充至150只股票×800日K线训练）
12. 同花顺修复 — 已修复SSL EOF错误，4个信息源全部正常（verify=False绕过+fallback URL）
13. 自动复盘追踪 — storage.py新增auto_review/auto_review_stocks，main.py集成（可开关）
14. 量化模型自动重训练 — 新增train_if_expired机制+config配置，每次运行自动检查
15. 多信号确信度 — 综合技术面/资金面/新闻面计算确信度评分
16. 推荐追踪系统 — 狙击清单记录+自动评估+月度业绩报告

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
- SERVER_CHAN_KEY：ServerChan密钥（需用户自行配置）
- TRAIN_MIN_STOCKS：150（量化模型训练股票数）
- TRAIN_KLINE_DAYS：800（每只股票K线天数）
- TRAIN_INTERVAL_DAYS：7（模型自动重训练间隔）

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
- GitHub push 网络不通，commit 仅本地保存（需切换网络或配置代理）
- 回测因历史买入信号不足，暂无可交易记录（需运行一段时间积累数据）
- 量化模型日历特征（day_of_month/month）重要性偏高，可能存在过拟合风险
- 4个信息源均为中文，无英文全球市场覆盖

## 存档指令
- 用户要求每次对话结束前（或修改重要代码后）执行 git add -A && git commit -m "描述" && git push origin main
- GitHub 远程仓库: https://github.com/Somepl/SCOUT.git (main分支)
- 直接覆盖推送，不新建分支

## 后续可改进方向
| 方向 | 优先级 | 说明 |
|------|--------|------|
| 扩充量化训练数据 | ✅已完成 | 已从3只×180天→150只×800日K线，MAE从4.52%降至3.50% |
| 量化模型自动重训练 | ✅已完成 | train_if_expired机制，运行自动检查，7天间隔可配置 |
| 切换更强AI模型 | ✅已完成 | 已切换至DeepSeek V4 Flash |
| 自动复盘追踪 | ✅已完成 | 新闻+个股双复盘，已整合进main.py |
| 修复同花顺解析器 | ✅已完成 | verify=False绕过+fallback URL，4个信息源全部正常 |
| 量化模型日历特征优化 | 中 | day_of_month/month特征重要性偏高，需添加更多非日历特征 |
| 接入英文信息源 | 低 | Reuters / Bloomberg |
| Web看板远程部署 | 低 | 云服务器或 NAS |
| SSH/代理解决Git推送 | 低 | 更换网络环境 |
| 推荐追踪详细报告 | 低 | 月度业绩报告自动推送微信 |

