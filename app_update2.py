"""
================================================================================
EigenFlow | 量化研究订阅平台 v3.5
Quantitative Research Platform - Institutional Grade

【核心设计理念】
├── T+1 数据映射（计算日 → 生效交易日）
├── 顶级UI/UX（专业感+信任度）
├── 极简数据路径（本地文件直接读取）
└── 合规克制表达

================================================================================
"""

import streamlit as st
import pandas as pd
import json
import hashlib
import uuid
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import streamlit.components.v1 as components

# ==================== 配置 | Configuration ====================

st.set_page_config(
    page_title="EigenFlow | 量化研究",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 项目目录（本地文件）
APP_DIR = os.path.dirname(__file__)

# 本地数据文件路径
SNAPSHOT_FILE = os.path.join(APP_DIR, 'regime_snapshot.json')
WEB_TOP10_FILE = os.path.join(APP_DIR, 'web_top10.csv')
HISTORY_FILE = os.path.join(APP_DIR, 'regime_history.csv')

# 订阅配置
KEY_VALIDITY_DAYS = 30
SHARE_CONFIG = {
    'max_devices_per_key': 2,
    'time_window_hours': 24,
    'device_threshold': 2,
}

# ==================== 数据加载模块 | 本地文件 ====================

@st.cache_data(ttl=300, show_spinner=False)
def load_regime_snapshot() -> Optional[Dict]:
    """
    加载实时快照（本地文件）
    regime_snapshot.json 结构：
    {
        "target_date": "2026-02-10",       // 目标交易日（T+1）
        "calculation_date": "2026-02-09",   // 计算日期（T）
        "market_regime": "Risk Off",        // 市场状态
        "action": "Defensive",              // 行动建议
        "shibor_2w": 1.584,
        "rsi_5": 54.54,
        "last_updated": "2026-02-09 21:16"
    }
    """
    try:
        if os.path.exists(SNAPSHOT_FILE):
            # 使用 UTF-8-sig 编码来移除 BOM 头
            with open(SNAPSHOT_FILE, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                data = json.loads(content)
                return data
        return None
    except json.JSONDecodeError as e:
        return None
    except Exception as e:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def load_regime_history() -> pd.DataFrame:
    """
    加载历史Regime数据（本地文件）
    用途：生成历史时间轴和统计

    注意：T日计算的risk_on → 指导T+1日交易
    """
    try:
        if os.path.exists(HISTORY_FILE):
            df = pd.read_csv(HISTORY_FILE)
            df.columns = df.columns.str.strip()

            # 核心处理：计算"目标交易日"（T+1）
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df['target_date'] = df['date'] + timedelta(days=1)
                df['target_date_str'] = df['target_date'].dt.strftime('%Y-%m-%d')

            return df
        else:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def load_web_top10() -> pd.DataFrame:
    """
    加载Top10信号数据（本地文件）
    web_top10.csv 字段:
    Rank, Symbol, Alpha Score, 1D Return, 20D Momentum, Size, Liquidity
    """
    try:
        if os.path.exists(WEB_TOP10_FILE):
            df = pd.read_csv(WEB_TOP10_FILE)
            df.columns = df.columns.str.strip()
            return df
        else:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ==================== 调试模式 | Debug Mode ====================
def render_debug_info():
    """渲染调试信息（开发用，上线可关闭）"""
    with st.expander("🔧 调试信息", expanded=False):
        st.write(f"**APP_DIR**: `{APP_DIR}`")
        st.write(f"**SNAPSHOT_FILE**: `{SNAPSHOT_FILE}` (存在: {os.path.exists(SNAPSHOT_FILE)})")
        
        # 显示 JSON 内容
        if os.path.exists(SNAPSHOT_FILE):
            try:
                with open(SNAPSHOT_FILE, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                    st.write("**JSON 内容**:")
                    st.code(content, language='json')
                    
                data = json.loads(content)
                st.write("**解析成功**:", data)
            except Exception as e:
                st.error(f"**解析失败**: {e}")
        
        st.write(f"**WEB_TOP10_FILE**: `{WEB_TOP10_FILE}` (存在: {os.path.exists(WEB_TOP10_FILE)})")
        st.write(f"**HISTORY_FILE**: `{HISTORY_FILE}` (存在: {os.path.exists(HISTORY_FILE)})")


# ==================== Key 验证模块 | Access Control ====================

def validate_access_key(key: str) -> dict:
    """验证Access Key"""
    key = key.strip().upper()

    # 从环境变量或 secrets 加载有效Key
    valid_keys = []
    try:
        if hasattr(st.secrets, 'access_keys'):
            valid_keys = st.secrets.access_keys.get('keys', [])
    except:
        pass

    if not valid_keys:
        valid_keys = [
            "EF-26Q1-A9F4KZ2M",
            "EF-26Q1-B3H8LP5N",
            "EF-26Q1-C7J2MR9R",
        ]

    if key not in valid_keys:
        return {'valid': False}

    # 检查有效期
    now = datetime.now()
    key_state = st.session_state.get('key_states', {})
    key_info = key_state.get(key, {})

    first_seen = key_info.get('first_seen')
    if not first_seen:
        first_seen = now.strftime('%Y-%m-%d')
        key_state[key] = {'first_seen': first_seen}
        st.session_state.key_states = key_state

    try:
        first_date = datetime.strptime(first_seen, '%Y-%m-%d')
        days_used = (now - first_date).days
    except:
        days_used = 0

    if days_used >= KEY_VALIDITY_DAYS:
        return {'valid': False, 'expired': True, 'first_seen': first_seen}

    return {
        'valid': True,
        'key_mask': mask_key(key),
        'first_seen': first_seen,
        'days_remaining': KEY_VALIDITY_DAYS - days_used,
    }


def mask_key(key: str) -> str:
    """掩码Key显示"""
    if len(key) >= 12:
        return f"{key[:8]}{'****'}{key[-4:]}"
    return key[:6] + '****'


# ==================== 工具函数 | Utilities ====================

def format_stock_code(code):
    """格式化股票代码"""
    return str(code).strip().zfill(6)


def get_tradingview_symbol(stock_code):
    """获取TradingView股票代码"""
    code = format_stock_code(stock_code)
    if code.startswith(('600', '601', '603', '605', '688')):
        return f"SSE:{code}"
    elif code.startswith(('000', '001', '002', '003', '300', '301')):
        return f"SZSE:{code}"
    return f"SSE:{code}"


def format_percent_from_raw(raw_value) -> str:
    """从原始值（含%或不含）格式化百分比"""
    if pd.isna(raw_value):
        return "—"
    val_str = str(raw_value).strip()
    if '%' in val_str:
        val_str = val_str.replace('%', '')
    try:
        val = float(val_str)
        sign = "+" if val > 0 else ""
        return f"{sign}{val:.2f}%"
    except:
        return "—"


def format_score(value) -> str:
    """格式化评分"""
    if pd.isna(value):
        return "—"
    return f"{value:.2f}"


# ==================== CSS 样式 | Institutional Dark Theme ====================

st.markdown("""
<style>
/* ========== 基础设置 ========== */
.info-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 20px;
    margin: 16px 0;
}

.info-card-title {
    font-size: 0.95em;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 10px;
}

.info-card-text {
    font-size: 0.85em;
    color: var(--text-secondary);
    line-height: 1.7;
}

.block-container {
    max-width: 720px !important;
    padding-top: 0.5rem !important;
    padding-bottom: 5rem !important;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* ========== 机构深蓝主题 ========== */
:root {
    --bg-primary: #0B1220;
    --bg-card: #111A2E;
    --bg-card-hover: #1A2744;
    --text-primary: #E5E7EB;
    --text-secondary: #9CA3AF;
    --text-muted: #6B7280;
    --accent-purple: #6366F1;
    --accent-purple-hover: #4F46E5;
    --accent-purple-gradient: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
    --gold-accent: #C9A227;
    --risk-on: #059669;
    --risk-off: #DC2626;
    --border-subtle: #1E293B;
    --overlay-dark: rgba(11, 18, 32, 0.92);
}

body {
    background: var(--bg-primary);
    color: var(--text-primary);
}

/* ========== 品牌头部 ========== */
.brand-header {
    text-align: center;
    padding: 20px 0 16px;
    margin-bottom: 12px;
}

.brand-logo {
    font-size: 1.9em;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.5px;
}

.brand-tagline {
    font-size: 0.82em;
    color: var(--text-muted);
    margin-top: 4px;
    letter-spacing: 2px;
}

/* ========== Regime 核心卡片（顶部） ========== */
.regime-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 28px;
    margin: 16px 0 24px;
    text-align: center;
}

/* 标题区 */
.regime-title {
    font-size: 0.85em;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 12px;
}

.regime-target-date {
    font-size: 1.8em;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 16px;
}

/* 状态徽章 */
.regime-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 14px 28px;
    border-radius: 12px;
    font-size: 1.15em;
    font-weight: 600;
    margin-bottom: 16px;
}

.regime-badge.risk-on {
    background: rgba(5, 150, 105, 0.15);
    color: #34D399;
    border: 1px solid rgba(5, 150, 105, 0.3);
}

.regime-badge.risk-off {
    background: rgba(220, 38, 38, 0.15);
    color: #F87171;
    border: 1px solid rgba(220, 38, 38, 0.3);
}

/* 行动建议 */
.regime-action {
    font-size: 0.95em;
    color: var(--text-secondary);
    margin-bottom: 20px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border-subtle);
}

/* 指标区 */
.regime-metrics {
    display: flex;
    justify-content: center;
    gap: 32px;
    padding-top: 16px;
}

.regime-metric {
    text-align: center;
}

.regime-metric-label {
    font-size: 0.68em;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}

.regime-metric-value {
    font-size: 1.1em;
    color: var(--text-primary);
    font-weight: 500;
}

/* 时间戳 */
.regime-timestamp {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px dashed var(--border-subtle);
    font-size: 0.72em;
    color: var(--text-muted);
    line-height: 1.8;
}

.regime-timestamp strong {
    color: var(--text-secondary);
}

/* ========== 信号表格 ========== */
.signal-table {
    width: 100%;
    background: var(--bg-card);
    border-radius: 12px;
    overflow: hidden;
    margin: 16px 0;
}

.signal-table th {
    background: var(--bg-card-hover);
    color: var(--text-muted);
    font-size: 0.72em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 14px 12px;
    text-align: center;
    border-bottom: 1px solid var(--border-subtle);
}

.signal-table td {
    padding: 14px 12px;
    text-align: center;
    border-bottom: 1px solid var(--border-subtle);
    font-size: 0.88em;
}

.signal-table tr:last-child td {
    border-bottom: none;
}

.signal-table tr:hover {
    background: var(--bg-card-hover);
}

.col-rank { font-weight: 600; color: var(--text-primary); }
.col-symbol { font-weight: 600; color: var(--text-primary); font-family: 'SF Mono', Monaco, monospace; }
.col-score { font-weight: 600; color: var(--gold-accent); }
.col-return { font-weight: 500; }
.col-return.pos { color: #34D399; }
.col-return.neg { color: #F87171; }
.col-size, .col-liquidity { color: var(--text-secondary); font-size: 0.8em; }

/* ========== 锁定卡片 ========== */
.locked-overlay {
    position: relative;
    overflow: hidden;
}

.locked-overlay::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
        to bottom,
        transparent 0%,
        var(--overlay-dark) 30%,
        var(--overlay-dark) 100%
    );
    pointer-events: none;
}

.locked-content {
    position: relative;
    z-index: 1;
}

.locked-cta {
    position: absolute;
    bottom: 40px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 2;
    text-align: center;
}

.lock-icon {
    font-size: 2em;
    margin-bottom: 8px;
}

.lock-title {
    font-size: 0.95em;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
}

.lock-desc {
    font-size: 0.78em;
    color: var(--text-secondary);
    margin-bottom: 16px;
}

/* ========== 按钮样式 ========== */
.stButton > button {
    background: var(--accent-purple-gradient) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 12px 24px !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4) !important;
}

.btn-secondary > button {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-secondary) !important;
}

.btn-secondary > button:hover {
    background: var(--bg-card-hover) !important;
    color: var(--text-primary) !important;
}

/* ========== 横向导航栏 ========== */
.nav-wrapper {
    display: flex;
    justify-content: center;
    margin: 20px 0 28px;
}

.nav-container {
    display: inline-flex;
    gap: 4px;
    padding: 4px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
}

.nav-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 12px 24px;
    border-radius: 10px;
    font-size: 0.9em;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
    border: none;
    background: transparent;
}

.nav-btn:hover {
    color: var(--text-primary);
    background: var(--bg-card-hover);
}

.nav-btn.active {
    background: var(--accent-purple-gradient);
    color: white;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.nav-icon {
    font-size: 1.1em;
}

/* ========== 免责声明 ========== */
.disclaimer-bar {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 14px 16px;
    margin: 20px 0 12px;
    font-size: 0.72em;
    color: var(--text-muted);
    text-align: center;
    line-height: 1.7;
}

/* ========== 页脚水印 ========== */
.watermark {
    position: fixed;
    bottom: 6px;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 0.6em;
    color: var(--text-muted);
    padding: 8px;
    background: linear-gradient(to top, rgba(11, 18, 32, 0.95), transparent);
    z-index: 100;
}

/* ========== 锁定提示卡片 ========== */
.locked-prompt-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 28px;
    margin: 20px 0;
    text-align: center;
}

/* ========== 输入框 ========== */
.stTextInput > div > div > input {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
}

.stTextInput > div > div > input::placeholder {
    color: var(--text-muted) !important;
}

/* ========== 选择框 ========== */
.stSelectbox > div > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-primary) !important;
}

/* ========== 时间轴 ========== */
.timeline-container {
    display: flex;
    gap: 2px;
    margin: 20px 0;
    overflow-x: auto;
    padding-bottom: 8px;
}

.timeline-bar {
    flex: 1;
    min-width: 20px;
    height: 32px;
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.timeline-bar:hover {
    transform: scaleY(1.1);
}

.timeline-bar.risk-on {
    background: var(--risk-on);
}

.timeline-bar.risk-off {
    background: var(--risk-off);
}

/* ========== 价格样式 ========== */
.price-tag {
    display: inline-block;
    background: var(--accent-purple-gradient);
    color: white;
    font-size: 0.65em;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    margin-left: 8px;
}

.price-value {
    font-size: 1.3em;
    font-weight: 700;
    color: var(--text-primary);
}

.price-value.highlight {
    color: var(--gold-accent);
}

/* ========== TradingView ========== */
.tv-container {
    width: 100%;
    min-height: 420px;
    margin-bottom: 12px;
}

.tv-disclaimer {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 14px;
    font-size: 0.68em;
    color: var(--text-muted);
    line-height: 1.7;
    margin-top: 12px;
}

/* ========== 二维码区域 ========== */
.qr-area {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    margin: 12px 0;
}

.qr-label {
    font-size: 0.78em;
    color: var(--text-secondary);
    margin-top: 10px;
}

/* ========== 响应式 ========== */
@media (max-width: 600px) {
    .nav-btn {
        padding: 10px 16px;
        font-size: 0.85em;
    }

    .regime-metrics {
        gap: 20px;
    }

    .signal-table th,
    .signal-table td {
        padding: 10px 8px;
        font-size: 0.82em;
    }
}

/* 隐藏 radio 组件 */
.stRadio {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)


# ==================== 页面组件 | Page Components ====================

def render_brand_header():
    """渲染品牌头部"""
    st.markdown("""
    <div class="brand-header">
        <div class="brand-logo">📊 EigenFlow</div>
        <div class="brand-tagline">Quantitative Research Platform</div>
    </div>
    """, unsafe_allow_html=True)


def render_nav_tabs(current_tab: int = 0):
    """渲染横向导航栏"""
    tabs = [
        (0, "📊", "信号清单"),
        (1, "📈", "行情视图"),
        (2, "📜", "历史记录"),
        (3, "☕", "支持订阅"),
    ]

    # 获取URL参数
    url_tab = st.query_params.get("tab", None)
    if url_tab is not None:
        current_tab = int(url_tab)

    # 渲染导航
    st.markdown('<div class="nav-wrapper"><div class="nav-container">', unsafe_allow_html=True)

    for idx, icon, name in tabs:
        active = 'active' if current_tab == idx else ''
        st.markdown(
            f'''<a href="?tab={idx}" class="nav-btn {active}">
                <span class="nav-icon">{icon}</span>{name}
            </a>''',
            unsafe_allow_html=True
        )

    st.markdown('</div></div>', unsafe_allow_html=True)


def render_regime_card(snapshot: Dict = None):
    """
    【核心组件】渲染次日市场展望卡片
    T日计算 → T+1日生效

    展示内容：
    1. 标题："次日市场展望"
    2. 目标日期：YYYY-MM-DD
    3. 状态徽章：Risk On / Risk Off
    4. 行动建议：做多 / 防御
    5. 核心指标：Shibor、RSI
    6. 时间戳：计算时间 + 生效时间
    """
    # 解析数据
    target_date = "—"
    regime = "Unknown"
    action = "—"
    shibor = None
    rsi = None
    calc_date = "—"
    last_updated = "—"

    if snapshot:
        target_date = snapshot.get('target_date', '—')
        regime = snapshot.get('market_regime', 'Unknown')
        action = snapshot.get('action', '—')
        shibor = snapshot.get('shibor_2w')
        rsi = snapshot.get('rsi_5')
        calc_date = snapshot.get('calculation_date', '—')
        last_updated = snapshot.get('last_updated', '—')

    is_risk_on = regime.lower() == 'risk on' or regime.lower() == 'risk_on'
    badge_class = 'risk-on' if is_risk_on else 'risk-off'
    badge_text = '🟢 Risk On' if is_risk_on else '🔴 Risk Off'
    action_text = '积极做多' if is_risk_on else '防御观望'

    # 格式化日期显示
    try:
        if target_date != '—':
            dt = datetime.strptime(target_date, '%Y-%m-%d')
            target_display = dt.strftime('%Y/%m/%d')
        else:
            target_display = '—'
    except:
        target_display = target_date

    st.markdown(f'''
    <div class="regime-card">
        <!-- 标题 -->
        <div class="regime-title">📅 次日市场展望</div>

        <!-- 目标日期 -->
        <div class="regime-target-date">{target_display}</div>

        <!-- 状态徽章 -->
        <div class="regime-badge {badge_class}">{badge_text}</div>

        <!-- 行动建议 -->
        <div class="regime-action">策略建议：{action_text}</div>

        <!-- 核心指标 -->
        <div class="regime-metrics">
    ''', unsafe_allow_html=True)

    if shibor is not None:
        st.markdown(f'''
            <div class="regime-metric">
                <div class="regime-metric-label">Shibor 2W</div>
                <div class="regime-metric-value">{shibor:.3f}%</div>
            </div>
        ''', unsafe_allow_html=True)

    if rsi is not None:
        st.markdown(f'''
            <div class="regime-metric">
                <div class="regime-metric-label">RSI-5</div>
                <div class="regime-metric-value">{rsi:.1f}</div>
            </div>
        ''', unsafe_allow_html=True)

    st.markdown('''
        </div>

        <!-- 时间戳 -->
        <div class="regime-timestamp">
            <strong>数据计算：</strong>''' + calc_date + '''<br>
            <strong>更新于：</strong>''' + last_updated + '''
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_signal_table(df: pd.DataFrame, unlocked: bool = True, limit: int = 2):
    """渲染信号表格"""
    if df.empty or 'Rank' not in df.columns:
        st.markdown('''
        <div class="info-card" style="text-align: center; padding: 40px;">
            <div style="font-size: 1.2em; color: var(--text-muted);">
                暂无信号数据
            </div>
        </div>
        ''', unsafe_allow_html=True)
        return

    # 准备显示数据
    if not unlocked:
        df_display = df.head(limit).copy()
    else:
        df_display = df.copy()

    # 构建表格HTML
    table_html = '''
    <table class="signal-table">
        <thead>
            <tr>
                <th style="width: 10%;">Rank</th>
                <th style="width: 16%;">Symbol</th>
                <th style="width: 16%;">Alpha<br>Score</th>
                <th style="width: 14%;">1D %</th>
                <th style="width: 14%;">20D %</th>
                <th style="width: 15%;">Size</th>
                <th style="width: 15%;">Liquidity</th>
            </tr>
        </thead>
        <tbody>
    '''

    for idx, row in df_display.iterrows():
        rank = int(row.get('Rank', idx + 1))
        symbol = format_stock_code(str(row.get('Symbol', '')))
        alpha = format_score(row.get('Alpha Score', row.get('Score', 0)))

        # 解析1D Return
        ret_1d_raw = row.get('1D Return', row.get('Return_1D', 0))
        ret_1d = format_percent_from_raw(ret_1d_raw)
        ret_1d_class = 'pos' if '+' in ret_1d or float(str(ret_1d_raw).replace('%', '').replace('+', '')) > 0 else 'neg'

        # 解析20D Momentum
        ret_20d_raw = row.get('20D Momentum', row.get('Return_20D', 0))
        ret_20d = format_percent_from_raw(ret_20d_raw)
        ret_20d_class = 'pos' if '+' in ret_20d or float(str(ret_20d_raw).replace('%', '').replace('+', '')) > 0 else 'neg'

        size = row.get('Size', '—')
        liquidity = row.get('Liquidity', '—')

        table_html += f'''
        <tr>
            <td class="col-rank">#{rank}</td>
            <td class="col-symbol">{symbol}</td>
            <td class="col-score">{alpha}</td>
            <td class="col-return {ret_1d_class}">{ret_1d}</td>
            <td class="col-return {ret_20d_class}">{ret_20d}</td>
            <td class="col-size">{size}</td>
            <td class="col-liquidity">{liquidity}</td>
        </tr>
        '''

    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

    # 未解锁时的锁定覆盖层
    if not unlocked:
        st.markdown('''
        <div class="locked-overlay">
            <div class="locked-cta">
                <div class="lock-icon">🔒</div>
                <div class="lock-title">解锁完整 Top 10 信号</div>
                <div class="lock-desc">订阅后查看全部排名与详细数据</div>
        ''', unsafe_allow_html=True)

        if st.button("→ 前往订阅获取 Access Key", type="primary", use_container_width=True):
            st.query_params["tab"] = "3"
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)


def render_locked_prompt(page_name: str = "此页面"):
    """渲染锁定提示卡片"""
    st.markdown(f'''
    <div class="locked-prompt-card">
        <div style="font-size: 2.5em; margin-bottom: 12px;">🔐</div>
        <div style="font-size: 1.1em; font-weight: 600; color: var(--text-primary); margin-bottom: 8px;">
            {page_name}需解锁后查看
        </div>
        <div style="font-size: 0.88em; color: var(--text-secondary); margin-bottom: 20px;">
            输入 Access Key 验证订阅身份
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_access_input():
    """渲染Key输入框"""
    col1, col2 = st.columns([3, 1])

    with col1:
        access_key = st.text_input(
            "Access Key",
            type="password",
            placeholder="EF-26Q1-XXXXXXXX",
            label_visibility="collapsed",
            key=f"access_input_{uuid.uuid4().hex[:8]}"
        )

    with col2:
        confirm = st.button("验证", type="primary", use_container_width=True)

    return access_key, confirm


def render_disclaimer():
    """渲染精简免责声明"""
    st.markdown('''
    <div class="disclaimer-bar">
        本平台内容仅用于量化研究与市场信息参考，不构成任何投资建议或买卖依据。<br>
        金融市场存在风险，历史表现不代表未来结果，用户据此决策风险自担。
    </div>
    ''', unsafe_allow_html=True)


def render_watermark(key_mask: str = None):
    """渲染水印"""
    if key_mask:
        text = f"授权码：{key_mask} | 仅限个人研究使用"
    else:
        text = "EigenFlow Research"

    st.markdown(f'<div class="watermark">{text}</div>', unsafe_allow_html=True)


def render_compliance_footer():
    """页脚合规声明"""
    st.markdown('''
    <div class="disclaimer-bar" style="margin-top: 24px; border-top: 1px solid var(--border-subtle);">
        <strong>免责声明：</strong>本平台内容仅供研究与信息参考，不构成投资建议。用户应基于自身判断独立决策并承担相应风险。
    </div>
    ''', unsafe_allow_html=True)


# ==================== TradingView 组件 ====================

def render_tradingview_chart(symbol: str, height: int = 400):
    """渲染TradingView图表"""
    tv_html = f'''
    <div class="tv-container">
        <div id="tradingview_widget" style="height:{height}px;"></div>
    </div>
    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script type="text/javascript">
    new TradingView.widget({{
        "width": "100%",
        "height": {height},
        "symbol": "{symbol}",
        "interval": "D",
        "timezone": "Asia/Shanghai",
        "theme": "dark",
        "style": "1",
        "locale": "zh_CN",
        "toolbar_bg": "#1A2744",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_widget"
    }});
    </script>

    <div class="tv-disclaimer">
        本页面行情图表由第三方数据服务提供，仅用于市场数据展示与可视化分析参考。<br>
        图表内容不构成任何买卖建议、价格预测或投资判断。<br>
        部分图表服务可能受网络环境影响，如加载异常请更换网络环境后重试。<br>
        TradingView 为 TradingView, Inc. 的注册商标。本平台与 TradingView, Inc. 无合作、授权或隶属关系。
    </div>
    '''
    components.html(tv_html, height=height + 180)


# ==================== 历史记录页面 ====================

def render_history_page(df_history: pd.DataFrame, snapshot: Dict = None):
    """渲染历史记录页面"""
    # 标题
    st.markdown('''
    <div class="info-card">
        <div class="info-card-title">📜 市场状态历史</div>
        <div class="info-card-text">
            最近 30 个交易日市场状态记录。绿色为 Risk On 阶段，红色为 Risk Off 阶段。
            <br><br>
            <strong style="color: var(--text-muted);">注：T日计算结果指导 T+1 日交易</strong>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    if df_history.empty or 'target_date_str' not in df_history.columns:
        st.markdown('''
        <div class="info-card" style="text-align: center; padding: 40px;">
            <div style="font-size: 1.1em; color: var(--text-muted);">
                暂无历史数据
            </div>
        </div>
        ''', unsafe_allow_html=True)
        return

    # 取最近30条
    df_recent = df_history.tail(30).copy()
    df_recent = df_recent.iloc[::-1]  # 倒序

    # 时间轴（使用target_date）
    timeline_html = '<div class="timeline-container">'
    for _, row in df_recent.iterrows():
        target_date = str(row.get('target_date_str', ''))
        risk_on = int(row.get('risk_on', 0))
        is_on = risk_on == 1
        bar_class = 'risk-on' if is_on else 'risk-off'
        title = f"交易日期: {target_date} | {'Risk On' if is_on else 'Risk Off'}"
        timeline_html += f'<div class="timeline-bar {bar_class}" title="{title}"></div>'
    timeline_html += '</div>'

    st.markdown(timeline_html, unsafe_allow_html=True)

    # 数据表格
    table_html = '''
    <table class="signal-table">
        <thead>
            <tr>
                <th style="width: 25%;">交易日期</th>
                <th style="width: 15%;">RSI-5</th>
                <th style="width: 15%;">Shibor</th>
                <th style="width: 20%;">涨跌</th>
                <th style="width: 25%;">市场状态</th>
            </tr>
        </thead>
        <tbody>
    '''

    for _, row in df_recent.iterrows():
        target_date = str(row.get('target_date_str', ''))
        rsi = row.get('rsi_5')
        shibor = row.get('shibor_2w')
        change = row.get('涨跌')
        risk_on = int(row.get('risk_on', 0))
        is_on = risk_on == 1
        regime_text = '🟢 Risk On' if is_on else '🔴 Risk Off'

        rsi_str = f"{rsi:.1f}" if rsi and not pd.isna(rsi) else "—"
        shibor_str = f"{shibor:.3f}%" if shibor and not pd.isna(shibor) else "—"
        change_str = f"{change:+.1f}%" if change and not pd.isna(change) else "—"

        table_html += f'''
        <tr>
            <td style="color: var(--text-primary);">{target_date}</td>
            <td style="color: var(--text-secondary);">{rsi_str}</td>
            <td style="color: var(--text-secondary);">{shibor_str}</td>
            <td style="color: {'#34D399' if (change or 0) > 0 else '#F87171'};">{change_str}</td>
            <td style="color: {'#34D399' if is_on else '#F87171'}; font-weight: 500;">{regime_text}</td>
        </tr>
        '''

    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

    # 统计
    total_days = len(df_recent)
    on_days = int(df_recent['risk_on'].sum()) if 'risk_on' in df_recent.columns else 0
    off_days = total_days - on_days

    # 当前状态（从snapshot获取）
    current_regime = snapshot.get('market_regime', 'Unknown') if snapshot else 'Unknown'
    is_current_on = current_regime.lower() == 'risk on' or current_regime.lower() == 'risk_on'

    st.markdown(f'''
    <div class="info-card" style="margin-top: 20px;">
        <div class="info-card-title">📊 历史统计</div>
        <div style="display: flex; justify-content: space-around; margin-top: 12px;">
            <div style="text-align: center;">
                <div style="font-size: 1.5em; font-weight: 700; color: #34D399;">{on_days}</div>
                <div style="font-size: 0.72em; color: var(--text-muted);">Risk On 天数</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 1.5em; font-weight: 700; color: #F87171;">{off_days}</div>
                <div style="font-size: 0.72em; color: var(--text-muted);">Risk Off 天数</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 1.5em; font-weight: 700; color: var(--gold-accent);">{total_days}</div>
                <div style="font-size: 0.72em; color: var(--text-muted);">总交易日</div>
            </div>
        </div>
        <div style="text-align: center; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-subtle);">
            <span style="
                background: rgba({'5, 150, 105' if is_current_on else '220, 38, 38'}, 0.15);
                border: 1px solid rgba({'5, 150, 105' if is_current_on else '220, 38, 38'}, 0.3);
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 0.85em;
                color: {'#34D399' if is_current_on else '#F87171'};
            ">
                当前状态: {"Risk On" if is_current_on else "Risk Off"}
            </span>
        </div>
    </div>
    ''', unsafe_allow_html=True)


# ==================== 订阅页面 ====================

def render_subscribe_page():
    """渲染订阅页面"""
    # 第一块：解锁内容
    st.markdown('''
    <div class="info-card">
        <div class="info-card-title">🔓 订阅权益</div>
        <div class="info-card-text">
            <ul style="margin: 0; padding-left: 18px; line-height: 2;">
                <li>每日量化模型输出 Top 10 信号</li>
                <li>完整历史数据访问</li>
                <li>TradingView 行情视图</li>
                <li>市场状态（Regime）实时判断</li>
                <li>历史数据统计与分析</li>
            </ul>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # 第二块：价格
    st.markdown('''
    <div class="info-card">
        <div class="info-card-title">💰 订阅价格</div>
        <div class="info-card-text">
            <div class="price-row" style="border:none; padding: 8px 0;">
                <span style="font-size: 0.95em; color: var(--text-secondary);">月度授权</span>
                <span class="price-value">299 元</span>
            </div>
            <div class="price-row" style="border:none; padding: 8px 0;">
                <span style="font-size: 0.95em; color: var(--text-secondary);">季度授权</span>
                <span class="price-value highlight">
                    799 元 <span class="price-tag">推荐</span>
                </span>
            </div>
            <div style="font-size: 0.72em; color: var(--text-muted); margin-top: 12px;">
                * 仅限个人研究使用，不支持退款
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # 第三块：获取Key
    st.markdown('''
    <div class="info-card">
        <div class="info-card-title">📧 获取 Access Key</div>
        <div class="info-card-text">
            <ul style="margin: 0; padding-left: 18px; line-height: 2;">
                <li><strong>微信：</strong>扫描下方二维码联系</li>
                <li><strong>Email：</strong>research.eigenflow@gmail.com</li>
            </ul>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # 二维码
    col_qr1, col_qr2 = st.columns(2)

    with col_qr1:
        st.markdown('<div class="qr-area">', unsafe_allow_html=True)
        st.markdown("**💬 微信咨询**")
        try:
            st.image("wechat_qr.png", width=160)
        except:
            st.markdown("<!-- wechat_qr.png -->")
        st.markdown('<div class="qr-label">扫码咨询详情</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_qr2:
        st.markdown('<div class="qr-area">', unsafe_allow_html=True)
        st.markdown("**💳 支付宝付款**")
        try:
            st.image("alipay_qr.png", width=160)
        except:
            st.markdown("<!-- alipay_qr.png -->")
        st.markdown('<div class="qr-label">付款备注：邮箱或微信号</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # FAQ
    with st.expander("📋 常见问题", expanded=False):
        st.markdown('''
        <div style="font-size: 0.82em; color: var(--text-secondary); line-height: 1.8;">
            <p><strong>Q: 数据更新频率？</strong><br>
            A: 每个交易日晚间更新一次。</p>

            <p><strong>Q: Access Key 可以多设备使用吗？</strong><br>
            A: 单个 Key 限个人研究使用，多设备异常使用可能被风控。</p>

            <p><strong>Q: 订阅后可以退款吗？</strong><br>
            A: 虚拟内容，订阅后不支持退款。</p>

            <p><strong>Q: 这是投资建议吗？</strong><br>
            A: 不是。本平台仅提供研究参考，不构成任何投资建议。</p>
        </div>
        ''', unsafe_allow_html=True)

    # 使用声明
    st.markdown('''
    <div class="info-card" style="margin-top: 16px;">
        <div class="info-card-title">⚖️ 使用声明</div>
        <div class="info-card-text">
            <ul style="margin: 0; padding-left: 18px; line-height: 1.8;">
                <li>本内容仅供个人研究与学习使用，禁止转售、二次分发或公开传播。</li>
                <li>严禁任何形式的二次收费或商业化使用。</li>
                <li>如发现违规行为，访问授权可能被立即终止。</li>
            </ul>
        </div>
    </div>
    ''', unsafe_allow_html=True)


# ==================== 主程序 | Main ====================

def main():
    """主入口"""
    # 初始化 session_state
    if 'verified_key' not in st.session_state:
        st.session_state.verified_key = None
    if 'verified_key_mask' not in st.session_state:
        st.session_state.verified_key_mask = None
    if 'key_states' not in st.session_state:
        st.session_state.key_states = {}

    # 渲染调试信息（开发用）
    render_debug_info()

    # 渲染头部
    render_brand_header()

    # 读取当前 tab
    tab = st.query_params.get("tab", "0")
    current_tab = int(tab)

    # 渲染导航
    render_nav_tabs(current_tab)

    # 加载数据
    snapshot = load_regime_snapshot()
    df_history = load_regime_history()
    df_top10 = load_web_top10()

    # 页面内容
    if current_tab == 0:
        # ===== 信号清单页 =====

        # 渲染核心Regime卡片
        render_regime_card(snapshot)

        # 检查是否解锁
        verified = st.session_state.get('verified_key') is not None

        if verified:
            # 已解锁：显示完整表格
            render_signal_table(df_top10, unlocked=True)

            # 显示Key信息
            key_mask = st.session_state.get('verified_key_mask', '')
            st.markdown(f'''
            <div style="text-align: center; margin: 16px 0;">
                <span style="
                    background: rgba(201, 162, 39, 0.1);
                    border: 1px solid rgba(201, 162, 39, 0.3);
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-size: 0.78em;
                    color: var(--gold-accent);
                ">
                    已解锁 | {key_mask}
                </span>
            </div>
            ''', unsafe_allow_html=True)
        else:
            # 未解锁：显示预览 + 锁定
            render_signal_table(df_top10, unlocked=False, limit=2)

            # 引导输入Key
            st.markdown('<div style="margin: 20px 0;">', unsafe_allow_html=True)

            access_key, confirm = render_access_input()

            if confirm and access_key:
                result = validate_access_key(access_key)
                if result.get('valid'):
                    st.session_state.verified_key = access_key
                    st.session_state.verified_key_mask = result.get('key_mask', mask_key(access_key))
                    st.success("✅ 验证成功！")
                    st.rerun()
                else:
                    st.error("❌ 无效或已过期的 Access Key")

            st.markdown('</div>', unsafe_allow_html=True)

            # 快捷入口
            st.markdown('<div style="text-align: center; margin: 16px 0;">', unsafe_allow_html=True)
            st.markdown('<span style="color: var(--text-muted); font-size: 0.85em;">没有 Access Key？</span>', unsafe_allow_html=True)
            if st.button("→ 获取 Access Key", type="secondary", use_container_width=True):
                st.query_params["tab"] = "3"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # 水印
        key_mask = st.session_state.get('verified_key_mask')
        render_watermark(key_mask)

    elif current_tab == 1:
        # ===== 行情视图页 =====

        # 验证状态
        verified = st.session_state.get('verified_key') is not None

        # Regime徽章
        if snapshot:
            is_risk_on = snapshot.get('market_regime', '').lower() in ['risk on', 'risk_on']
            st.markdown(f'''
            <div style="position: absolute; top: 60px; right: 20px; z-index: 10;">
                <span style="
                    background: rgba(17, 26, 46, 0.9);
                    border: 1px solid var(--border-subtle);
                    padding: 6px 12px;
                    border-radius: 6px;
                    font-size: 0.72em;
                    color: var(--text-secondary);
                ">
                    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{'#34D399' if is_risk_on else '#F87171'};margin-right:6px;"></span>
                    {"Risk On" if is_risk_on else "Risk Off"}
                </span>
            </div>
            ''', unsafe_allow_html=True)

        if not verified:
            render_locked_prompt("行情视图")

            access_key, confirm = render_access_input()

            if confirm and access_key:
                result = validate_access_key(access_key)
                if result.get('valid'):
                    st.session_state.verified_key = access_key
                    st.session_state.verified_key_mask = result.get('key_mask', mask_key(access_key))
                    st.success("✅ 验证成功！")
                    st.rerun()
                else:
                    st.error("❌ 无效或已过期的 Access Key")

            st.markdown('<div style="text-align: center; margin: 16px 0;">', unsafe_allow_html=True)
            if st.button("→ 获取 Access Key", type="secondary", use_container_width=True):
                st.query_params["tab"] = "3"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            render_watermark()
        else:
            # 已解锁
            st.markdown('''
            <div style="margin-bottom: 16px;">
                <span style="
                    background: var(--bg-card);
                    border: 1px solid var(--border-subtle);
                    padding: 10px 16px;
                    border-radius: 8px;
                    font-size: 0.88em;
                    color: var(--text-secondary);
                ">
                    📈 行情视图
                </span>
            </div>
            ''', unsafe_allow_html=True)

            # 股票选择器
            if not df_top10.empty and 'Symbol' in df_top10.columns:
                stock_options = [f"{row['Symbol']}" for _, row in df_top10.iterrows()]
                selected = st.selectbox("选择股票", options=stock_options, index=0)
                if selected:
                    symbol = get_tradingview_symbol(selected)
                    render_tradingview_chart(symbol)
            else:
                ticker = st.text_input("输入股票代码", placeholder="600519, 000001, 300624", max_chars=6)
                if ticker:
                    code = ticker.strip().zfill(6)
                    if len(code) == 6 and code.isdigit():
                        symbol = get_tradingview_symbol(code)
                        render_tradingview_chart(symbol)

            key_mask = st.session_state.get('verified_key_mask')
            render_watermark(key_mask)

    elif current_tab == 2:
        # ===== 历史记录页 =====

        # Regime卡片
        render_regime_card(snapshot)

        # 历史记录
        render_history_page(df_history, snapshot)
        render_watermark(st.session_state.get('verified_key_mask'))

    else:
        # ===== 订阅页面 =====
        render_subscribe_page()

    # 合规页脚
    render_compliance_footer()


if __name__ == "__main__":
    main()
