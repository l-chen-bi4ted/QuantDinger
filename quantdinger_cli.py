#!/usr/bin/env python3
"""QuantDinger CLI — 从 Hermes 调用的数据分析工具"""

import json, os, urllib.request, urllib.error, sys, time

BASE = "http://127.0.0.1:5001"

# 从 .env 读密码
ENV_FILE = os.path.expanduser("~/QuantDinger/backend_api_python/.env")
_token = None


def _get_token():
    global _token
    if _token:
        return _token
    pw = None
    with open(ENV_FILE) as f:
        for line in f:
            if line.startswith("ADMIN_PASSWORD="):
                pw = line.strip().split("=", 1)[1]
                break
    if not pw:
        print("ERROR: ADMIN_PASSWORD not found in .env")
        sys.exit(1)
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"username": "quantdinger", "password": pw}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req).read())
        _token = resp["data"]["token"]
        return _token
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)


def _api(method, path, body=None, params=None):
    url = f"{BASE}{path}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items() if v is not None)
        url = f"{url}?{qs}"
    headers = {"Authorization": f"Bearer {_get_token()}"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    else:
        data = None
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        resp = json.loads(urllib.request.urlopen(req).read())
        return resp
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def cmd_price(args):
    """当前价格"""
    r = _api("GET", "/api/market/price", params={"symbol": args.symbol, "market": "Crypto"})
    if r and r.get("code") == 1:
        d = r["data"]
        chg = d.get("changePercent", 0)
        arrow = "📈" if chg > 0 else "📉"
        print(f"{d['symbol']:10s} ${d['price']:<10,.2f}  {chg:+.2f}% {arrow}")


def cmd_kline(args):
    """K 线数据 (OHLCV)"""
    r = _api("GET", "/api/indicator/kline", params={
        "symbol": args.symbol, "market": "Crypto",
        "interval": args.interval, "limit": args.limit,
    })
    if r and r.get("code") == 1:
        data = r["data"]
        print(f"{'time':>20s}  {'open':>10s}  {'high':>10s}  {'low':>10s}  {'close':>10s}  {'volume':>12s}")
        print("-" * 80)
        for d in data[-args.limit:]:
            t = time.strftime("%m/%d %H:%M", time.gmtime(d["time"]))
            print(f"{t:>20s}  {d['open']:>10.2f}  {d['high']:>10.2f}  {d['low']:>10.2f}  {d['close']:>10.2f}  {d['volume']:>12.2f}")


def cmd_balance(args):
    """账户余额"""
    r = _api("GET", "/api/quick-trade/balance", params={"symbol": args.symbol, "market": "Crypto"})
    if r and r.get("code") == 1:
        print(json.dumps(r["data"], indent=2, ensure_ascii=False))


def cmd_positions(args):
    """持仓"""
    r = _api("GET", "/api/portfolio/positions")
    if r and r.get("code") == 1:
        data = r["data"]
        if not data:
            print("No positions")
            return
        if isinstance(data, list):
            for p in data:
                print(f"{p.get('symbol',''):10s} {p.get('side',''):6s} {p.get('size',0):>8.4f}  PnL {p.get('pnl',0):+.2f}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False)[:500])


def cmd_strategies(args):
    """策略列表"""
    r = _api("GET", "/api/strategies")
    if r and r.get("code") == 1:
        data = r["data"]
        if isinstance(data, list):
            for s in data:
                status = s.get("status", "?")
                name = s.get("name", "?")
                symbol = s.get("symbol", "")
                print(f"  {s.get('id','?'):>4d}  {name:20s}  {symbol:10s}  {status}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False)[:500])


def cmd_backtest(args):
    """运行回测"""
    body = {
        "symbol": args.symbol, "market": "Crypto",
        "interval": args.interval,
        "start_time": args.start, "end_time": args.end,
        "initial_capital": args.capital,
        "strategy_code": args.code,
    }
    r = _api("POST", "/api/strategies/backtest", body=body)
    if r:
        print(json.dumps(r, indent=2, ensure_ascii=False)[:2000])


def cmd_indicators(args):
    """可用指标列表"""
    r = _api("GET", "/api/indicator/getIndicators")
    if r and r.get("code") == 1:
        for ind in (r["data"] or [])[:20]:
            print(f"  {ind.get('name','?'):25s}  {ind.get('description','')[:60]}")


def cmd_ai_analyze(args):
    """AI 市场分析"""
    r = _api("POST", "/api/fast-analysis/analyze", body={
        "symbol": args.symbol, "market": "Crypto", "interval": args.interval,
    })
    if r:
        out = json.dumps(r, indent=2, ensure_ascii=False)
        print(out[:3000])


def cmd_agent_klines(args):
    """Agent API — K线"""
    r = _api("GET", "/api/agent/v1/klines", params={
        "symbol": args.symbol, "interval": args.interval, "limit": args.limit,
    })
    if r:
        print(json.dumps(r, indent=2, ensure_ascii=False)[:2000])


def cmd_agent_price(args):
    """Agent API — 价格"""
    r = _api("GET", "/api/agent/v1/price", params={"symbol": args.symbol})
    if r:
        print(json.dumps(r, indent=2, ensure_ascii=False)[:500])


def cmd_help(args):
    print("""
QuantDinger CLI — 数据分析工具

用法:
  ./quantdinger.py <command> [options]

命令:
  price      当前价格
    --symbol BTCUSDT (默认)

  kline      K 线数据 (OHLCV)
    --symbol BTCUSDT   --interval 1h   --limit 50

  balance    账户余额
    --symbol BTCUSDT

  positions  当前持仓

  strategies 策略列表

  indicators 可用指标列表

  backtest   运行回测
    --symbol BTCUSDT   --code 'strategy code'   --capital 10000

  ai         市场 AI 分析
    --symbol BTCUSDT   --interval 1h

  agent-k    通过 Agent API 拉 K 线
    --symbol BTCUSDT   --limit 50

  agent-p    Agent API 价格
    --symbol BTCUSDT

示例:
  ./quantdinger.py kline --symbol BTCUSDT --interval 1h --limit 24
  ./quantdinger.py price
  ./quantdinger.py ai --symbol BTCUSDT --interval 4h
""")


if __name__ == "__main__":
    import argparse
    import urllib.parse

    p = argparse.ArgumentParser(add_help=False)
    sub = p.add_subparsers(dest="cmd")

    # price
    px = sub.add_parser("price")
    px.add_argument("--symbol", default="BTCUSDT")

    # kline
    kl = sub.add_parser("kline")
    kl.add_argument("--symbol", default="BTCUSDT")
    kl.add_argument("--interval", default="1h")
    kl.add_argument("--limit", type=int, default=50)

    # balance
    ba = sub.add_parser("balance")
    ba.add_argument("--symbol", default="BTCUSDT")

    # positions
    sub.add_parser("positions")

    # strategies
    sub.add_parser("strategies")

    # indicators
    sub.add_parser("indicators")

    # backtest
    bt = sub.add_parser("backtest")
    bt.add_argument("--symbol", default="BTCUSDT")
    bt.add_argument("--interval", default="1h")
    bt.add_argument("--start")
    bt.add_argument("--end")
    bt.add_argument("--capital", type=float, default=10000)
    bt.add_argument("--code", required=True)

    # ai
    ai = sub.add_parser("ai")
    ai.add_argument("--symbol", default="BTCUSDT")
    ai.add_argument("--interval", default="1h")

    # agent klines
    ak = sub.add_parser("agent-k")
    ak.add_argument("--symbol", default="BTCUSDT")
    ak.add_argument("--interval", default="1h")
    ak.add_argument("--limit", type=int, default=50)

    # agent price
    ap = sub.add_parser("agent-p")
    ap.add_argument("--symbol", default="BTCUSDT")

    sub.add_parser("help")

    args = p.parse_args()

    cmds = {
        "price": cmd_price, "kline": cmd_kline,
        "balance": cmd_balance, "positions": cmd_positions,
        "strategies": cmd_strategies, "indicators": cmd_indicators,
        "backtest": cmd_backtest, "ai": cmd_ai_analyze,
        "agent-k": cmd_agent_klines, "agent-p": cmd_agent_price,
        "help": cmd_help,
    }

    if args.cmd in cmds:
        cmds[args.cmd](args)
    else:
        cmd_help(args)
