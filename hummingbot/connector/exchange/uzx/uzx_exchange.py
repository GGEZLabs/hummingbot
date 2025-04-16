import asyncio
import math
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.uzx import uzx_constants as CONSTANTS, uzx_web_utils as web_utils
from hummingbot.connector.exchange.uzx.uzx_api_order_book_data_source import UzxAPIOrderBookDataSource
from hummingbot.connector.exchange.uzx.uzx_api_user_stream_data_source import UzxAPIUserStreamDataSource
from hummingbot.connector.exchange.uzx.uzx_auth import UzxAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class UzxExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        uzx_api_key: str,
        uzx_api_secret: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.api_key = uzx_api_key
        self.secret_key = uzx_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_uzx_timestamp = 1.0
        self._unfilled_or_partially_filled_responses_cache = {}
        self._filled_responses_cache = {}

        super().__init__(client_config_map)

    @staticmethod
    def uzx_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(uzx_type: str) -> OrderType:
        return OrderType[uzx_type]

    @property
    def authenticator(self):
        return UzxAuth(api_key=self.api_key, secret_key=self.secret_key, time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "uzx"
        else:
            return f"uzx{self._domain}"

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
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.MARKETS_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.MARKETS_PATH_URL

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
        return UzxAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return UzxAPIUserStreamDataSource(
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
        order_result = None
        try:

            side_str = (
                CONSTANTS.Order_Direction.buy.value
                if trade_type is TradeType.BUY
                else CONSTANTS.Order_Direction.sell.value
            )
            symbol = self.get_exchange_trading_pair(trading_pair=trading_pair)

            api_data = {
                "symbol": symbol,
                "price": float(price),
                "amount": float(amount),
                "direction": side_str,
                "type": CONSTANTS.Order_Type.limit_price.value,
            }
            order_result = await self._api_get(
                path_url=CONSTANTS.CREATE_NEW_ORDER_PATH_URL, params=api_data, is_auth_required=True
            )
            if not order_result["success"]:
                raise IOError(
                    f"Error submitting {trade_type.name.upper()} order to {self.name_cap}. Error: {order_result['message']}"
                )

            o_id = str(order_result["orderId"])
            transact_time = order_result["serTime"]
        except IOError as e:
            error_description = str(e)
            is_server_overloaded = (
                "status is 503" in error_description
                and "Unknown error, please check your request or try again later." in error_description
            )
            if is_server_overloaded:
                o_id = "UNKNOWN"
                transact_time = self._time_synchronizer.time()
            else:
                raise
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):

        try:
            if tracked_order.exchange_order_id is None:
                return True
            cancel_result = await self._api_get(
                path_url=CONSTANTS.CANCEL_ORDER_PATH_URL.format(orderId=tracked_order.exchange_order_id),
                limit_id=CONSTANTS.CANCEL_ORDER_PATH_URL,
                is_auth_required=True,
            )

            # return True if the order is successfully cancelled else False
            return cancel_result.get("success")
        # if the order is not found then with status 400 and error code 2020 return True
        except IOError as e:
            error_description = str(e)
            if "status is 400" in error_description and str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in error_description:
                return True
            else:
                raise e

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        {
            "product_id": 204165,
            "product_name": "BTCUSDT",
            "swap_value": "0.001",
            "base_coin_id": 9075,
            "base_coin_name": "BTC",
            "quote_coin_id": 9747,
            "quote_coin_name": "USDT",
            "coin_precision": 3,
            "price_precision": 1,
            "price_unit": "0.1",
            "price_range": "0.05",
            "max_leverage": 100,
            "max_once_limit_num": 300000,
            "max_once_market_num": 100000,
            "max_hold_num": 1000000,
            "status": 1,
            "maker_fee": "0.0004",
            "taker_fee": "0.0006",
            "sort": 0,
        }
        """
        trading_pair_rules = exchange_info_dict.get("data", [])
        retval = []
        temp_min_order_size = "0.00001"
        for rule in trading_pair_rules:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("product_name"))
                min_order_size = Decimal(temp_min_order_size)  # TODO Fill minimum order size
                tick_size = rule.get("price_precision")
                step_size = Decimal(temp_min_order_size)  # TODO This is not the step_size it is wrong and way to hight
                min_notional = Decimal(temp_min_order_size)  # TODO Fill minimum order notional size
                price_step = Decimal("1") / Decimal(str(math.pow(10, tick_size)))
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=price_step,
                        min_base_amount_increment=step_size,
                        min_notional_size=min_notional,
                    )
                )

            except Exception as e:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.", e)
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
                if "result" in event_message:
                    continue

                event_type = event_message.get("method")
                # Refer to https://github.com/uzx-exchange/uzx-official-api-docs/blob/master/user-data-stream.md
                # As per the order update section in Uzx the ID of the order being canceled is under the "C" key
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
        if order.exchange_order_id is not None:
            exchange_order_id = order.exchange_order_id
            trading_pair = self.get_exchange_trading_pair(trading_pair=order.trading_pair)

            # get deal details for the filled order id.
            filled_orders_response = await self._get_filled_response(trading_pair)
            for filled_order in filled_orders_response:
                # TODO: check if there is a way to get the fee
                total_fee = 0
                if filled_order["orderId"] == exchange_order_id:
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=str(total_fee),
                        flat_fees=[TokenAmount(amount=total_fee, token=order.base_asset)],
                    )
                    fill_time = filled_order[
                        (
                            "completedTime"
                            if filled_order["status"] == CONSTANTS.OrderStatus.COMPLETED.value
                            else "canceledTime"
                        )
                    ]
                    trade_update = TradeUpdate(
                        trade_id=f"T{fill_time}",
                        client_order_id=order.client_order_id,
                        exchange_order_id=str(exchange_order_id),
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(filled_order["tradedAmount"]),
                        fill_quote_amount=Decimal(filled_order["turnover"]),
                        fill_price=Decimal(filled_order["price"]),
                        fill_timestamp=fill_time,
                    )
                    trade_updates.append(trade_update)

            if len(trade_updates) > 0:
                return trade_updates

            # Query unfilled or partially filled orders.
            unfilled_or_partially_filled_response = await self._get_unfilled_or_partially_filled_response(trading_pair)
            for unfilled_order in unfilled_or_partially_filled_response:
                if unfilled_order["orderId"] == exchange_order_id:

                    fill_timestamp = unfilled_order["time"]
                    order_details = unfilled_order["detail"]
                    # TODO: check if there is a way to get the fee
                    total_fee = 0
                    if len(order_details) > 0:
                        fill_timestamp = order_details[-1]["time"]

                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=str(total_fee),
                        flat_fees=[TokenAmount(amount=total_fee, token=order.base_asset)],
                    )
                    trade_update = TradeUpdate(
                        trade_id=f"T{fill_timestamp}",
                        client_order_id=order.client_order_id,
                        exchange_order_id=str(exchange_order_id),
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(unfilled_order["tradedAmount"]),
                        fill_quote_amount=Decimal(unfilled_order["turnover"]),
                        fill_price=Decimal(unfilled_order["price"]),
                        fill_timestamp=fill_timestamp,
                    )
                    trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        if tracked_order.exchange_order_id is None:
            raise ValueError("Cannot request order status without exchange_order")

        exchange_order_id = tracked_order.exchange_order_id
        trading_pair = self.get_exchange_trading_pair(trading_pair=tracked_order.trading_pair)
        new_state = None
        update_timestamp = None

        # get deal details for the filled order id.
        filled_orders_response = await self._get_filled_response(trading_pair)

        for filled_order in filled_orders_response:
            if filled_order["orderId"] == exchange_order_id:
                status = filled_order["status"]
                new_state = CONSTANTS.ORDER_STATE.get(
                    "FILLED" if status == CONSTANTS.OrderStatus.COMPLETED.value else "CANCELED"
                )
                update_timestamp = filled_order.get(
                    "completedTime" if status == CONSTANTS.OrderStatus.COMPLETED.value else "canceledTime"
                )

        if new_state is None:
            # Query unfilled or partially filled orders.
            unfilled_or_partially_filled_response = await self._get_unfilled_or_partially_filled_response(trading_pair)
            for unfilled_order in unfilled_or_partially_filled_response:
                if unfilled_order["orderId"] == exchange_order_id:
                    if unfilled_order["tradedAmount"] == 0:
                        new_state = CONSTANTS.ORDER_STATE["OPEN"]
                    else:
                        new_state = CONSTANTS.ORDER_STATE["PARTIALLY_FILLED"]
                    update_timestamp = unfilled_order["timestamp"]
                    break

        # if not found in the open orders or filled orders then the order is canceled
        new_state = new_state or CONSTANTS.ORDER_STATE["CANCELED"]
        update_timestamp = update_timestamp or self.current_timestamp

        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(tracked_order.exchange_order_id),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._api_get(
            path_url=CONSTANTS.BALANCES_PATH_URL, params={"symbol": ""}, is_auth_required=True
        )
        if not account_info["success"]:
            return

        assets = account_info["data"]
        for asset_data in assets:
            if asset_data["totalBalance"] == 0:
                continue
            asset_name = asset_data["coin"]["unit"]
            free_balance = Decimal(asset_data["balance"])
            total_balance = Decimal(asset_data["totalBalance"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)
        exchange_info["data"].extend(CONSTANTS.CUSTOMER_MARKET_PAIR)
        return exchange_info

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        exchange_info["data"].extend(CONSTANTS.CUSTOMER_MARKET_PAIR)
        return exchange_info

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in exchange_info["data"]:
            mapping[symbol_data["product_name"]] = combine_to_hb_trading_pair(
                base=symbol_data["base_coin_name"], quote=symbol_data["quote_coin_name"]
            )
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        # Symbol should be in the format of "BTC/USDT"
        params = {"symbol": self.get_exchange_trading_pair(trading_pair=trading_pair), "size": 1}
        resp_json = await self._api_request(
            method=RESTMethod.GET, path_url=CONSTANTS.LATEST_TRADES_PATH_URL, params=params, is_auth_required=True
        )
        return float(resp_json[0]["price"])

    def get_exchange_trading_pair(self, trading_pair: str) -> str:
        return trading_pair.replace("-", "/")

    def get_hbot_trading_pair(self, trading_pair: str) -> str:
        return trading_pair.replace("/", "")

    async def _get_unfilled_or_partially_filled_response(self, market: str):
        unfilled_or_partially_filled_response = None

        if self._unfilled_or_partially_filled_responses_cache.get(market) is not None:
            if (
                self._unfilled_or_partially_filled_responses_cache[market]["timestamp"]
                > self.current_timestamp - CONSTANTS.ORDER_REQUESTS_CACHE_TIME
            ):
                unfilled_or_partially_filled_response = self._unfilled_or_partially_filled_responses_cache[market][
                    "response"
                ]
        if unfilled_or_partially_filled_response is None:
            unfilled_or_partially_filled_response = await self._api_get(
                path_url=CONSTANTS.CURRENT_ORDERS_PATH_URL,
                params={"symbol": market, "pageNo": 1, "pageSize": 100},
                is_auth_required=True,
            )
            self._unfilled_or_partially_filled_responses_cache[market] = {
                "response": unfilled_or_partially_filled_response,
                "timestamp": self.current_timestamp,
            }
        return unfilled_or_partially_filled_response

    async def _get_filled_response(self, market: str):
        filled_response = None

        if self._filled_responses_cache.get(market) is not None:
            if (
                self._filled_responses_cache[market]["timestamp"]
                > self.current_timestamp - CONSTANTS.ORDER_REQUESTS_CACHE_TIME
            ):
                filled_response = self._filled_responses_cache[market]["response"]
        if filled_response is None:
            filled_response = await self._api_get(
                path_url=CONSTANTS.FILLED_ORDERS_PATH_URL,
                params={"symbol": market, "pageNo": 1, "pageSize": 100},
                is_auth_required=True,
            )
            self._filled_responses_cache[market] = {
                "response": filled_response,
                "timestamp": self.current_timestamp,
            }
        return filled_response

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(
            path_url=CONSTANTS.TICKERS_PATH_URL,
            is_auth_required=True,
        )
        if pairs_prices:
            return pairs_prices
        return []
