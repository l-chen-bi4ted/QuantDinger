# ============================================================
# Five-Factor Consensus Strategy — 移植自 AlphaGPT
# ------------------------------------------------------------
# 五因子（RET + LIQ + PRESSURE + FOMO + ROC20）共识投票，
# ADX 市场环境感知 + EMA3 平滑。
#
# 信号逻辑：
#   每个因子独立投票（+1 多 / -1 空 / 0 中性）
#   求和 → EMA3 平滑 → 超阈值触发 buy/sell
#   阈值随 ADX 动态调整（趋势市放宽，震荡市收紧）
# ============================================================

my_indicator_name = "5-Factor Consensus Strategy"
my_indicator_description = (
    "AlphaGPT 移植: RET+LIQ+PRESSURE+FOMO+ROC20 五因子共识投票。"
    "ADX 环境感知，EMA3 平滑，趋势市放宽阈值。"
    "适合 BTC/ETH 1H/4H 级别。"
)

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 0.5
# @strategy tradeDirection both

# @param ret_period int 12 回报计算周期 range=8:20:1
# @param vol_ma int 20 成交量均线周期 range=10:30:2
# @param fomo_ma int 20 FOMO SMA 周期 range=10:30:2
# @param roc_period int 20 ROC 周期 range=10:30:2
# @param adx_period int 14 ADX 周期 range=10:20:1
# @param ema_signal int 3 信号平滑 EMA range=2:6:1
# @param threshold_ranging float 2.5 震荡市信号阈值 range=1.5:3.5:0.1
# @param threshold_trending float 1.5 趋势市信号阈值 range=1.0:2.5:0.1

import numpy as np
import pandas as pd

ret_period = int(params.get('ret_period', 12))
vol_ma = int(params.get('vol_ma', 20))
fomo_ma = int(params.get('fomo_ma', 20))
roc_period = int(params.get('roc_period', 20))
adx_period = int(params.get('adx_period', 14))
ema_signal = int(params.get('ema_signal', 3))

df = df.copy()
high = df['high'].values
low = df['low'].values
close = df['close'].values
volume = df['volume'].values
n = len(df)

# ---- 1) ADX ----
tr = np.maximum(high - low,
    np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
tr[0] = high[0] - low[0]
atr = pd.Series(tr).ewm(alpha=1/adx_period, adjust=False).mean().values

sp = np.where(high - np.roll(high, 1) > 0, high - np.roll(high, 1), 0)
sm = np.where(np.roll(low, 1) - low > 0, np.roll(low, 1) - low, 0)
sp[0], sm[0] = 0, 0
di_plus = pd.Series(np.where(atr > 0, 100 * sp / atr, 0)).ewm(alpha=1/adx_period, adjust=False).mean().values
di_minus = pd.Series(np.where(atr > 0, 100 * sm / atr, 0)).ewm(alpha=1/adx_period, adjust=False).mean().values
dx = np.where(di_plus + di_minus > 0, 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus), 0)
adx = pd.Series(dx).ewm(alpha=1/adx_period, adjust=False).mean().values

# ---- 2) 五因子计算 ----
sma = pd.Series(close).rolling(ret_period).mean().values
sma20 = pd.Series(close).rolling(fomo_ma).mean().values
vol_sma = pd.Series(volume).rolling(vol_ma).mean().values

ret = np.full(n, 0.0)
roc20 = np.full(n, 0.0)
fomo_raw = np.full(n, 0.0)
liq = np.full(n, 0.0)
pressure = np.full(n, 0.0)

for i in range(1, n):
    if i >= ret_period:
        ret[i] = (close[i] / close[i - ret_period] - 1) * 100
    if i >= roc_period:
        roc20[i] = (close[i] / close[i - roc_period] - 1) * 100
    if i >= fomo_ma and sma20[i] > 0:
        fomo_raw[i] = (close[i] - sma20[i]) / sma20[i]
    if i >= vol_ma and vol_sma[i] > 0:
        liq[i] = (volume[i] - vol_sma[i]) / vol_sma[i]
    # 买压: (close - low) / (high - low)
    rng = high[i] - low[i]
    if rng > 0:
        pressure[i] = (close[i] - low[i]) / rng - 0.5  # -0.5 ~ +0.5

