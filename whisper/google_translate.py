import requests
import config

# 使用谷歌翻译网页接口进行翻译
def google_web_translate(text, src=config.SourceLanguage, tgt=config.TargetLanguage):
    # 在linux中使用了代理，windows不需要
    # proxies = {
    #     "http": "http://127.0.0.1:7890",
    #     "https": "http://127.0.0.1:7890"
    # }

    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": src,
        "tl": tgt,
        "dt": "t",
        "q": text
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # 添加代理
    r = requests.get(url, params=params, headers=headers, timeout=10)#, proxies=proxies)
    r.raise_for_status()

    data = r.json()
    return "".join([item[0] for item in data[0]])

