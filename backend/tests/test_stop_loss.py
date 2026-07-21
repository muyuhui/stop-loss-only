import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.stop_loss import StopLossEngine


class TestStopLossEngine:

    def test_fixed_stop_loss(self):
        price = StopLossEngine.calculate(
            buy_price=10.0, highest_price=10.0,
            method="fixed", value=9.0
        )
        assert price == 9.0

    def test_percentage_stop_loss(self):
        price = StopLossEngine.calculate(
            buy_price=10.0, highest_price=10.0,
            method="percentage", value=10
        )
        assert price == 9.0

    def test_trailing_initial(self):
        price = StopLossEngine.calculate(
            buy_price=10.0, highest_price=10.0,
            method="trailing", value=10
        )
        assert price == 9.0

    def test_trailing_rises_with_price(self):
        price = StopLossEngine.calculate(
            buy_price=10.0, highest_price=18.0,
            method="trailing", value=10
        )
        assert price == 16.2

    def test_trigger_when_below(self):
        assert StopLossEngine.is_triggered(8.80, 9.0) is True

    def test_trigger_when_equal(self):
        assert StopLossEngine.is_triggered(9.0, 9.0) is True

    def test_no_trigger_when_above(self):
        assert StopLossEngine.is_triggered(10.5, 9.0) is False

    def test_validate_fixed_valid(self):
        ok, _ = StopLossEngine.validate(10.0, "fixed", 9.0)
        assert ok

    def test_validate_fixed_above_buy(self):
        ok, err = StopLossEngine.validate(10.0, "fixed", 11.0)
        assert not ok
        assert "低于" in err

    def test_validate_percentage_out_of_range(self):
        ok, err = StopLossEngine.validate(10.0, "percentage", 101)
        assert not ok
