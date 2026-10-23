"""极简鉴权：HMAC 签名的会话 cookie + 单密码。

生产环境应替换为企业身份源（LDAP/SSO）；这里是给"公网只放行授权用户"的最小门槛：
  - APP_PASSWORD：登录密码
  - APP_SECRET：签名密钥（务必在生产改成强随机值）
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

PASSWORD = os.environ.get("APP_PASSWORD", "demo")
SECRET = os.environ.get("APP_SECRET", "change-me-in-prod")
MAX_AGE_SECONDS = 24 * 3600


def _sign(payload: str) -> str:
    return hmac.new(SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_token() -> str:
    ts = str(int(time.time()))
    return f"{ts}.{_sign(ts)}"


def verify_token(token: str) -> bool:
    try:
        ts, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(ts)):
            return False
        return (time.time() - int(ts)) < MAX_AGE_SECONDS
    except (ValueError, TypeError):
        return False


def check_password(pwd: str) -> bool:
    return hmac.compare_digest(pwd, PASSWORD)
