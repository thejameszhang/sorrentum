import logging

import pandas as pd

import core.finance.execution as cfinexec
import core.finance.market_data_example as cfmadaex
import helpers.hpandas as hpandas
import helpers.hunit_test as hunitest

_LOG = logging.getLogger(__name__)


def get_data() -> pd.DataFrame:
    start_timestamp = pd.Timestamp("2022-01-10 09:30", tz="America/New_York")
    end_timestamp = pd.Timestamp("2022-01-10 10:00", tz="America/New_York")
    asset_id = 101
    data = cfmadaex.generate_random_top_of_book_bars_for_asset(
        start_timestamp,
        end_timestamp,
        asset_id,
    )
    data = data.set_index("end_datetime")
    return data


def get_limit_order_prices(
    data: pd.DataFrame,
    *,
    buy_reference_price_col: str = "midpoint",
    sell_reference_price_col: str = "midpoint",
    sell_spread_frac_offset: float = -0.1,
) -> pd.DataFrame:
    bid_col = "bid"
    ask_col = "ask"
    buy_spread_frac_offset = 0.1
    subsample_freq = "10T"
    ffill_limit = 3
    _LOG.debug("data=\n%s", hpandas.df_to_str(data, num_rows=None))
    limit_order_prices = cfinexec.generate_limit_order_price(
        data,
        bid_col,
        ask_col,
        buy_reference_price_col,
        sell_reference_price_col,
        buy_spread_frac_offset,
        sell_spread_frac_offset,
        subsample_freq,
        ffill_limit,
    )
    return limit_order_prices


class Test_generate_limit_order_price1(hunitest.TestCase):
    def test1(self) -> None:
        data = get_data()
        limit_order_prices = get_limit_order_prices(
            data,
        )
        precision = 2
        actual = hpandas.df_to_str(
            limit_order_prices.round(precision),
            num_rows=None,
            precision=precision,
        )
        expected = r"""
                           buy_limit_order_price  sell_limit_order_price
end_datetime
2022-01-10 09:31:00-05:00                    NaN                     NaN
2022-01-10 09:32:00-05:00                    NaN                     NaN
2022-01-10 09:33:00-05:00                    NaN                     NaN
2022-01-10 09:34:00-05:00                    NaN                     NaN
2022-01-10 09:35:00-05:00                    NaN                     NaN
2022-01-10 09:36:00-05:00                    NaN                     NaN
2022-01-10 09:37:00-05:00                    NaN                     NaN
2022-01-10 09:38:00-05:00                    NaN                     NaN
2022-01-10 09:39:00-05:00                    NaN                     NaN
2022-01-10 09:40:00-05:00                 999.28                  999.27
2022-01-10 09:41:00-05:00                 999.28                  999.27
2022-01-10 09:42:00-05:00                 999.28                  999.27
2022-01-10 09:43:00-05:00                 999.28                  999.27
2022-01-10 09:44:00-05:00                    NaN                     NaN
2022-01-10 09:45:00-05:00                    NaN                     NaN
2022-01-10 09:46:00-05:00                    NaN                     NaN
2022-01-10 09:47:00-05:00                    NaN                     NaN
2022-01-10 09:48:00-05:00                    NaN                     NaN
2022-01-10 09:49:00-05:00                    NaN                     NaN
2022-01-10 09:50:00-05:00                 993.94                  993.93
2022-01-10 09:51:00-05:00                 993.94                  993.93
2022-01-10 09:52:00-05:00                 993.94                  993.93
2022-01-10 09:53:00-05:00                 993.94                  993.93
2022-01-10 09:54:00-05:00                    NaN                     NaN
2022-01-10 09:55:00-05:00                    NaN                     NaN
2022-01-10 09:56:00-05:00                    NaN                     NaN
2022-01-10 09:57:00-05:00                    NaN                     NaN
2022-01-10 09:58:00-05:00                    NaN                     NaN
2022-01-10 09:59:00-05:00                    NaN                     NaN
2022-01-10 10:00:00-05:00                    NaN                     NaN"""
        self.assert_equal(actual, expected, fuzzy_match=True)


