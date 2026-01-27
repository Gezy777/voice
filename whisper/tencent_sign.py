# -*- coding: utf-8 -*-
import os
import json
import time
import hashlib
import hmac
from datetime import datetime
from http.client import HTTPSConnection
from dotenv import load_dotenv


# ---------- 基础工具 ----------
def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


# ---------- 核心请求函数 ----------
def tc3_request(
    *,
    service: str,
    action: str,
    payload: dict,
    region: str = "",
    version: str = "2018-03-21",
    host: str = None,
    timeout: int = 10,
):
    """
    通用腾讯云 TC3 API 请求封装
    """

    load_dotenv()

    secret_id = os.getenv("TENCENTCLOUD_SECRET_ID")
    secret_key = os.getenv("TENCENTCLOUD_SECRET_KEY")

    if not secret_id or not secret_key:
        raise RuntimeError("Missing TENCENTCLOUD_SECRET_ID / SECRET_KEY")

    if not host:
        host = f"{service}.tencentcloudapi.com"

    endpoint = host
    algorithm = "TC3-HMAC-SHA256"
    timestamp = int(time.time())
    date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    # ===== Step 1: Canonical Request =====
    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    content_type = "application/json; charset=utf-8"

    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-tc-action:{action.lower()}\n"
    )

    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    canonical_request = (
        http_request_method + "\n" +
        canonical_uri + "\n" +
        canonical_querystring + "\n" +
        canonical_headers + "\n" +
        signed_headers + "\n" +
        hashed_payload
    )

    # ===== Step 2: String To Sign =====
    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical_request = hashlib.sha256(
        canonical_request.encode("utf-8")
    ).hexdigest()

    string_to_sign = (
        f"{algorithm}\n"
        f"{timestamp}\n"
        f"{credential_scope}\n"
        f"{hashed_canonical_request}"
    )

    # ===== Step 3: Signature =====
    secret_date = _sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _sign(secret_date, service)
    secret_signing = _sign(secret_service, "tc3_request")

    signature = hmac.new(
        secret_signing,
        string_to_sign.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # ===== Step 4: Authorization =====
    authorization = (
        f"{algorithm} "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    # ===== Step 5: HTTP Request =====
    headers = {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
    }
    if region:
        headers["X-TC-Region"] = region

    conn = HTTPSConnection(endpoint, timeout=timeout)
    conn.request("POST", "/", body=payload_json.encode("utf-8"), headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8")

    if resp.status != 200:
        raise RuntimeError(f"HTTP {resp.status}: {data}")

    return json.loads(data)
