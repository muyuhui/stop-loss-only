# -*- coding: utf-8 -*-
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)


def is_trading_day(check_date: date = None) -> bool:
    try:
        import akshare as ak
        if check_date is None:
            check_date = date.today()
        day_str = check_date.strftime("%Y%m%d")
        calendar = ak.tool_trade_date_hist_sina()
        trading_days = set(calendar["trade_date"].tolist())
        return day_str in trading_days
    except Exception:
        logger.warning("交易日历获取失败，按周一到周五假定")
        if check_date is None:
            check_date = date.today()
        wd = check_date.weekday()
        return wd < 5


def fetch_stock_price(code: str) -> dict:
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        if row.empty:
            return {"code": code, "current_price": 0, "change_pct": 0, "error": f"未找到股票 {code}"}
        r = row.iloc[0]
        return {
            "code": code,
            "current_price": float(r["最新价"]),
            "change_pct": float(r["涨跌幅"]),
            "error": None,
        }
    except Exception as e:
        logger.error(f"获取股票 {code} 价格失败: {e}")
        return {"code": code, "current_price": 0, "change_pct": 0, "error": str(e)}


def fetch_fund_price(code: str) -> dict:
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        row = df[df["代码"] == code]
        if not row.empty:
            r = row.iloc[0]
            return {
                "code": code,
                "current_price": float(r["最新价"]),
                "change_pct": float(r["涨跌幅"]),
                "error": None,
            }
        df_lof = ak.fund_lof_spot_em()
        row_lof = df_lof[df_lof["代码"] == code]
        if not row_lof.empty:
            r = row_lof.iloc[0]
            return {
                "code": code,
                "current_price": float(r["最新价"]),
                "change_pct": float(r.get("涨跌幅", 0)),
                "error": None,
            }
        try:
            nav_df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            if not nav_df.empty:
                latest = nav_df.iloc[-1]
                return {
                    "code": code,
                    "current_price": float(latest["单位净值"]),
                    "change_pct": 0,
                    "error": None,
                }
        except Exception:
            pass
        return {"code": code, "current_price": 0, "change_pct": 0, "error": f"未找到基金 {code}"}
    except Exception as e:
        logger.error(f"获取基金 {code} 价格失败: {e}")
        return {"code": code, "current_price": 0, "change_pct": 0, "error": str(e)}


def fetch_price(code: str, asset_type: str) -> dict:
    if asset_type == "stock":
        return fetch_stock_price(code)
    elif asset_type == "fund":
        return fetch_fund_price(code)
    else:
        return {"code": code, "current_price": 0, "change_pct": 0, "error": f"未知类型 {asset_type}"}


def fetch_all_prices(holdings: list) -> list[dict]:
    results = []
    for h in holdings:
        result = fetch_price(h.code, h.type)
        result["name"] = h.name
        result["fetched_at"] = datetime.now().isoformat()
        results.append(result)
    return results
