"""
SCOUT 配置文件
==============
你只需要修改这个文件里的配置项即可。
重要: 密钥优先从环境变量读取，如未设置则使用下方硬编码值。
可在 .env 文件或系统环境变量中设置:
  SCOUT_AI_API_KEY, SCOUT_SERVER_CHAN_KEY
"""

import os

AI_API_KEY = os.environ.get("SCOUT_AI_API_KEY") or "sk-你的DeepSeek Key"
AI_BASE_URL = "https://api.deepseek.com/v1"
AI_MODEL = "deepseek-v4-flash"

"""
切换示例（取消下面对应组的注释即可）：

--- DeepSeek（当前配置，V4 Flash 能力强，500万免费额度）---
AI_API_KEY = "sk-你的key"
AI_MODEL = "deepseek-v4-flash"
AI_BASE_URL = "https://api.deepseek.com/v1"

--- 智谱 GLM-4-Flash（永久免费无限量，能力弱于 DeepSeek）---
AI_API_KEY = "你的智谱API Key"
AI_MODEL = "glm-4-flash"
AI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

--- 阿里云百炼 Qwen（新用户送7000万token）---
AI_API_KEY = "你的DashScope Key"
AI_MODEL = "qwen3-plus"
AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

--- 硅基流动（原配置，余额不足需充值）---
AI_API_KEY = "sk-你的key"
AI_MODEL = "Qwen/Qwen2.5-7B-Instruct"
AI_BASE_URL = "https://api.siliconflow.cn/v1"

--- OpenAI（需科学上网）---
AI_API_KEY = "sk-你的key"
AI_MODEL = "gpt-4o-mini"
AI_BASE_URL = "https://api.openai.com/v1"
"""

NEWS_SOURCES = [
    {
        "name": "东方财富要闻",
        "url": "https://finance.eastmoney.com/a/czqyw.html",
        "type": "news",
        "parser": "eastmoney"
    },
    {
        "name": "新浪财经头条",
        "url": "https://finance.sina.com.cn/",
        "type": "news",
        "parser": "sina"
    },
    {
        "name": "同花顺要闻",
        "url": "https://stock.10jqka.com.cn/",
        "type": "news",
        "parser": "10jqka",
        "fallback_url": "https://www.10jqka.com.cn/"
    },
    {
        "name": "证券时报",
        "url": "https://www.stcn.com/",
        "type": "news",
        "parser": "stcn"
    },
]

MAX_NEWS = 20
DATA_DIR = "data"

# ===== 个股动态筛选配置 =====
# SCOUT 根据新闻分析的热点板块，自动发现相关股票进行分析推荐
# 你无需手动维护自选股列表
MAX_SCREENED_STOCKS = 5  # 每日最多分析这么多只（控制运行时长）

# 如果有些股票你特别想关注，可以加在这里（可选），它们会被额外分析
# EXTRA_WATCH = ["600519", "300750"]

# ===== 量化模型配置 =====
# 启用 LightGBM 机器学习评分（替代/补充固定规则评分）
# 首次运行会自动训练模型，需要 lightgbm + scipy 依赖
USE_ML_SCORING = True
TRAIN_INTERVAL_DAYS = 7  # 量化模型自动重训练间隔（天）
TRAIN_MIN_STOCKS = 50    # 训练时使用的股票数量

# ===== 自动复盘配置 =====
# 系统自动追踪预判后续走势，无需手动评价
AUTO_REVIEW_ENABLED = True        # 开启/关闭自动复盘
AUTO_REVIEW_LOOKBACK_DAYS = 90    # 回溯多少天的预判
AUTO_REVIEW_CHECK_DAYS = [5, 10]  # 发出预判后 N 个交易日复查
AUTO_REVIEW_PROFIT_THRESHOLD = 3.0  # 涨幅超过此值视为"正确"（%）

PUSH_WECHAT = True
SERVER_CHAN_KEY = os.environ.get("SCOUT_SERVER_CHAN_KEY") or "SCT364176THOR5HnLTftAFmEceCMAuGd5j"
