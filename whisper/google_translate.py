import requests

def google_web_translate(text, src="en", tgt="zh-CN"):
    proxies = {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890"
    }

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

    r = requests.get(url, params=params, headers=headers, timeout=10, proxies=proxies)
    r.raise_for_status()

    data = r.json()
    return "".join([item[0] for item in data[0]])

text = "This paper proposes a congestion control algorithm for data center networks."
print(google_web_translate(text))
