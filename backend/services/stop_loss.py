# -*- coding: utf-8 -*-
class StopLossEngine:

    @staticmethod
    def calculate(buy_price, highest_price, method, value):
        if method == "fixed":
            return round(value, 4)
        elif method == "percentage":
            return round(buy_price * (1 - value / 100), 4)
        elif method == "trailing":
            return round(highest_price * (1 - value / 100), 4)
        else:
            raise ValueError(f"Unknown stop loss method: {method}")

    @staticmethod
    def is_triggered(current_price, stop_loss_price):
        return current_price <= stop_loss_price

    @staticmethod
    def validate(buy_price, method, value):
        if value <= 0:
            return False, "止损参数必须大于 0"
        if method == "fixed" and value >= buy_price:
            return False, "固定止损价必须低于买入价"
        if method in ("percentage", "trailing") and (value <= 0 or value >= 100):
            return False, "止损百分比必须在 1-99 之间"
        return True, None
