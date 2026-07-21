from decimal import Decimal, ROUND_HALF_UP


PRICE_QUANTUM = Decimal("0.0001")


def to_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


class StopLossEngine:
    @staticmethod
    def calculate(buy_price, highest_price, method, value) -> Decimal:
        buy = to_decimal(buy_price)
        high = to_decimal(highest_price)
        parameter = to_decimal(value)
        if method == "fixed":
            result = parameter
        elif method == "percentage":
            result = buy * (Decimal("1") - parameter / Decimal("100"))
        elif method == "trailing":
            result = high * (Decimal("1") - parameter / Decimal("100"))
        else:
            raise ValueError(f"Unknown stop loss method: {method}")
        return result.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)

    @staticmethod
    def is_triggered(current_price, stop_loss_price) -> bool:
        return to_decimal(current_price) <= to_decimal(stop_loss_price)

    @staticmethod
    def validate(buy_price, method, value):
        buy = to_decimal(buy_price)
        parameter = to_decimal(value)
        if parameter <= 0:
            return False, "止损参数必须大于 0"
        if method == "fixed" and parameter >= buy:
            return False, "固定止损价必须低于买入价"
        if method in ("percentage", "trailing") and not Decimal("1") <= parameter <= Decimal("99"):
            return False, "止损百分比必须在 1-99 之间"
        if method not in ("fixed", "percentage", "trailing"):
            return False, "未知止损方式"
        return True, None