# ---- 3) 因子投票 ----
votes = np.zeros((n, 5))

for i in range(n):
    # RET: 涨跌方向
    if i >= ret_period:
        votes[i, 0] = 1 if ret[i] > 0.5 else (-1 if ret[i] < -0.5 else 0)

    # ROC20: 趋势动量
    if i >= roc_period:
        votes[i, 1] = 1 if roc20[i] > 1.0 else (-1 if roc20[i] < -1.0 else 0)

    # FOMO: 价格偏离均线
    if i >= fomo_ma:
        votes[i, 2] = 1 if fomo_raw[i] > 0.02 else (-1 if fomo_raw[i] < -0.02 else 0)

    # LIQ: 成交量放大/缩小
    if i >= vol_ma:
        votes[i, 3] = 1 if liq[i] > 0.3 else (-1 if liq[i] < -0.3 else 0)

    # PRESSURE: 买卖压力
    votes[i, 4] = 1 if pressure[i] > 0.1 else (-1 if pressure[i] < -0.1 else 0)

# ---- 4) 共识信号 ----
raw_signal = np.sum(votes, axis=1)  # -5 ~ +5

# EMA 平滑
signal = pd.Series(raw_signal).ewm(span=ema_signal, adjust=False).mean().values

# ---- 5) ADX 动态阈值 ----
threshold_ranging = float(params.get('threshold_ranging', 2.5))
threshold_trending = float(params.get('threshold_trending', 1.5))

buy = np.zeros(n, dtype=bool)
sell = np.zeros(n, dtype=bool)

for i in range(1, n):
    if i < adx_period:
        continue
    thresh = threshold_trending if adx[i] >= 25 else threshold_ranging

    # DI 方向过滤器: 趋势市只允许顺趋势方向开仓
    di_long_ok = di_plus[i] > di_minus[i]   # 多头占优
    di_short_ok = di_minus[i] > di_plus[i]  # 空头占优
    if adx[i] >= 25:
        buy_cond = signal[i] > thresh and signal[i-1] <= thresh and di_long_ok
        sell_cond = signal[i] < -thresh and signal[i-1] >= -thresh and di_short_ok
    else:
        buy_cond = signal[i] > thresh and signal[i-1] <= thresh
        sell_cond = signal[i] < -thresh and signal[i-1] >= -thresh

    if buy_cond:
        buy[i] = True
    elif sell_cond:
        sell[i] = True

df['buy'] = pd.Series(buy)
df['sell'] = pd.Series(sell)

# ---- 6) 输出 ----
# 各因子曲线
ret_series = [float(v) if not np.isnan(v) else None for v in ret]
roc20_series = [float(v) if not np.isnan(v) else None for v in roc20]
fomo_series = [float(v) if not np.isnan(v) else None for v in fomo_raw]
adx_series = [float(v) if not np.isnan(v) else None for v in adx]
signal_series = [float(v) if not np.isnan(v) else None for v in signal]

# 买卖标记（价格附近）
buy_marks = [float(close[i] * 0.995) if buy[i] else None for i in range(n)]
sell_marks = [float(close[i] * 1.005) if sell[i] else None for i in range(n)]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': 'ADX', 'data': adx_series, 'color': '#FF9800', 'overlay': False},
        {'name': 'Consensus', 'data': signal_series, 'color': '#E040FB', 'overlay': False},
        {'name': 'RET%', 'data': ret_series, 'color': '#42A5F5', 'overlay': False},
        {'name': 'ROC20%', 'data': roc20_series, 'color': '#26A69A', 'overlay': False},
        {'name': 'FOMO', 'data': fomo_series, 'color': '#FFA726', 'overlay': False},
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'},
    ],
}
