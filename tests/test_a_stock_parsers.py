"""a_stock.py 数据层解析器单测：不打真实 API，全部 mock 网络层。"""

from __future__ import annotations

import pytest

import alphamind.dataflows.a_stock as a_stock


# ---------------------------------------------------------------------------
# _tencent_quote：腾讯 GBK ~ 分隔行情解析
# ---------------------------------------------------------------------------

def _make_tencent_line(code: str, name: str, price: str) -> str:
    """按腾讯 qt.gtimg.cn 响应格式构造一行（53+ 字段，~ 分隔）。"""
    vals = [""] * 60
    vals[1] = name          # 名称
    vals[3] = price         # 现价
    vals[4] = "10.00"       # 昨收
    vals[5] = "10.50"       # 今开
    vals[32] = "5.00"       # 涨跌幅
    vals[39] = "25.6"       # PE TTM
    vals[44] = "1200.5"     # 总市值(亿)
    vals[46] = "3.2"        # PB
    vals[47] = "11.00"      # 涨停价
    vals[48] = "9.00"       # 跌停价
    body = "~".join(vals)
    return f'v_sh{code}="{body}";'


def test_tencent_quote_parses_fields(monkeypatch):
    raw = _make_tencent_line("600000", "浦发银行", "10.50")
    monkeypatch.setattr(
        a_stock, "_http_get_json", lambda *a, **k: raw, raising=True
    )
    result = a_stock._tencent_quote(["600000"])

    assert "600000" in result
    q = result["600000"]
    assert q["name"] == "浦发银行"
    assert q["price"] == 10.50
    assert q["last_close"] == 10.00
    assert q["change_pct"] == 5.00
    assert q["pe_ttm"] == 25.6
    assert q["limit_up"] == 11.00
    assert q["limit_down"] == 9.00


def test_tencent_quote_skips_short_lines(monkeypatch):
    """字段数不足 53 的行（停牌/异常响应）应跳过而不是崩掉。"""
    short = 'v_sh600000="1~浦发银行~10.50";'
    monkeypatch.setattr(a_stock, "_http_get_json", lambda *a, **k: short)
    assert a_stock._tencent_quote(["600000"]) == {}


def test_tencent_quote_uses_correct_prefix(monkeypatch):
    """6/9 开头走 sh，8 开头走 bj，其余 sz。"""
    seen_urls: list[str] = []

    def fake_get(url, **kwargs):
        seen_urls.append(url)
        return ""

    monkeypatch.setattr(a_stock, "_http_get_json", fake_get)
    a_stock._tencent_quote(["600000", "000001", "830001"])

    assert "sh600000" in seen_urls[0]
    assert "sz000001" in seen_urls[0]
    assert "bj830001" in seen_urls[0]


# ---------------------------------------------------------------------------
# _http_get_json：重试 + 退避
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload: str):
        self._payload = payload
        self.encoding = None

    @property
    def text(self) -> str:
        return self._payload

    def json(self) -> dict:
        import json as _json
        return _json.loads(self._payload)


def test_http_get_json_retries_then_succeeds(monkeypatch):
    """前两次失败、第三次成功 → 返回结果且共调用 3 次。"""
    calls = {"n": 0}

    def flaky_get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("timeout")
        return _FakeResponse('{"ok": true}')

    monkeypatch.setattr(a_stock._requests, "get", flaky_get)
    monkeypatch.setattr(a_stock.time, "sleep", lambda s: None)  # 跳过退避等待

    assert a_stock._http_get_json("http://x/api") == {"ok": True}
    assert calls["n"] == 3


def test_http_get_json_exhausts_retries(monkeypatch):
    calls = {"n": 0}

    def always_fail(url, **kwargs):
        calls["n"] += 1
        raise ConnectionError("down")

    monkeypatch.setattr(a_stock._requests, "get", always_fail)
    monkeypatch.setattr(a_stock.time, "sleep", lambda s: None)

    with pytest.raises(ConnectionError):
        a_stock._http_get_json("http://x/api", retries=3)
    assert calls["n"] == 3


def test_http_get_json_text_mode_decodes_gbk(monkeypatch):
    monkeypatch.setattr(
        a_stock._requests,
        "get",
        lambda url, **k: _FakeResponse("name=浦发"),
    )
    out = a_stock._http_get_json("http://x", parse="text", encoding="gbk")
    assert out == "name=浦发"


# ---------------------------------------------------------------------------
# resolve_ticker：代码归一化与中文名歧义
# ---------------------------------------------------------------------------

def test_resolve_ticker_accepts_code_formats():
    assert a_stock.resolve_ticker("600379") == "600379"
    assert a_stock.resolve_ticker("SH600379") == "600379"
    assert a_stock.resolve_ticker("600379.SH") == "600379"
    assert a_stock.resolve_ticker("sh600379") == "600379"


def test_resolve_ticker_rejects_empty():
    with pytest.raises(ValueError):
        a_stock.resolve_ticker("   ")


def test_resolve_ticker_unique_name(monkeypatch):
    monkeypatch.setattr(
        a_stock,
        "_build_name_code_map",
        lambda: ({"浦发银行": "600000", "宝光股份": "600379"}, {"600000": "浦发银行"}),
    )
    assert a_stock.resolve_ticker("浦发银行") == "600000"


def test_resolve_ticker_ambiguous_name(monkeypatch):
    """模糊匹配到多只股票 → 报错并列出候选项，不静默选第一个。"""
    monkeypatch.setattr(
        a_stock,
        "_build_name_code_map",
        lambda: ({"银行A": "600001", "银行B": "600002"}, {}),
    )
    with pytest.raises(ValueError, match="匹配到多只股票"):
        a_stock.resolve_ticker("银行")


def test_resolve_ticker_unknown_name(monkeypatch):
    monkeypatch.setattr(
        a_stock, "_build_name_code_map", lambda: ({"浦发银行": "600000"}, {})
    )
    with pytest.raises(ValueError, match="找不到股票"):
        a_stock.resolve_ticker("不存在的股票")
