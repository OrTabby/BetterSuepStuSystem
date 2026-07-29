"""CAS 统一认证登录

上海电力大学使用 CAS (Central Authentication Service) 协议进行统一认证。
流程：
  1. GET /authserver/login → 获取页面中的隐藏字段 (lt, execution, _eventId)
  2. POST 用户名 + 密码 + 隐藏字段 → 提交登录
  3. 处理重定向和 Ticket → 访问目标系统
"""

import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs, urljoin

import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

try:
    from .config import CAS_LOGIN_URL, CAS_CAPTCHA_URL, REQUEST_TIMEOUT, USE_PROXY, PROXY_URL
except ImportError:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from app.config import CAS_LOGIN_URL, CAS_CAPTCHA_URL, REQUEST_TIMEOUT, USE_PROXY, PROXY_URL


class AuthSession:
    """CAS 认证会话"""

    def __init__(self, proxy_url: str = ""):
        self.session = requests.Session()
        self.session.trust_env = False
        # 教务系统使用的旧证书在 Python 证书库中无法通过校验；
        # 浏览器链路本身可访问，这里仅对本地自用客户端放宽校验。
        self.session.verify = False
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        })

        # 配置代理
        if USE_PROXY and proxy_url:
            # 让 SOCKS5 代理负责 DNS 解析，避免本机 DNS 与浏览器路径不一致。
            requests_proxy_url = proxy_url
            if requests_proxy_url.startswith("socks5://"):
                requests_proxy_url = "socks5h://" + requests_proxy_url[len("socks5://"):]
            self.session.proxies = {
                "http": requests_proxy_url,
                "https": requests_proxy_url,
            }
            print(f"[Auth] 使用代理: {requests_proxy_url}")

        self._authenticated = False
        self.last_error = ""
        self._login_redirect_url = ""

    # ── 公开方法 ──────────────────────────────────────────

    def login(self, username: str, password: str, service_url: str = "") -> bool:
        """执行 CAS 登录

        注意：带 service 参数获取的登录页是 JS 动态渲染的，
        lt/execution 需要从无 service 的页面获取。

        Args:
            username: 学号
            password: 统一认证密码
            service_url: 登录后要跳转的目标服务（教务系统 URL）

        Returns:
            是否登录成功
        """
        self.last_error = ""
        for attempt in range(1, 4):
            timeout = self._timeout_for_attempt(attempt)
            try:
                # Step 1: 必须从带 service 的 CAS 页面获取 token。
                # 不带 service 时，CAS 可能创建另一条认证会话，提交后无法回到教务系统。
                page = self._fetch_login_page(service_url=service_url, timeout=timeout)
                lt, execution, captcha_on = self._parse_hidden_fields(page)

                if not lt or not execution:
                    if self._login_redirect_url:
                        resp = self._follow_eams_redirects(
                            self._login_redirect_url,
                            timeout=timeout,
                        )
                        self._authenticated = self._check_success(resp, username)
                        return self._authenticated
                    self.last_error = "未能获取登录令牌（lt/execution）"
                    print(f"[!] {self.last_error}")
                    return False

                # Step 2: 如果有验证码，提示用户（暂不处理）
                if captcha_on:
                    print("[!] 验证码已开启，后续需处理验证码识别")

                # Step 3: 提交登录（service 参数放在 URL 中）
                resp = self._submit_login(
                    username,
                    password,
                    lt,
                    execution,
                    service_url,
                    timeout=timeout,
                )

                # Step 4: 检查结果
                self._authenticated = self._check_success(resp, username)
                return self._authenticated

            except requests.RequestException as e:
                self.last_error = str(e)
                print(f"[!] 网络请求失败 ({attempt}/3): {e}")
                if attempt < 3:
                    time.sleep(2 * attempt)

        return False

    def is_authenticated(self) -> bool:
        return self._authenticated

    def get_session(self) -> requests.Session:
        """获取已认证的 requests Session，供 scraper 使用"""
        return self.session

    # ── 内部方法 ──────────────────────────────────────────

    def _timeout_for_attempt(self, attempt: int) -> tuple[int, int]:
        """逐次放宽读取超时：正常情况快，偶发慢请求留兜底。"""
        read_timeout = min(REQUEST_TIMEOUT, (12, 24, REQUEST_TIMEOUT)[attempt - 1])
        return (8, read_timeout)

    def _fetch_login_page(self, service_url: str = "", timeout=None) -> str:
        """GET /login，获取登录页面 HTML"""
        params = {}
        if service_url:
            params["service"] = service_url

        self._login_redirect_url = ""
        resp = self.session.get(
            CAS_LOGIN_URL,
            params=params,
            timeout=timeout or REQUEST_TIMEOUT,
            allow_redirects=False,
        )
        if resp.is_redirect:
            location = resp.headers.get("Location", "")
            self._login_redirect_url = urljoin(resp.url, location)
            self.last_error = f"CAS 已重定向到目标系统，未返回登录表单：{location}"
            return ""
        resp.encoding = "utf-8"
        return resp.text

    def _parse_hidden_fields(self, html: str) -> tuple[str, str, bool]:
        """从登录页提取 hidden 字段"""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form", id="loginForm") or soup.find("form")

        lt = ""
        execution = ""
        captcha_on = False

        if form:
            lt_input = form.find("input", {"name": "lt"})
            if lt_input and lt_input.get("value"):
                lt = lt_input["value"]

            exec_input = form.find("input", {"name": "execution"})
            if exec_input and exec_input.get("value"):
                execution = exec_input["value"]

            # 检查验证码
            captcha_img = form.find("img", {"id": "captchaImg"})
            captcha_on = captcha_img is not None

        if not lt or not execution:
            # fallback: 正则提取
            lt = re.search(r'name="lt"\s+value="([^"]+)"', html)
            execution = re.search(r'name="execution"\s+value="([^"]+)"', html)
            lt = lt.group(1) if lt else ""
            execution = execution.group(1) if execution else ""

        return lt, execution, captcha_on

    def _submit_login(
        self,
        username: str,
        password: str,
        lt: str,
        execution: str,
        service_url: str = "",
        timeout=None,
    ) -> requests.Response:
        """POST 提交登录表单"""
        data = {
            "username": username,
            "password": password,
            "lt": lt,
            "dllt": "userNamePasswordLogin",
            "execution": execution,
            "_eventId": "submit",
            "rmShown": "1",
        }
        params = {}
        if service_url:
            params["service"] = service_url

        resp = self.session.post(
            CAS_LOGIN_URL,
            data=data,
            params=params,
            timeout=timeout or REQUEST_TIMEOUT,
            allow_redirects=False,
        )

        # CAS 通常把 ticket 发往 http://jw...，而该站点会再跳到 HTTPS。
        # 直接从 HTTPS 兑换 ticket，避免代理在 80/443 之间反复跳转或卡在 80 端口。
        location = resp.headers.get("Location")
        if resp.is_redirect and location:
            target_url = urljoin(resp.url, location)
            resp = self._follow_eams_redirects(target_url, timeout=timeout)
        return resp

    def _follow_eams_redirects(self, url: str, timeout=None) -> requests.Response:
        """手动跟随教务系统跳转，避开不稳定的 http://jw 端口。"""
        current_url = url
        resp = self._get_with_eams_scheme_fallback(current_url, timeout=timeout)

        for _ in range(8):
            if not resp.is_redirect:
                return resp

            location = resp.headers.get("Location")
            if not location:
                return resp
            current_url = urljoin(resp.url, location)
            resp = self._get_with_eams_scheme_fallback(current_url, timeout=timeout)

        return resp

    def _get_with_eams_scheme_fallback(self, url: str, timeout=None) -> requests.Response:
        try:
            return self.session.get(
                url,
                timeout=timeout or REQUEST_TIMEOUT,
                allow_redirects=False,
            )
        except requests.RequestException:
            alternate = self._alternate_eams_scheme_url(url)
            if not alternate:
                raise
            print(f"[Auth] retry EAMS with alternate scheme: {alternate}")
            return self.session.get(
                alternate,
                timeout=timeout or REQUEST_TIMEOUT,
                allow_redirects=False,
            )

    def _alternate_eams_scheme_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.hostname != "jw.shiep.edu.cn":
            return ""
        if parsed.scheme == "http":
            return "https://" + url[len("http://"):]
        if parsed.scheme == "https":
            return "http://" + url[len("https://"):]
        return ""

    def _check_success(self, resp: requests.Response, username: str) -> bool:
        """判断登录是否成功"""
        if resp.status_code >= 400:
            print(f"[!] 登录失败：目标系统返回 HTTP {resp.status_code}")
            return False
        # 成功时通常会重定向到目标服务，URL 中带 ticket 参数
        # 失败时会返回登录页，其中包含错误提示
        if "login" in resp.url.lower() and "error" in resp.text.lower():
            print("[!] 登录失败：用户名或密码错误")
            return False
        if "应用未注册" in resp.text or "不允许使用认证服务" in resp.text:
            print("[!] 登录失败：CAS service 地址未注册")
            return False
        if "authserver" in resp.url.lower() and "/login" in resp.url.lower():
            print("[!] 登录失败：仍停留在 CAS 登录页")
            return False
        if urlparse(resp.url).hostname != "jw.shiep.edu.cn":
            print(f"[!] 登录失败：未跳转到教务系统（{resp.url}）")
            return False
        if username in resp.text and ("密码" in resp.text or "错误" in resp.text):
            return False
        return True

    def close(self):
        self.session.close()
