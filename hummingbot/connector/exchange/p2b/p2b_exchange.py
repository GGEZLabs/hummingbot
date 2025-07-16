import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.p2b import p2b_constants as CONSTANTS, p2b_web_utils as web_utils
from hummingbot.connector.exchange.p2b.p2b_api_order_book_data_source import P2bAPIOrderBookDataSource
from hummingbot.connector.exchange.p2b.p2b_api_user_stream_data_source import P2bAPIUserStreamDataSource
from hummingbot.connector.exchange.p2b.p2b_auth import P2bAuth
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


class P2bExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 1.0
    LONG_POLL_INTERVAL = 10
    TICK_INTERVAL_LIMIT = 10
    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        p2b_api_key: str,
        p2b_api_secret: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.api_key = p2b_api_key
        self.secret_key = p2b_api_secret
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_p2b_timestamp = 1.0
        self._unfilled_or_partially_filled_responses_cache = {}

        super().__init__(client_config_map)

    @staticmethod
    def p2b_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(p2b_type: str) -> OrderType:
        return OrderType[p2b_type]

    @property
    def authenticator(self):
        return P2bAuth(api_key=self.api_key, secret_key=self.secret_key, time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "p2b"
        else:
            return f"p2b{self._domain}"

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

    async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
        pairs_prices = await self._api_get(path_url=CONSTANTS.TICKERS_PATH_URL)
        if pairs_prices["success"]:
            return pairs_prices["result"]
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
        return P2bAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return P2bAPIUserStreamDataSource(
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
            amount_str = f"{amount:f}"
            price_str = f"{price:f}"
            side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
            symbol = self.get_exchange_trading_pair(trading_pair=trading_pair)

            api_data = {
                "market": symbol,
                "side": side_str,
                "amount": amount_str,
                "price": price_str,
            }

            order_result = await self._api_post(
                path_url=CONSTANTS.CREATE_NEW_ORDER_PATH_URL, data=api_data, is_auth_required=True
            )

            o_id = str(order_result["result"]["orderId"])
            transact_time = order_result["result"]["timestamp"]
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

            symbol = self.get_exchange_trading_pair(trading_pair=tracked_order.trading_pair)
            api_data = {"market": symbol, "orderId": tracked_order.exchange_order_id}
            cancel_result = await self._api_post(
                path_url=CONSTANTS.CANCEL_ORDER_PATH_URL, data=api_data, is_auth_required=True
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
        Example:
            {
            "name": "YFI_BTC",
            "stock": "YFI",
            "money": "BTC",
            "precision": {
                "money": "4",
                "stock": "5",
                "fee": "4"
            },
            "limits": {
                "min_amount": "0.00001",
                "max_amount": "9000",
                "step_size": "0.00001",
                "min_price": "0.0001",
                "max_price": "100000",
                "tick_size": "0.0001",
                "min_total": "0.0001"
                }
            }
        """
        trading_pair_rules = exchange_info_dict.get("result", [])
        retval = []
        for rule in trading_pair_rules:
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(
                    symbol=self.get_hbot_trading_pair(rule.get("name"))
                )
                limits = rule.get("limits")
                min_order_size = Decimal(limits.get("min_amount"))
                tick_size = limits.get("tick_size")
                step_size = Decimal(limits.get("step_size"))
                min_notional = Decimal(limits.get("min_total"))

                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=Decimal(tick_size),
                        min_base_amount_increment=Decimal(step_size),
                        min_notional_size=Decimal(min_notional),
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
                # Refer to https://github.com/p2b-exchange/p2b-official-api-docs/blob/master/user-data-stream.md
                # As per the order update section in P2b the ID of the order being canceled is under the "C" key
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
            exchange_order_id = int(order.exchange_order_id)
            trading_pair = self.get_exchange_trading_pair(trading_pair=order.trading_pair)

            # get deal details for the filled order id.
            filled_orders_response = await self._api_post(
                path_url=CONSTANTS.ORDER_PATH_URL,
                data={"orderId": exchange_order_id},
                is_auth_required=True,
            )

            if "records" in filled_orders_response["result"]:
                filled_order_deals = filled_orders_response["result"]["records"]
                if len(filled_order_deals) > 0:
                    """
                    {
                        "id": 12112428585,
                        "time": 1741081455.015521,
                        "fee": "0.00180153",
                        "price": "0.01665",
                        "amount": "54.1",
                        "dealOrderId": 256198314826,
                        "role": 1,
                        "deal": "0.900765"
                    },
                    {
                        "id": 12112415901,
                        "time": 1741081348.30054,
                        "fee": "0.0021978",
                        "price": "0.01665",
                        "amount": "66",
                        "dealOrderId": 256198081697,
                        "role": 1,
                        "deal": "1.0989"
                    }
                    """
                    latest_deal = filled_order_deals[-1]
                    total_fee = Decimal(0)
                    total_filled_base_amount = Decimal(0)
                    total_filled_quote_amount = Decimal(0)
                    for deal in filled_order_deals:
                        total_fee += Decimal(deal["fee"])
                        total_filled_base_amount += Decimal(deal["amount"])
                        total_filled_quote_amount += Decimal(deal["deal"])

                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=str(total_fee),
                        flat_fees=[TokenAmount(amount=total_fee, token=order.base_asset)],
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(latest_deal["dealOrderId"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=str(exchange_order_id),
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=total_filled_base_amount,
                        fill_quote_amount=total_filled_quote_amount,
                        fill_price=Decimal(order.price),
                        fill_timestamp=latest_deal["time"],
                    )
                    trade_updates.append(trade_update)

            if len(trade_updates) > 0:
                return trade_updates

            # Query unfilled or partially filled orders.
            unfilled_or_partially_filled_response = await self._get_unfilled_or_partially_filled_response(trading_pair)
            unfilled_or_partially_filled_orders = unfilled_or_partially_filled_response["result"]

            for trade in unfilled_or_partially_filled_orders:
                """
                {
                    "orderId": 256198053319,
                    "market": "AUT_USDT",
                    "price": "0.01665",
                    "side": "sell",
                    "type": "limit",
                    "timestamp": 1741081334.855849,
                    "dealMoney": "1.0989",
                    "dealStock": "66",
                    "amount": "120.1",
                    "takerFee": "0.002",
                    "makerFee": "0.002",
                    "left": "54.1",
                    "dealFee": "0.0021978",
                    "clientOrderId": ""
                 }
                """
                if trade["orderId"] == exchange_order_id:
                    #  the order is not fully filled return the trade details
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=trade["takerFee"] if trade["side"] == "buy" else trade["makerFee"],
                        flat_fees=[TokenAmount(amount=Decimal(trade["dealFee"]), token=order.base_asset)],
                    )
                    trade_update = TradeUpdate(
                        trade_id=str(trade["orderId"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=str(exchange_order_id),
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(trade["dealStock"]),
                        fill_quote_amount=Decimal(trade["dealMoney"]),
                        fill_price=Decimal(trade["price"]),
                        fill_timestamp=float(trade["timestamp"]),
                    )
                    trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        if tracked_order.exchange_order_id is None:
            raise ValueError("Cannot request order status without exchange_order")

        exchange_order_id = int(tracked_order.exchange_order_id)
        trading_pair = self.get_exchange_trading_pair(trading_pair=tracked_order.trading_pair)
        new_state = None
        update_timestamp = None

        # get deal details for the filled order id.
        filled_orders_response = await self._api_post(
            path_url=CONSTANTS.ORDER_PATH_URL,
            data={"orderId": exchange_order_id},
            is_auth_required=True,
        )
        if "records" in filled_orders_response["result"]:
            filled_order_deals = filled_orders_response["result"]["records"]
            if len(filled_order_deals) > 0:
                # the order is filled
                filled_order = filled_order_deals[-1]
                new_state = CONSTANTS.ORDER_STATE["FILLED"]
                update_timestamp = filled_order["time"]

        if new_state is None:
            # Query unfilled or partially filled orders.
            unfilled_or_partially_filled_response = await self._get_unfilled_or_partially_filled_response(trading_pair)

            unfilled_or_partially_filled_orders = unfilled_or_partially_filled_response["result"]
            for trade in unfilled_or_partially_filled_orders:
                if trade["orderId"] == exchange_order_id:
                    if trade["dealMoney"] == "0":
                        new_state = CONSTANTS.ORDER_STATE["OPEN"]
                    else:
                        new_state = CONSTANTS.ORDER_STATE["PARTIALLY_FILLED"]
                    update_timestamp = trade["timestamp"]
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
        account_info = await self._api_post(path_url=CONSTANTS.BALANCES_PATH_URL, data={}, is_auth_required=True)
        balances = account_info["result"]
        for asset_name in balances:
            if balances[asset_name]["available"] == "0" and balances[asset_name]["freeze"] == "0":
                continue

            free_balance = Decimal(balances[asset_name]["available"])
            total_balance = Decimal(balances[asset_name]["available"]) + Decimal(balances[asset_name]["freeze"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in exchange_info["result"]:
            mapping[self.get_hbot_trading_pair(symbol_data["name"])] = combine_to_hb_trading_pair(
                base=symbol_data["stock"], quote=symbol_data["money"]
            )
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {"market": self.get_exchange_trading_pair(trading_pair=trading_pair)}
        resp_json = await self._api_request(method=RESTMethod.GET, path_url=CONSTANTS.TICKER_PATH_URL, params=params)
        return float(resp_json["result"]["last"])

    def get_exchange_trading_pair(self, trading_pair: str) -> str:
        return trading_pair.replace("-", "_")

    def get_hbot_trading_pair(self, trading_pair: str) -> str:
        return trading_pair.replace("_", "")

    async def _get_unfilled_or_partially_filled_response(self, market: str):
        unfilled_or_partially_filled_response = None

        if self._unfilled_or_partially_filled_responses_cache.get(market) is not None:
            if (
                self._unfilled_or_partially_filled_responses_cache[market]["timestamp"]
                > self.current_timestamp - CONSTANTS.OPEN_ORDERS_CACHE_TIME
            ):
                unfilled_or_partially_filled_response = self._unfilled_or_partially_filled_responses_cache[market][
                    "response"
                ]
        if unfilled_or_partially_filled_response is None:
            unfilled_or_partially_filled_response = await self._api_post(
                path_url=CONSTANTS.OPEN_ORDERS_PATH_URL,
                data={"market": market},
                is_auth_required=True,
            )
            self._unfilled_or_partially_filled_responses_cache[market] = {
                "response": unfilled_or_partially_filled_response,
                "timestamp": self.current_timestamp,
            }
        return unfilled_or_partially_filled_response
