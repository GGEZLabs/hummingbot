import asyncio
import math
from decimal import Decimal
from itertools import groupby
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.coinstore import (
    coinstore_constants as CONSTANTS,
    coinstore_utils,
    coinstore_web_utils as web_utils,
)
from hummingbot.connector.exchange.coinstore.coinstore_api_order_book_data_source import CoinstoreAPIOrderBookDataSource
from hummingbot.connector.exchange.coinstore.coinstore_api_user_stream_data_source import (
    CoinstoreAPIUserStreamDataSource,
)
from hummingbot.connector.exchange.coinstore.coinstore_auth import CoinstoreAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CoinstoreExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 1.0
    LONG_POLL_INTERVAL = 10
    TICK_INTERVAL_LIMIT = 10
    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        coinstore_api_key: str,
        coinstore_api_secret: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.api_key = coinstore_api_key
        self.secret_key = coinstore_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_coinstore_timestamp = 1.0
        super().__init__(client_config_map)

    @staticmethod
    def coinstore_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(coinstore_type: str) -> OrderType:
        return OrderType[coinstore_type]

    @property
    def authenticator(self):
        return CoinstoreAuth(api_key=self.api_key, secret_key=self.secret_key, time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "coinstore"
        else:
            return f"coinstore_{self._domain}"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.ACCOUNTS_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        if pairs_prices["code"] == CONSTANTS.API_SUCCESS_CODE:
            return pairs_prices["data"]
        return []

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = (
            "-1021" in error_description and "Timestamp for this request" in error_description
        )
        return is_time_synchronizer_related

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler, time_synchronizer=self._time_synchronizer, domain=self._domain, auth=self._auth
        )

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CoinstoreAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CoinstoreAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        try:
            timestamp = self.current_timestamp
            api_params = {
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
                "side": trade_type.name.upper(),
                "ordType": CONSTANTS.COINSTORE_ORDER_TYPE[order_type],
                "ordPrice": f"{price:f}",
                "ordQty": f"{amount:f}",
                "clOrdId": order_id,
                # "ordAmt" :  ,  # market price
                "timestamp": timestamp,
            }
            order_result = await self._api_post(
                path_url=CONSTANTS.REST_CREATE_ORDER, data=api_params, is_auth_required=True
            )

            exchange_order_id = str(order_result["data"]["ordId"])
            return exchange_order_id, timestamp
        except Exception as e:
            print(e)

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        api_params = {
            "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
        }
        if tracked_order.exchange_order_id is not None:
            api_params["ordId"] = tracked_order.exchange_order_id
        else:
            api_params["clOrdId"] = order_id

        cancel_result = await self._api_post(
            path_url=CONSTANTS.REST_CANCEL_ORDER, data=api_params, is_auth_required=True
        )
        if cancel_result["code"] != CONSTANTS.API_SUCCESS_CODE:
            return False
        if cancel_result["data"]["state"] != CONSTANTS.OrderState.CANCELED.name:
            return False
        return True

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        incomplete_orders.sort(key=attrgetter("trading_pair"))
        grouped_orders = {key: list(group) for key, group in groupby(incomplete_orders, key=attrgetter("trading_pair"))}

        successful_cancellations = []
        failed_cancellations = []
        for trading_pair, orders in grouped_orders.items():
            api_params = {
                "orderIds": [o.exchange_order_id for o in orders],
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            }
            cancel_result = await self._api_post(
                path_url=CONSTANTS.REST_CANCEL_BATCH_ORDERS, data=api_params, is_auth_required=True
            )
            if cancel_result["code"] != CONSTANTS.API_SUCCESS_CODE:
                continue
            cancel_result_data = cancel_result["data"]
            # this ID is exchange order ID
            successful_cancellations.extend([CancellationResult(id, True) for id in cancel_result_data["success"]])
            failed_cancellations.extend([CancellationResult(id, False) for id in cancel_result_data["reject"]])

        return successful_cancellations + failed_cancellations

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            'symbolId': 2,
            'symbolCode': 'trxUSDT',
            'tradeCurrencyCode': 'trx',
            'quoteCurrencyCode': 'USDT',
            'openTrade': True,
            'onLineTime': 1611104824934,
            'tickSz': 6,
            'lotSz': 2,
            'minLmtPr': '0.000001',
            'minLmtSz': '1',
            'minMktVa': '1',
            'minMktSz': '1',
            'makerFee': '0.002',
            'takerFee': '0.002'
        }
        """
        trading_pair_info = exchange_info_dict.get("data", [])
        retval = []
        for rule in filter(coinstore_utils.is_exchange_information_valid, trading_pair_info):
            try:

                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=rule.get("symbolCode").upper()
                )
                min_order_size = Decimal(rule.get("minLmtSz"))
                min_order_value = Decimal(rule.get("minMktVa"))
                tick_size = rule.get("tickSz")
                lotSz = Decimal(rule.get("lotSz"))
                min_notional = Decimal(rule.get("minMktSz"))

                price_step = Decimal("1") / Decimal(str(math.pow(10, tick_size)))
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_value=min_order_value,
                        min_order_size=min_order_size,
                        min_price_increment=Decimal(price_step),
                        min_base_amount_increment=Decimal(lotSz),
                        min_notional_size=Decimal(min_notional),
                    )
                )

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")
                # Refer to https://github.com/coinstore-exchange/coinstore-official-api-docs/blob/master/user-data-stream.md
                # As per the order update section in Coinstore the ID of the order being canceled is under the "C" key
                if event_type == "executionReport":
                    execution_type = event_message.get("x")
                    if execution_type != "CANCELED":
                        client_order_id = event_message.get("c")
                    else:
                        client_order_id = event_message.get("C")

                    if execution_type == "TRADE":
                        tracked_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        if tracked_order is not None:
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=event_message["N"],
                                flat_fees=[TokenAmount(amount=Decimal(event_message["n"]), token=event_message["N"])],
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(event_message["t"]),
                                client_order_id=client_order_id,
                                exchange_order_id=str(event_message["i"]),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(event_message["l"]),
                                fill_quote_amount=Decimal(event_message["l"]) * Decimal(event_message["L"]),
                                fill_price=Decimal(event_message["L"]),
                                fill_timestamp=event_message["T"] * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                    tracked_order = self._order_tracker.all_updatable_orders.get(client_order_id)
                    if tracked_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=event_message["E"] * 1e-3,
                            new_state=CONSTANTS.ORDER_STATE[event_message["X"]],
                            client_order_id=client_order_id,
                            exchange_order_id=str(event_message["i"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "outboundAccountPosition":
                    balances = event_message["B"]
                    for balance_entry in balances:
                        asset_name = balance_entry["a"]
                        free_balance = Decimal(balance_entry["f"])
                        total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        try:
            if order.exchange_order_id is not None:
                exchange_order_id = int(order.exchange_order_id)
                trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
                all_fills_response = await self._api_get(
                    path_url=CONSTANTS.ACCOUNT_MATCHES_TRADE,
                    params={"symbol": trading_pair, "ordId": exchange_order_id},
                    is_auth_required=True,
                )

                for trade in all_fills_response["data"]:
                    exchange_order_id = str(trade["orderId"])
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent=Decimal(trade["acturalFeeRate"]),
                        percent_token=trade["acturalFeeRate"],
                        flat_fees=[TokenAmount(amount=Decimal(trade["fee"]), token=order.base_asset)],
                    )
                    price = Decimal(trade["execAmt"]) / Decimal(trade["execQty"])
                    trade_update = TradeUpdate(
                        trade_id=str(trade["tradeId"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(trade["execQty"]),
                        fill_quote_amount=Decimal(trade["execAmt"]),
                        fill_price=price,
                        fill_timestamp=trade["matchTime"] * 1e-3,
                    )
                    trade_updates.append(trade_update)
        except Exception as e:
            print(e)
        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.ORDER_INFO_PATH_URL,
            params={"ordId": tracked_order.exchange_order_id},
            is_auth_required=True,
        )
        if updated_order_data["code"] == CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE:
            return OrderUpdate(
                exchange_order_id=tracked_order.exchange_order_id,
                new_state=CONSTANTS.ORDER_STATE["CANCELED"],
                trading_pair=tracked_order.trading_pair,
                client_order_id=tracked_order.client_order_id,
                update_timestamp=self.current_timestamp,
            )

        order_data = updated_order_data["data"]
        new_state = CONSTANTS.ORDER_STATE[order_data["ordStatus"]]

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(order_data["ordId"]),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=order_data["orderUpdateTime"] * 1e-3,
            new_state=new_state,
        )

        return order_update

    def sort_by_currency(self, x):
        return x["currency"]

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        account_info = await self._api_post(path_url=CONSTANTS.ACCOUNTS_PATH_URL, is_auth_required=True, data={})
        balances = account_info["data"]

        frozen_balances = sorted([balance for balance in balances if balance["type"] == 4], key=self.sort_by_currency)
        available_balances = sorted(
            [balance for balance in balances if balance["type"] == 1], key=self.sort_by_currency
        )

        for available_balance, frozen_balance in zip(available_balances, frozen_balances):
            asset_name = available_balance["currency"]

            self._account_available_balances[asset_name] = Decimal(available_balance["balance"])
            self._account_balances[asset_name] = Decimal(available_balance["balance"]) + Decimal(
                frozen_balance["balance"]
            )

            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        """"
        for account in account_info["data"]["wallet"]:
            asset_name = account["id"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["available"])) + Decimal(str(account["frozen"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]
        """

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(coinstore_utils.is_exchange_information_valid, exchange_info["data"]):
            mapping[symbol_data["symbolCode"].upper()] = combine_to_hb_trading_pair(
                base=symbol_data["tradeCurrencyCode"].upper(), quote=symbol_data["quoteCurrencyCode"].upper()
            )
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        end_point = f"{CONSTANTS.TICKER_PRICE_PATH_URL};symbol={symbol.upper()}"
        resp_json = await self._api_get(path_url=end_point, limit_id=CONSTANTS.TICKER_PRICE_PATH_URL)
        ticker_data = resp_json["data"][0]
        return float(ticker_data["price"])

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_post(path_url=self.trading_pairs_request_path, data={})
        return exchange_info

    async def _make_network_check_request(self):
        await self._api_post(path_url=self.check_network_request_path, data={})

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_post(path_url=self.trading_pairs_request_path, data={})
        return exchange_info

    async def trading_pair_associated_to_exchange_symbol(
        self,
        symbol: str,
    ) -> str:
        symbol_map = await self.trading_pair_symbol_map()
        return symbol_map[symbol]
