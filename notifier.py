import requests
from config import PUSH_WECHAT, SERVER_CHAN_KEY


def push_wechat(title, content):
    if not PUSH_WECHAT or not SERVER_CHAN_KEY:
        print("  微信推送未启用（PUSH_WECHAT = False 或未配置 Key）", flush=True)
        return False
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_KEY}.send"
    try:
        resp = requests.post(url, data={"title": title, "desp": content}, timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            print(f"  微信推送成功: {title}", flush=True)
            return True
        else:
            print(f"  微信推送失败: {data.get('message', '未知错误')}", flush=True)
            return False
    except Exception as e:
        print(f"  微信推送异常: {e}", flush=True)
        return False