class Test_estimate_limit_order_execution1(hunitest.TestCase):
    def test_execution(self) -> None:
        data = get_data()
        #
        buy_reference_price_col: str = "bid"
        sell_reference_price_col: str = "ask"
        sell_spread_frac_offset: float = -3.0
        limit_order_prices = get_limit_order_prices(
            data,
            buy_reference_price_col=buy_reference_price_col,
            sell_reference_price_col=sell_reference_price_col,
            sell_spread_frac_offset=sell_spread_frac_offset,
        )
        _LOG.debug("limit_order_prices=\n%s", limit_order_prices)
        #
        bid_col = "bid"
        ask_col = "ask"
        buy_limit_price_col = "buy_limit_order_price"
        sell_limit_price_col = "sell_limit_order_price"
        execution = cfinexec.estimate_limit_order_execution(
            pd.concat([data, limit_order_prices], axis=1),
            bid_col,
            ask_col,
            buy_limit_price_col,
            sell_limit_price_col,
        )
        actual = hpandas.df_to_str(
            execution,
            num_rows=None,
        )
        expected = r"""
                           limit_buy_executed  limit_sell_executed
end_datetime
2022-01-10 09:31:00-05:00               False                False
2022-01-10 09:32:00-05:00               False                False
2022-01-10 09:33:00-05:00               False                False
2022-01-10 09:34:00-05:00               False                False
2022-01-10 09:35:00-05:00               False                False
2022-01-10 09:36:00-05:00               False                False
2022-01-10 09:37:00-05:00               False                False
2022-01-10 09:38:00-05:00               False                False
2022-01-10 09:39:00-05:00               False                False
2022-01-10 09:40:00-05:00               False                False
2022-01-10 09:41:00-05:00                True                False
2022-01-10 09:42:00-05:00                True                False
2022-01-10 09:43:00-05:00                True                False
2022-01-10 09:44:00-05:00                True                False
2022-01-10 09:45:00-05:00               False                False
2022-01-10 09:46:00-05:00               False                False
2022-01-10 09:47:00-05:00               False                False
2022-01-10 09:48:00-05:00               False                False
2022-01-10 09:49:00-05:00               False                False
2022-01-10 09:50:00-05:00               False                False
2022-01-10 09:51:00-05:00                True                False
2022-01-10 09:52:00-05:00                True                False
2022-01-10 09:53:00-05:00                True                False
2022-01-10 09:54:00-05:00                True                False
2022-01-10 09:55:00-05:00               False                False
2022-01-10 09:56:00-05:00               False                False
2022-01-10 09:57:00-05:00               False                False
2022-01-10 09:58:00-05:00               False                False
2022-01-10 09:59:00-05:00               False                False
2022-01-10 10:00:00-05:00               False                False"""
        self.assert_equal(actual, expected, fuzzy_match=True)


class Test_generate_limit_orders_and_estimate_execution1(hunitest.TestCase):
    def test1(self):
        data = get_data()
        bid_col = "bid"
        ask_col = "ask"
        buy_reference_price_col = "bid"
        sell_reference_price_col = "ask"
        buy_spread_frac_offset = 0.5
        sell_spread_frac_offset = -0.5
        subsample_freq = "5T"
        ffill_limit = 1
        execution = cfinexec.generate_limit_orders_and_estimate_execution(
            data,
            bid_col,
            ask_col,
            buy_reference_price_col,
            sell_reference_price_col,
            buy_spread_frac_offset,
            sell_spread_frac_offset,
            subsample_freq,
            ffill_limit,
        )
        actual = hpandas.df_to_str(
            execution,
            num_rows=None,
        )
        expected = r"""
                           buy_limit_order_price  sell_limit_order_price  limit_buy_executed  limit_sell_executed  buy_trade_price  sell_trade_price
end_datetime
2022-01-10 09:31:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:32:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:33:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:34:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:35:00-05:00                 997.44                  997.44               False                False              NaN               NaN
2022-01-10 09:36:00-05:00                 997.44                  997.44               False                 True              NaN            997.44
2022-01-10 09:37:00-05:00                    NaN                     NaN               False                 True              NaN               NaN
2022-01-10 09:38:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:39:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:40:00-05:00                 999.28                  999.28               False                False              NaN               NaN
2022-01-10 09:41:00-05:00                 999.28                  999.28                True                False           999.28               NaN
2022-01-10 09:42:00-05:00                    NaN                     NaN                True                False              NaN               NaN
2022-01-10 09:43:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:44:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:45:00-05:00                 996.36                  996.36               False                False              NaN               NaN
2022-01-10 09:46:00-05:00                 996.36                  996.36                True                False           996.36               NaN
2022-01-10 09:47:00-05:00                    NaN                     NaN                True                False              NaN               NaN
2022-01-10 09:48:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:49:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:50:00-05:00                 993.94                  993.94               False                False              NaN               NaN
2022-01-10 09:51:00-05:00                 993.94                  993.94                True                False           993.94               NaN
2022-01-10 09:52:00-05:00                    NaN                     NaN                True                False              NaN               NaN
2022-01-10 09:53:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:54:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:55:00-05:00                 991.64                  991.64               False                False              NaN               NaN
2022-01-10 09:56:00-05:00                 991.64                  991.64                True                False           991.64               NaN
2022-01-10 09:57:00-05:00                    NaN                     NaN                True                False              NaN               NaN
2022-01-10 09:58:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 09:59:00-05:00                    NaN                     NaN               False                False              NaN               NaN
2022-01-10 10:00:00-05:00                    NaN                     NaN               False                False              NaN               NaN"""
        self.assert_equal(actual, expected, fuzzy_match=True)
