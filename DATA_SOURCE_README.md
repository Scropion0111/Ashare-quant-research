# EigenFlow 数据源设置指南 v3.5

## 目录结构（极简同级目录）

所有文件都在 GitHub 仓库根目录，无需子文件夹：

```
<username>/<repo>/
├── regime_snapshot.json      # 实时快照（T+1展望）
├── web_top10.csv             # Top10信号（付费内容）
└── regime_history.csv         # 完整历史数据
```

## 文件格式说明

### 1. regime_snapshot.json（核心文件）

**用途**：首页顶部展示"次日市场展望"

```json
{
  "target_date": "2026-02-10",       // 目标交易日（T+1）
  "calculation_date": "2026-02-09",   // 计算日期（T）
  "market_regime": "Risk Off",        // 市场状态：Risk On / Risk Off
  "action": "Defensive",              // 行动建议：Offensive / Defensive
  "shibor_2w": 1.584,                // Shibor 2周利率
  "rsi_5": 54.54,                    // RSI-5 指标
  "signal_strength": "Medium",        // 信号强度
  "last_updated": "2026-02-09 21:16"  // 更新时间
}
```

**前端展示逻辑**：
- 标题显示：**次日市场展望**
- 目标日期：显示 `target_date`
- 状态徽章：Risk On（绿）/ Risk Off（红）
- 策略建议：根据 `market_regime` 自动生成
- 时间戳：显示 `calculation_date` + `last_updated`

### 2. web_top10.csv

**用途**：付费解锁的 Top 10 信号表格

```
Rank,Symbol,Alpha Score,1D Return,20D Momentum,Size,Liquidity
1,600751,7.75,10.10%,4.3%,Small,Low
2,603663,6.98,7.17%,23.7%,Large,Medium
3,603308,6.67,10.00%,25.1%,Large,High
4,600185,6.58,9.96%,25.3%,Mid,Medium
5,688503,6.4,20.00%,24.1%,Mid,High
6,601869,5.82,10.00%,74.0%,Large,High
7,688313,5.8,10.83%,5.0%,Large,High
8,688262,5.53,12.85%,28.6%,Mid,Medium
9,688337,5.51,6.44%,0.4%,Small,Low
10,688190,5.18,8.25%,4.2%,Small,Low
```

### 3. regime_history.csv

**用途**：历史记录页面 + 统计

```
date,shibor_2w,涨跌,rsi_5,risk_on
2025-11-17,1.55,4.1,72.55,0
2025-11-18,1.55,0.0,72.55,0
...
2026-02-09,1.584,8.0,54.54,0
```

**核心逻辑**：
- `date`：数据计算日期（T）
- `risk_on`：0 = Risk Off，1 = Risk On
- T 日计算的 `risk_on` → 指导 T+1 日的交易
- 因此 02-09 的 `risk_on=0` 对应显示为 02-10 的市场展望
- 前端会自动计算 `target_date = date + 1天`

## Streamlit 配置

在 `app_update2.py` 中修改 GitHub Raw 地址：

```python
# 第 37 行
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/<username>/<repo>/main/"
```

## T+1 数据映射说明

| date（CSV） | risk_on | 前端显示 |
|-------------|---------|----------|
| 2026-02-09 | 0 | 2026-02-10 Risk Off |
| 2026-02-10 | 1 | 2026-02-11 Risk On |

前端会自动计算 `target_date = 计算日期 + 1天`

## 合规提示

- 本平台仅供研究参考，不构成投资建议
- 数据来源需合法合规
- 禁止承诺收益或预测准确率
- "Risk On" 不等于"买入建议"，仅表示市场风险偏好状态
