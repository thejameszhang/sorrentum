import logging
import unittest.mock as umock

import ccxt
import ccxt.pro as ccxtpro
import pandas as pd
import pytest

import helpers.hdatetime as hdateti
import helpers.henv as henv
import helpers.hpandas as hpandas
import helpers.hunit_test as hunitest
import im_v2.ccxt.data.extract.extractor as imvcdexex

_LOG = logging.getLogger(__name__)


@pytest.mark.skipif(
    not henv.execute_repo_config_code("is_CK_S3_available()"),
    reason="Run only if CK S3 is available",
)
class TestCcxtExtractor1(hunitest.TestCase):
    # Mock calls to external providers.
    ccxt_patch = umock.patch.object(imvcdexex, "ccxt", spec=ccxt)

    def setUp(self) -> None:
        super().setUp()
        # Create new mocks from patch's start() method.
        self.ccxt_mock: umock.MagicMock = self.ccxt_patch.start()

    def tearDown(self) -> None:
        self.ccxt_patch.stop()
        # Deallocate in reverse order to avoid race conditions.
        super().tearDown()

    def test_initialize_class(self) -> None:
        """
        Smoke test that the class is being initialized correctly.
        """
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        self.assertEqual(exchange_class.exchange_id, "binance")
        self.assertEqual(exchange_class.contract_type, "spot")
        self.assertEqual(exchange_class.vendor, "CCXT")
        # Check if `exchange_class._sync_exchange` was created from `ccxt.binance()` call.
        # Mock memorizes calls that lead to creation of it.
        self.assertEqual(
            exchange_class._sync_exchange._extract_mock_name(), "ccxt.binance()"
        )
        actual_method_calls = str(exchange_class._sync_exchange.method_calls)
        # Check calls against `exchange_class._sync_exchange`.
        expected_method_calls = "[call.load_markets()]"
        self.assertEqual(actual_method_calls, expected_method_calls)
        # Wrong contract type.
        with pytest.raises(AssertionError) as fail:
            imvcdexex.CcxtExtractor("binance", "dummy")
        actual = str(fail.value)
        expected = (
            "Failed assertion *\n'dummy' in '['futures', 'spot']'\n"
            "Supported contract types: spot, futures"
        )
        self.assertIn(expected, actual)

    def test_log_into_exchange(self) -> None:
        """
        Verify that login is done correctly based on the contract type.
        """
        exchange_mock = self.ccxt_mock.binance
        # Verify with `spot` contract type.
        _ = imvcdexex.CcxtExtractor("binance", "spot")
        actual_args = tuple(exchange_mock.call_args)
        expected_args = (
            ({"rateLimit": True},),
            {},
        )
        self.assertEqual(actual_args, expected_args)
        # Verify with `futures` contract type.
        _ = imvcdexex.CcxtExtractor("binance", "futures")
        actual_args = tuple(exchange_mock.call_args)
        expected_args = (
            (
                {
                    "options": {"defaultType": "future"},
                    "rateLimit": True,
                },
            ),
            {},
        )
        self.assertEqual(actual_args, expected_args)
        # Check overall exchange initialization.
        self.assertEqual(exchange_mock.call_count, 2)

    @umock.patch.object(
        imvcdexex.CcxtExtractor,
        "_fetch_ohlcv",
        spec=imvcdexex.CcxtExtractor._fetch_ohlcv,
    )
    @umock.patch.object(imvcdexex.time, "sleep")
    def test_download_ohlcv1(
        self, sleep_mock: umock.MagicMock, fetch_ohlcv_mock: umock.MagicMock
    ) -> None:
        """
        Verify that wrapper around `ccxt.binance` download is properly called.
        """
        # Prepare data and initialize class before run.
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        exchange_class.currency_pairs = ["BTC/USDT"]
        start_timestamp = pd.Timestamp("2022-02-24T00:00:00Z")
        # _download_ohlcv filters out bars which are within bounds
        #  of the provided time intervals.
        mid_timestamp = hdateti.convert_timestamp_to_unix_epoch(
            pd.Timestamp("2022-02-24T12:00:00Z")
        )
        end_timestamp = pd.Timestamp("2022-02-25T00:00:00Z")
        fetch_ohlcv_mock.return_value = pd.DataFrame(
            [["dummy", mid_timestamp]], columns=["dummy", "timestamp"]
        )
        # Mock a call to ccxt's `parse_timeframe method` called inside `_fetch_ohlcv`.
        with umock.patch.object(
            exchange_class._sync_exchange, "parse_timeframe", create=True
        ) as parse_timeframe_mock:
            parse_timeframe_mock.return_value = 60
            # Run.
            ohlcv_data = exchange_class._download_ohlcv(
                exchange_id="binance",
                currency_pair="BTC/USDT",
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                bar_per_iteration=500,
            )
            #
            self.assertEqual(parse_timeframe_mock.call_count, 1)
            actual_args = tuple(parse_timeframe_mock.call_args)
            expected_args = (("1m",), {})
            self.assertEqual(actual_args, expected_args)
        #
        self.assertEqual(sleep_mock.call_count, 3)
        # Check output.
        self.assertEqual(fetch_ohlcv_mock.call_count, 3)
        actual_args = str(fetch_ohlcv_mock.call_args_list)
        expected_args = r"""
        [call('BTC/USDT', since=1645660800000, bar_per_iteration=500),
         call('BTC/USDT', since=1645690800000, bar_per_iteration=500),
         call('BTC/USDT', since=1645720800000, bar_per_iteration=500)]
        """
        self.assert_equal(actual_args, expected_args, fuzzy_match=True)
        actual_output = hpandas.df_to_str(ohlcv_data)
        expected_output = rf"""dummy timestamp
            0  dummy {mid_timestamp}
            1  dummy {mid_timestamp}
            2  dummy {mid_timestamp}
        """
        self.assert_equal(actual_output, expected_output, fuzzy_match=True)

    @umock.patch.object(
        imvcdexex.CcxtExtractor,
        "_fetch_ohlcv",
        spec=imvcdexex.CcxtExtractor._fetch_ohlcv,
    )
    def test_download_ohlcv2(self, fetch_ohlcv_mock: umock.MagicMock) -> None:
        """
        Verify that wrapper around `ccxt.binance` is getting the latest bars.
        """
        fetch_ohlcv_mock.return_value = pd.DataFrame(["dummy"], columns=["dummy"])
        # Prepare data and initialize class before run.
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        exchange_class.currency_pairs = ["BTC/USDT"]
        # Run.
        ohlcv_data = exchange_class._download_ohlcv(
            exchange_id="binance",
            currency_pair="BTC/USDT",
        )
        # Check output.
        self.assertEqual(fetch_ohlcv_mock.call_count, 1)
        actual_args = tuple(fetch_ohlcv_mock.call_args)
        expected_args = (("BTC/USDT",), {"bar_per_iteration": 1000})
        self.assertEqual(actual_args, expected_args)
        actual_output = hpandas.df_to_str(ohlcv_data)
        expected_output = r"""dummy
            0  dummy
        """
        self.assert_equal(actual_output, expected_output, fuzzy_match=True)

    def test_download_ohlcv_websocket_kline_is_not_present(self) -> None:
        """
        Verify that warning message is properly logged when last minutes
        timestamp not in the downloaded raw websocket data.
        """
        # Initialize class and parameters.
        exchange_id = "binance"
        contract_type = "futures"
        extractor = imvcdexex.CcxtExtractor(exchange_id, contract_type)
        currency_pair = "BTC_USDT"
        # Mock currency pairs.
        extractor.currency_pairs = [currency_pair]
        # Mock an async_exchange.
        extractor._async_exchange = umock.MagicMock()
        # Test case 1 ------------------------------------------------------------
        # Last minute timestamp is not in the downloaded raw websocket data.
        # Mock return value of trades.
        ohlcv_data = ccxtpro.base.cache.ArrayCacheByTimestamp()
        ohlcv_data.append([1645660900000, 1.11, 2.11, 3.11, 4.11, 5.11])
        ohlcv_data.append([1645660900000, 1.11, 2.11, 3.11, 4.11, 5.11])
        expected = {"1m": ohlcv_data}
        extractor._async_exchange.ohlcvs.__getitem__.return_value = expected
        # Run with mocked log.
        with umock.patch.object(imvcdexex, "_LOG") as mock_log:
            extractor._download_websocket_ohlcv(exchange_id, currency_pair)
        actual_logs = str(mock_log.method_calls)
        # Check output.
        expected_logs = (
            "[call.warning('Latest kline is not present in the downloaded data."
            " currency_pair=BTC_USDT.')]"
        )
        self.assert_equal(actual_logs, expected_logs, fuzzy_match=True)
        # Test case 2 ------------------------------------------------------------
        # Last minute timestamp is in the downloaded raw websocket data.
        # Mock return value of trades.
        timestamp_to_check = (
            pd.Timestamp.utcnow() - pd.Timedelta(minutes=1)
        ).replace(second=0, microsecond=0)
        timestamp_to_check = hdateti.convert_timestamp_to_unix_epoch(
            timestamp_to_check, unit="ms"
        )
        ohlcv_data = ccxtpro.base.cache.ArrayCacheByTimestamp()
        ohlcv_data.append([1645660900000, 1.11, 2.11, 3.11, 4.11, 5.11])
        ohlcv_data.append([timestamp_to_check, 1.11, 2.11, 3.11, 4.11, 5.11])
        expected = {"1m": ohlcv_data}
        extractor._async_exchange.ohlcvs.__getitem__.return_value = expected
        # Run with mocked log.
        with umock.patch.object(imvcdexex, "_LOG") as mock_log:
            extractor._download_websocket_ohlcv(exchange_id, currency_pair)
        actual_logs = str(mock_log.method_calls)
        # Check output.
        expected_logs = "[]"
        self.assert_equal(actual_logs, expected_logs, fuzzy_match=True)

    @umock.patch.object(imvcdexex.hdateti, "get_current_time")
    def test_fetch_ohlcv1(self, mock_get_current_time: umock.MagicMock) -> None:
        """
        Verify if download is properly requested and parsed upon retrieval.
        """
        # Prepare test data.
        current_time = "2022-02-24 00:00:00.000000+00:00"
        mock_get_current_time.return_value = current_time
        bars = [
            [1645660800000, 37250.02, 37267.8, 37205.4, 37218.81, 59.1615],
            [1645660860000, 37218.8, 37234.26, 37213.2, 37214.46, 23.41537],
            [1645660920000, 37214.47, 37224.2, 37138.58, 37138.58, 48.11884],
            [1645660980000, 37138.59, 37216.5, 37100.17, 37216.49, 53.65817],
            [1645661040000, 37216.49, 37302.46, 37213.66, 37270.45, 36.44746],
        ]
        columns = ["timestamp", "open", "high", "low", "close", "volume"]
        expected_df = pd.DataFrame(data=bars, columns=columns)
        expected_df["end_download_timestamp"] = current_time
        expected_df = hpandas.df_to_str(expected_df)
        # Initialize class.
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        exchange_class.currency_pairs = ["BTC/USDT"]
        # Mock a call to ccxt's `fetch_ohlcv` method called inside `_fetch_ohlcv`.
        with umock.patch.object(
            exchange_class._sync_exchange, "fetch_ohlcv", create=True
        ) as fetch_ohlcv_mock:
            fetch_ohlcv_mock.return_value = bars
            # Run.
            ohlcv_df = exchange_class._fetch_ohlcv(
                currency_pair="BTC_USDT",
                since=1,
                bar_per_iteration=2,
            )
            ohlcv_df = hpandas.df_to_str(ohlcv_df)
            self.assert_equal(ohlcv_df, expected_df)
            #
            self.assertEqual(fetch_ohlcv_mock.call_count, 1)
            actual_args = tuple(fetch_ohlcv_mock.call_args)
            expected_args = (
                ("BTC/USDT",),
                {"limit": 2, "since": 1, "timeframe": "1m"},
            )
            self.assertEqual(actual_args, expected_args)
            #
            actual_args = tuple(mock_get_current_time.call_args)
            expected_args = (("UTC",), {})
            self.assertEqual(actual_args, expected_args)
            self.assertEqual(mock_get_current_time.call_count, 1)

    @umock.patch.object(imvcdexex.hdateti, "get_current_time")
    def test_fetch_trades1(self, mock_get_current_time: umock.MagicMock) -> None:
        """
        Verify if download is properly requested and parsed upon retrieval.
        """
        # Prepare test data.
        current_time = "2023-01-02 00:00:00.000000+00:00"
        start_timestamp = pd.Timestamp("2023-01-01 00:00:01")
        end_timestamp = pd.Timestamp("2023-01-01 00:10:01")
        start_timestamp_in_ms = hdateti.convert_timestamp_to_unix_epoch(
            start_timestamp
        )
        end_timestamp_in_ms = hdateti.convert_timestamp_to_unix_epoch(
            end_timestamp
        )
        mock_get_current_time.return_value = current_time
        mock_trades_start_chunk = [
            ["123456789", start_timestamp_in_ms, "BTC/USDT", "buy", 10000.0, 1.0],
            ["123456790", start_timestamp_in_ms, "BTC/USDT", "buy", 10001.0, 1.0],
        ]
        mock_trades_chunk_with_extra = [
            ["123456791", start_timestamp_in_ms, "BTC/USDT", "buy", 10002.0, 1.0],
            [
                "123456792",
                end_timestamp_in_ms + 1000,
                "BTC/USDT",
                "buy",
                10003.0,
                1.0,
            ],
        ]
        # Prepare expected output.
        expected = r"""timestamp    symbol side    price  amount            end_download_timestamp
            0  1672531201000  BTC/USDT  buy  10000.0     1.0  2023-01-02 00:00:00.000000+00:00
            1  1672531201000  BTC/USDT  buy  10001.0     1.0  2023-01-02 00:00:00.000000+00:00
            2  1672531201000  BTC/USDT  buy  10002.0     1.0  2023-01-02 00:00:00.000000+00:00"""
        # Prepare data and initialize class before run.
        exchange_id = "binance"
        contract_type = "futures"
        ccxt_extractor = imvcdexex.CcxtExtractor(exchange_id, contract_type)
        currency_pair = "BTC_USDT"
        limit = 500
        with umock.patch.object(
            ccxt_extractor._sync_exchange, "fetch_trades", create=True
        ) as fetch_trades_mock:
            # Mock a call to CCXT `fetch_trades` method called inside
            # `_fetch_trades`.
            # The first call will return the first chunk of trades.
            # The second call will return the second chunk of trades
            # with an extra trade that is outside the requested time range.
            fetch_trades_mock.side_effect = [
                mock_trades_start_chunk,
                mock_trades_chunk_with_extra,
            ]
            # Run.
            ccxt_data = ccxt_extractor._fetch_trades(
                currency_pair=currency_pair,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                limit=limit,
            )
        # Check output.
        actual = hpandas.df_to_str(ccxt_data)
        self.assert_equal(actual, expected, fuzzy_match=True)

    def test_download_trades(self) -> None:
        """
        Verify if download is properly requested and parsed upon retrieval.
        """
        # Prepare test data.
        mock_trades = [
            [
                123456789000,
                "BTC/USDT",
                "buy",
                10000.0,
                1.0,
                "2022-02-24 00:00:00.000000+00:00",
            ],
            [
                123456789001,
                "BTC/USDT",
                "buy",
                10012.0,
                1.0,
                "2022-02-24 00:00:00.000000+00:00",
            ],
        ]
        columns = [
            "timestamp",
            "symbol",
            "side",
            "price",
            "amount",
            "end_download_timestamp",
        ]
        expected_df = pd.DataFrame(mock_trades, columns=columns)
        # Prepare data and initialize class before run.
        exchange_id = "binance"
        contract_type = "futures"
        ccxt_extractor = imvcdexex.CcxtExtractor(exchange_id, contract_type)
        currency_pair = "BTC_USDT"
        ccxt_extractor.currency_pairs = ["BTC/USDT"]
        start_timestamp = pd.Timestamp("2023-01-01 00:00:01")
        end_timestamp = pd.Timestamp("2023-01-01 00:10:01")
        with umock.patch.object(
            ccxt_extractor, "_fetch_trades", create=True
        ) as mock_fetch_trades:
            # Mock a call to ccxt's `fetch_trades` method called inside
            # `_fetch_trades`.
            mock_fetch_trades.return_value = expected_df
            actual_df = ccxt_extractor._download_trades(
                exchange_id,
                currency_pair,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
        self.assertTrue(actual_df.equals(expected_df))
        """
        Verify if download is properly requested and parsed upon retrieval.
        """
        # Prepare test data.
        mock_trades = [
            [
                123456789000,
                "BTC/USDT",
                "buy",
                10000.0,
                1.0,
                "2022-02-24 00:00:00.000000+00:00",
            ],
            [
                123456789001,
                "BTC/USDT",
                "buy",
                10012.0,
                1.0,
                "2022-02-24 00:00:00.000000+00:00",
            ],
        ]
        columns = [
            "timestamp",
            "symbol",
            "side",
            "price",
            "amount",
            "end_download_timestamp",
        ]
        mocked_df = pd.DataFrame(mock_trades, columns=columns)
        # Prepare expected output.
        expected_output = """timestamp    symbol side    price  amount            end_download_timestamp
            0  123456789000  BTC/USDT  buy  10000.0     1.0  2022-02-24 00:00:00.000000+00:00
            1  123456789001  BTC/USDT  buy  10012.0     1.0  2022-02-24 00:00:00.000000+00:00"""
        # Prepare data and initialize class before run.
        exchange_id = "binance"
        contract_type = "futures"
        ccxt_extractor = imvcdexex.CcxtExtractor(exchange_id, contract_type)
        currency_pair = "BTC_USDT"
        ccxt_extractor.currency_pairs = ["BTC/USDT"]
        start_timestamp = pd.Timestamp("2023-01-01 00:00:01")
        end_timestamp = pd.Timestamp("2023-01-01 00:10:01")
        with umock.patch.object(
            ccxt_extractor, "_fetch_trades", create=True
        ) as mock_fetch_trades:
            # Mock a call to ccxt's `fetch_trades` method called inside
            # `_fetch_trades`.
            mock_fetch_trades.return_value = mocked_df
            actual_df = ccxt_extractor._download_trades(
                exchange_id,
                currency_pair,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
        actual_output = hpandas.df_to_str(actual_df)
        self.assert_equal(actual_output, expected_output, fuzzy_match=True)

    def test_get_exchange_currency_pairs(self) -> None:
        """
        Test that a non-empty list of exchange currencies is loaded.
        """
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        # Mock a call to ccxt's `load_markets` method called inside `get_exchange_currency_pairs`.
        with umock.patch.object(
            exchange_class._sync_exchange, "load_markets", create=True
        ) as load_markets_mock:
            load_markets_mock.return_value = {"BTC/USDT": {}}
            # Run.
            actual = exchange_class.get_exchange_currency_pairs()
            self.assertEqual(load_markets_mock.call_count, 1)
        # Check output.
        expected = ["BTC/USDT"]
        self.assertEqual(actual, expected)

    def test_download_ohlcv_invalid_input1(self) -> None:
        """
        Run with invalid start timestamp.
        """
        # Initialize class.
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        exchange_class.currency_pairs = ["BTC/USDT"]
        # Run with invalid input.
        start_timestamp = "invalid"
        end_timestamp = pd.Timestamp("2021-09-10T00:00:00Z")
        with pytest.raises(AssertionError) as fail:
            exchange_class._download_ohlcv(
                exchange_id="binance",
                currency_pair="BTC/USDT",
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
        # Check output for error.
        actual = str(fail.value)
        expected = (
            "'invalid' is '<class 'str'>' instead of "
            "'<class 'pandas._libs.tslibs.timestamps.Timestamp'"
        )
        self.assertIn(expected, actual)

    def test_download_ohlcv_invalid_input2(self) -> None:
        """
        Run with invalid end timestamp.
        """
        # Initialize class.
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        exchange_class.currency_pairs = ["BTC/USDT"]
        # Run with invalid input.
        start_timestamp = pd.Timestamp("2021-09-09T00:00:00Z")
        end_timestamp = "invalid"
        with pytest.raises(AssertionError) as fail:
            exchange_class._download_ohlcv(
                exchange_id="binance",
                currency_pair="BTC/USDT",
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
        # Check output for error.
        actual = str(fail.value)
        expected = (
            "'invalid' is '<class 'str'>' instead of "
            "'<class 'pandas._libs.tslibs.timestamps.Timestamp'"
        )
        self.assertIn(expected, actual)

    def test_download_ohlcv_invalid_input3(self) -> None:
        """
        Run with invalid range.

        Start greater than the end.
        """
        # Initialize class.
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        exchange_class.currency_pairs = ["BTC/USDT"]
        # Run with invalid input.
        start_timestamp = pd.Timestamp("2021-09-10T00:00:00Z")
        end_timestamp = pd.Timestamp("2021-09-09T00:00:00Z")
        with pytest.raises(AssertionError) as fail:
            exchange_class._download_ohlcv(
                exchange_id="binance",
                currency_pair="BTC/USDT",
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
        # Check output for error.
        actual = str(fail.value)
        expected = "2021-09-10 00:00:00+00:00 <= 2021-09-09 00:00:00+00:00"
        self.assertIn(expected, actual)

    def test_download_ohlcv_invalid_input4(self) -> None:
        """
        Run with invalid currency pair.
        """
        # Initialize class.
        exchange_class = imvcdexex.CcxtExtractor("binance", "spot")
        # Run with invalid input.
        with pytest.raises(AssertionError) as fail:
            exchange_class._download_ohlcv(
                exchange_id="binance",
                currency_pair="invalid_currency_pair",
                start_timestamp=None,
                end_timestamp=None,
            )
        # Check output for error.
        actual = str(fail.value)
        expected = "Currency pair is not present in exchange"
        self.assertIn(expected, actual)

    @umock.patch.object(imvcdexex.hdateti, "get_current_time")
    def test_download_bid_ask1(
        self, mock_get_current_time: umock.MagicMock
    ) -> None:
        """
        Verify that order book is downloaded correctly.
        """
        # Prepare test data.
        current_time = "2022-02-24 00:00:00"
        mock_get_current_time.return_value = current_time
        symbol = "BTC/BUSD"
        depth = 5
        exchange = "binance"
        exchange_class = imvcdexex.CcxtExtractor("binance", "futures")
        exchange_class.currency_pairs = [symbol]
        self.assertEqual(
            exchange_class._sync_exchange._extract_mock_name(),
            f"ccxt.{exchange}()",
        )
        # Mock a call to ccxt's `fetch_order_book` method called inside `_download_bid_ask`.
        with umock.patch.object(
            exchange_class._sync_exchange, "fetch_order_book", create=True
        ) as fetch_order_book_mock:
            fetch_order_book_mock.return_value = {
                "symbol": symbol,
                "bids": [
                    [18904.6, 15.996],
                    [18904.5, 0.457],
                    [18904.4, 0.148],
                    [18904.3, 0.25],
                    [18904.2, 0.016],
                ],
                "asks": [
                    [18904.7, 6.286],
                    [18904.8, 0.023],
                    [18904.9, 0.016],
                    [18905.0, 0.331],
                    [18905.1, 0.071],
                ],
                "timestamp": 1662561646753,
            }
            # Run.
            order_book = exchange_class._download_bid_ask(exchange, symbol, depth)
            #
            self.assertEqual(fetch_order_book_mock.call_count, 1)
            actual_args = tuple(fetch_order_book_mock.call_args)
            expected_args = ((symbol, depth), {})
            self.assertEqual(actual_args, expected_args)
            # Check output.
            actual_output = hpandas.df_to_str(order_book)
            expected_output = r"""
            timestamp  bid_price  bid_size  ask_price  ask_size  end_download_timestamp  level
            0  1662561646753    18904.6    15.996    18904.7     6.286  2022-02-24 00:00:00      1
            1  1662561646753    18904.5     0.457    18904.8     0.023  2022-02-24 00:00:00      2
            2  1662561646753    18904.4     0.148    18904.9     0.016  2022-02-24 00:00:00      3
            3  1662561646753    18904.3     0.250    18905.0     0.331  2022-02-24 00:00:00      4
            4  1662561646753    18904.2     0.016    18905.1     0.071  2022-02-24 00:00:00      5
            """
            self.assert_equal(actual_output, expected_output, fuzzy_match=True)

    def test__download_websocket_trades(self) -> None:
        """
        Verify that trades are downloaded correctly by websocket.
        """
        # Initialize class and parameters.
        exchange_id = "binance"
        contract_type = "futures"
        extractor = imvcdexex.CcxtExtractor(exchange_id, contract_type)
        currency_pair = "BTC_USDT"
        # Mock currency pairs.
        extractor.currency_pairs = [currency_pair]
        # Mock an async_exchange.
        extractor._async_exchange = umock.MagicMock()
        # Mock return value of trades.
        expected = [
            {
                "info": {},
                "timestamp": 1678109748838,
                "datetime": "2023-03-06T13:35:48.838Z",
                "symbol": "BTC/USDT",
                "id": "3363915321",
                "order": None,
                "type": None,
                "side": "buy",
                "takerOrMaker": "taker",
                "price": 22399.5,
                "amount": 0.035,
                "cost": 783.9825,
                "fee": None,
                "fees": [],
            }
        ]
        extractor._async_exchange.trades.get.return_value = {
            "some_key": "some_value"
        }
        extractor._async_exchange.trades.__getitem__.return_value = expected
        # Run.
        actual = extractor._download_websocket_trades(exchange_id, currency_pair)
        # Check output.
        self.assertEqual(actual["data"], expected)

    def test_download_bid_ask_invalid_input1(self) -> None:
        """
        Run with invalid currency pair.
        """
        # Initialize test data.
        exchange = "binance"
        exchange_class = imvcdexex.CcxtExtractor(exchange, "spot")
        exchange_class.currency_pairs = ["BTC/USDT"]
        fake_currency_pair = "NON_EXIST"
        # Run with invalid input.
        with pytest.raises(AssertionError) as fail:
            exchange_class._download_bid_ask(exchange, fake_currency_pair, 10)
        # Check output for error.
        actual = str(fail.value)
        expected = "Currency pair is not present in exchange"
        self.assertIn(expected, actual)


class TestCcxtExtractor2(hunitest.TestCase):
    @pytest.mark.superslow("~30 seconds.")
    @umock.patch.object(imvcdexex.hdateti, "get_current_time")
    def test_download_ohlcv_timestamp_representation1(
        self, mock_get_current_time: umock.MagicMock
    ) -> None:
        """
        Verify OHLCV data timestamps for exchange ID Binance.US and currency
        pair "BTC/USDT".
        """
        # Using Binance.US API because Binance API is not accessible.
        exchange_id = "binanceus"
        currency_pair = "BTC/USDT"
        contract_type = "spot"
        start_timestamp = pd.Timestamp("2022-10-20T00:01:00Z")
        end_timestamp = pd.Timestamp("2022-10-20T00:05:00Z")
        # Prepare expected output.
        # pylint: disable=line-too-long
        expected_output = r"""
        timestamp    open    high    low    close    volume    end_download_timestamp
        0    1666224060000    19120.48    19123.30    19114.05    19114.05    0.483268    2022-10-21 00:00:00.000000+00:00
        1    1666224120000    19117.81    19128.66    19117.81    19128.66    0.813596    2022-10-21 00:00:00.000000+00:00
        2    1666224180000    19128.27    19128.27    19115.57    19122.26    1.800264    2022-10-21 00:00:00.000000+00:00
        3    1666224240000    19118.08    19122.31    19115.23    19115.23    0.482966    2022-10-21 00:00:00.000000+00:00
        4    1666224300000    19120.87    19120.87    19113.28    19113.28    0.434573    2022-10-21 00:00:00.000000+00:00
        """
        # pylint: enable=line-too-long
        self._test_download_ohlcv_timestamp_representation_helper(
            exchange_id,
            currency_pair,
            contract_type,
            start_timestamp,
            end_timestamp,
            expected_output,
            mock_get_current_time,
        )

    @pytest.mark.superslow("~30 seconds.")
    @umock.patch.object(imvcdexex.hdateti, "get_current_time")
    def test_download_ohlcv_timestamp_representation2(
        self, mock_get_current_time: umock.MagicMock
    ) -> None:
        """
        Verify OHLCV data timestamps for exchange ID Binance.US and currency
        pair "ETH/USDT".
        """
        # Using Binance.US API because Binance API is not accessible.
        exchange_id = "binanceus"
        currency_pair = "ETH/USDT"
        contract_type = "spot"
        start_timestamp = pd.Timestamp("2022-10-20T00:01:00Z")
        end_timestamp = pd.Timestamp("2022-10-20T00:05:00Z")
        # Prepare expected output.
        # pylint: disable=line-too-long
        expected_output = r"""
        timestamp    open    high    low    close    volume    end_download_timestamp
        0    1666224060000    1284.46    1284.46    1284.46    1284.46    0.50910    2022-10-21 00:00:00.000000+00:00
        1    1666224120000    1284.46    1284.46    1284.46    1284.46    0.00000    2022-10-21 00:00:00.000000+00:00
        2    1666224180000    1285.00    1285.00    1284.45    1284.45    3.66371    2022-10-21 00:00:00.000000+00:00
        3    1666224240000    1284.45    1284.45    1284.45    1284.45    0.00000    2022-10-21 00:00:00.000000+00:00
        4    1666224300000    1283.32    1283.32    1283.32    1283.32    4.93685    2022-10-21 00:00:00.000000+00:00
        """
        # pylint: enable=line-too-long
        self._test_download_ohlcv_timestamp_representation_helper(
            exchange_id,
            currency_pair,
            contract_type,
            start_timestamp,
            end_timestamp,
            expected_output,
            mock_get_current_time,
        )

    def _test_download_ohlcv_timestamp_representation_helper(
        self,
        exchange_id: str,
        currency_pair: str,
        contract_type: str,
        start_timestamp: pd.Timestamp,
        end_timestamp: pd.Timestamp,
        expected_output: str,
        mock_get_current_time: umock.MagicMock,
    ) -> None:
        """
        Verify that OHLCV data timestamps are correctly represented.

        1. Perform a historical download of OHLCV data for a given time period
           and currency pair.
        2. Compare it to previously downloaded data using a specific CCXT version.
           This test ensures we can detect a change in interface (i.e. timestamp
           representation in this case) upon upgrading the library version.
        """
        # Mock current time.
        current_time = "2022-10-21 00:00:00.000000+00:00"
        mock_get_current_time.return_value = current_time
        # Initialize class.
        exchange_class = imvcdexex.CcxtExtractor(exchange_id, contract_type)
        exchange_class.currency_pairs = [currency_pair]
        # Download real OHLCV data using CCXT.
        ccxt_data = exchange_class._download_ohlcv(
            exchange_id=exchange_id,
            currency_pair=currency_pair,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            bar_per_iteration=500,
        )
        _LOG.info("\n==> Current CCXT version = '%s' <==", ccxt.__version__)
        # Check output.
        actual_output = hpandas.df_to_str(ccxt_data)
        self.assert_equal(actual_output, expected_output, fuzzy_match=True)
