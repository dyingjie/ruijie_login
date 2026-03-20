from __future__ import annotations

import argparse
import http.cookiejar
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Optional


JS_SAFE = "-_.!~*'()"


@dataclass
class PortalConfig:
    portal_url: str
    username: str = ""
    password: str = ""
    service: str = ""
    timeout_seconds: float = 20.0
    use_portal_prefix: bool = False


class PortalError(RuntimeError):
    pass


class PortalSession:
    def __init__(self, portal_url: str, timeout_seconds: float) -> None:
        parsed = urllib.parse.urlsplit(portal_url)
        if not parsed.scheme or not parsed.netloc:
            raise PortalError("portal_url 不是有效的 URL。")
        if not parsed.query:
            raise PortalError("portal_url 必须包含认证页完整查询参数。")
        base_path = parsed.path.rsplit("/", 1)[0] + "/"
        self.portal_url = portal_url
        self.query_string = parsed.query
        self.root_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, base_path, "", ""))
        self.timeout_seconds = timeout_seconds
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
        }

    def request(self, method: str, url: str, body: Optional[str] = None) -> str:
        data = body.encode("utf-8") if body is not None else None
        headers = dict(self.default_headers)
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PortalError(f"请求失败: {exc.code} {exc.reason} {detail}") from exc
        except urllib.error.URLError as exc:
            raise PortalError(f"网络请求失败: {exc.reason}") from exc

    def interface_call(self, method_name: str, body: str) -> dict:
        interface_url = urllib.parse.urljoin(self.root_url, f"InterFace.do?method={method_name}")
        response_text = self.request("POST", interface_url, body)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise PortalError(f"{method_name} 返回了无法解析的响应: {response_text[:200]}") from exc

    def open_login_page(self) -> None:
        self.request("GET", self.portal_url)

    def get_page_info(self) -> dict:
        body = "queryString=" + js_quote(self.query_string)
        return self.interface_call("pageInfo", body)

    def get_services(self) -> dict:
        body = "queryString=" + js_quote(self.query_string)
        return self.interface_call("getServices", body)

    def get_online_user_info(self, user_index: str = "") -> dict:
        body = "userIndex=" + js_quote(user_index)
        return self.interface_call("getOnlineUserInfo", body)

    def login(
        self,
        username: str,
        password: str,
        service: str,
        page_info: dict,
        use_portal_prefix: bool,
    ) -> dict:
        final_username = username
        if page_info.get("prefixName") == "true" and use_portal_prefix:
            final_username = page_info.get("prefixValue", "") + username

        encrypt_flag = "true" if page_info.get("passwordEncrypt") == "true" else "false"
        final_password = password
        if encrypt_flag == "true":
            mac = extract_mac(self.query_string)
            final_password = encrypt_password(
                plain_text=f"{password}>{mac}",
                exponent_hex=page_info.get("publicKeyExponent", ""),
                modulus_hex=page_info.get("publicKeyModulus", ""),
            )

        body = "&".join(
            [
                "userId=" + double_js_quote(final_username),
                "password=" + double_js_quote(final_password),
                "service=" + double_js_quote(service),
                "queryString=" + double_js_quote(self.query_string),
                "operatorPwd=",
                "operatorUserId=",
                "validcode=",
                "passwordEncrypt=" + double_js_quote(encrypt_flag),
            ]
        )
        return self.interface_call("login", body)


def js_quote(value: str) -> str:
    return urllib.parse.quote(value, safe=JS_SAFE)


def double_js_quote(value: str) -> str:
    return js_quote(js_quote(value))


def extract_mac(query_string: str) -> str:
    params = urllib.parse.parse_qs(query_string, keep_blank_values=True)
    return params.get("mac", ["111111111"])[0] or "111111111"


