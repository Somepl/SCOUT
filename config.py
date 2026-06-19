"""
SCOUT 配置文件
==============
你只需要修改这个文件里的配置项即可。
"""

AI_API_KEY = "sk-xsljgmciqbwrtgkrrslmzvmllbkbtjtbwrudwqpnshykniex"
AI_BASE_URL = "https://api.siliconflow.cn/v1"
AI_MODEL = "Qwen/Qwen2.5-7B-Instruct"

"""
切换示例（取消下面对应组的注释即可）：

--- 硅基流动（免费，推荐）---
AI_API_KEY = "sk-你的key"
AI_MODEL = "Qwen/Qwen2.5-7B-Instruct"
AI_BASE_URL = "https://api.siliconflow.cn/v1"

--- DeepSeek（约 ¥1/月）---
AI_API_KEY = "sk-你的key"
AI_MODEL = "deepseek-chat"
AI_BASE_URL = "https://api.deepseek.com/v1"

--- OpenAI（需科学上网）---
AI_API_KEY = "sk-你的key"
AI_MODEL = "gpt-4o-mini"
AI_BASE_URL = "https://api.openai.com/v1"

--- 阿里通义千问 ---
AI_API_KEY = "sk-你的key"
AI_MODEL = "qwen-turbo"
AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
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
        "url": "https://www.10jqka.com.cn/",
        "type": "news",
        "parser": "10jqka"
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

PUSH_WECHAT = True
SERVER_CHAN_KEY = "SCT364176THOR5HnLTftAFmEceCMAuGd5j"