def encrypt_password(plain_text: str, exponent_hex: str, modulus_hex: str) -> str:
    if not exponent_hex or not modulus_hex:
        raise PortalError("页面没有返回 RSA 公钥，无法加密密码。")
    exponent = int(exponent_hex, 16)
    modulus = int(modulus_hex, 16)
    stripped_modulus = modulus_hex.lstrip("0") or "0"
    chunk_size = 2 * max(1, (len(stripped_modulus) + 3) // 4 - 1)
    characters = [ord(char) for char in plain_text[::-1]]
    while len(characters) % chunk_size != 0:
        characters.append(0)

    blocks: List[str] = []
    for offset in range(0, len(characters), chunk_size):
        block_value = 0
        index = 0
        for position in range(offset, offset + chunk_size, 2):
            low = characters[position]
            high = characters[position + 1] if position + 1 < offset + chunk_size else 0
            digit = low + (high << 8)
            block_value += digit << (16 * index)
            index += 1
        encrypted = pow(block_value, exponent, modulus)
        blocks.append(format(encrypted, "x"))
    return " ".join(blocks)


def choose_service(configured_service: str, services_info: dict) -> str:
    if configured_service:
        return configured_service
    raw_service_json = services_info.get("serviceJson") or services_info.get("services") or "[]"
    try:
        services = json.loads(raw_service_json)
    except json.JSONDecodeError:
        return ""
    if not services:
        return ""
    for item in services:
        if item.get("serviceDefault") == "true":
            return item.get("serviceName", "")
    return services[0].get("serviceName", "")


def load_config(path: pathlib.Path) -> PortalConfig:
    if not path.exists():
        raise PortalError(f"没有找到配置文件: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PortalError(f"配置文件不是合法 JSON: {path}") from exc
    return PortalConfig(
        portal_url=str(raw.get("portal_url", "")).strip(),
        username=str(raw.get("username", "")).strip(),
        password=str(raw.get("password", "")),
        service=str(raw.get("service", "")).strip(),
        timeout_seconds=float(raw.get("timeout_seconds", 20)),
        use_portal_prefix=bool(raw.get("use_portal_prefix", False)),
    )


def merge_cli_overrides(config: PortalConfig, args: argparse.Namespace) -> PortalConfig:
    return PortalConfig(
        portal_url=args.portal_url or config.portal_url,
        username=args.username if args.username is not None else config.username,
        password=args.password if args.password is not None else config.password,
        service=args.service if args.service is not None else config.service,
        timeout_seconds=args.timeout if args.timeout is not None else config.timeout_seconds,
        use_portal_prefix=(
            args.use_portal_prefix
            if args.use_portal_prefix is not None
            else config.use_portal_prefix
        ),
    )


def run_status(config: PortalConfig) -> int:
    session = PortalSession(config.portal_url, config.timeout_seconds)
    session.open_login_page()
    online_info = session.get_online_user_info()
    result = online_info.get("result", "")
    if result == "success" and online_info.get("userIndex"):
        print("当前已在线。")
        print(f"userId: {online_info.get('userId', '')}")
        print(f"userName: {online_info.get('userName', '')}")
        print(f"userGroup: {online_info.get('userGroup', '')}")
        return 0
    print(f"当前未确认在线，portal 返回: {result or 'unknown'}")
    if online_info.get("message"):
        print(online_info["message"])
    return 1


def run_api_login(config: PortalConfig) -> int:
    session = PortalSession(config.portal_url, config.timeout_seconds)
    session.open_login_page()

    online_info = session.get_online_user_info()
    if online_info.get("result") == "success" and online_info.get("userIndex"):
        print("当前已经在线，无需重复认证。")
        return 0

    if not config.username or not config.password:
        raise PortalError("API 模式需要在 config.json 中填写 username 和 password。")

    page_info = session.get_page_info()
    services_info = session.get_services()
    service = choose_service(config.service, services_info)
    login_result = session.login(
        username=config.username,
        password=config.password,
        service=service,
        page_info=page_info,
        use_portal_prefix=config.use_portal_prefix,
    )

    if login_result.get("result") == "success":
        print("认证成功。")
        if login_result.get("message"):
            print(login_result["message"])
        if login_result.get("userIndex"):
            print(f"userIndex: {login_result['userIndex']}")
        return 0

    message = login_result.get("message", "未知错误")
    if login_result.get("validCodeUrl"):
        raise PortalError(
            "认证失败，portal 要求验证码。当前项目只支持 API 模式，无法自动处理验证码。\n"
            f"portal message: {message}"
        )
    raise PortalError(f"认证失败: {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ruijie_login CLI helper.")
    parser.add_argument("--config", default="config.json", help="配置文件路径，默认使用 config.json")
    parser.add_argument("--portal-url", help="覆盖配置文件中的 portal_url")
    parser.add_argument("--username", help="覆盖配置文件中的 username")
    parser.add_argument("--password", help="覆盖配置文件中的 password")
    parser.add_argument("--service", help="覆盖配置文件中的 service")
    parser.add_argument("--timeout", type=float, help="超时时间，单位秒")
    add_boolean_override(parser, "use-portal-prefix", "是否自动追加 portal 返回的账号前缀")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("login", help="执行认证登录")
    subparsers.add_parser("status", help="查询当前在线状态")
    return parser


def add_boolean_override(parser: argparse.ArgumentParser, name: str, help_text: str) -> None:
    dest = name.replace("-", "_")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(f"--{name}", dest=dest, action="store_true", help=help_text)
    group.add_argument(f"--no-{name}", dest=dest, action="store_false", help=f"关闭: {help_text}")
    parser.set_defaults(**{dest: None})


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "login"
    try:
        config = load_config(pathlib.Path(args.config))
        config = merge_cli_overrides(config, args)
        if not config.portal_url:
            raise PortalError("config.json 里的 portal_url 不能为空。")
        if command == "status":
            return run_status(config)
        return run_api_login(config)
    except PortalError as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
