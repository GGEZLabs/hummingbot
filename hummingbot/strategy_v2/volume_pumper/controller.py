"""
Volume Pumper Controller - Main orchestrator.

This is a slim controller that coordinates all services to implement
the Volume Pumper trading strategy. It follows the Single Responsibility
Principle by delegating all business logic to specialized services.
"""

import time
from decimal import Decimal
from random import randint
from typing import List, Optional

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.utils.volume_pumper_config import VolumePumperConfigBase
from hummingbot.strategy_v2.volume_pumper.adapters.market_data_adapter import MarketDataAdapter
from hummingbot.strategy_v2.volume_pumper.adapters.order_adapter import OrderAdapter
from hummingbot.strategy_v2.volume_pumper.adapters.persistence_adapter import PersistenceAdapter
from hummingbot.strategy_v2.volume_pumper.domain.enums import StrategyState
from hummingbot.strategy_v2.volume_pumper.domain.market_config import VolumePumperMarketConfig
from hummingbot.strategy_v2.volume_pumper.domain.order_plan import OrderActionPlan
from hummingbot.strategy_v2.volume_pumper.services.architect_service import ArchitectService
from hummingbot.strategy_v2.volume_pumper.services.boundary_service import BoundaryService
from hummingbot.strategy_v2.volume_pumper.services.report_service import ReportService
from hummingbot.strategy_v2.volume_pumper.services.risk_service import RiskService
from hummingbot.strategy_v2.volume_pumper.services.volume_order_service import VolumeOrderService


class VolumePumperController(ControllerBase):
    """
    Main orchestrator for the Volume Pumper strategy.

    This controller is intentionally slim - it only handles:
    - State management
    - Service coordination
    - Action dispatching

    All business logic is delegated to specialized services:
    - VolumeOrderService: Volume order generation
    - BoundaryService: Boundary calculation and orders
    - ArchitectService: Phase decisions
    - RiskService: Risk monitoring
    - ReportService: Statistics and reporting
    """

    # Class constants
    ACTIVE_ORDER_LIFESPAN = 20  # seconds

    def __init__(
        self,
        config: VolumePumperConfigBase,
        volume_service: VolumeOrderService,
        boundary_service: BoundaryService,
        architect_service: ArchitectService,
        risk_service: RiskService,
        report_service: ReportService,
        market_data: MarketDataAdapter,
        order_adapter: OrderAdapter,
        persistence: PersistenceAdapter,
        market_data_provider=None,
        actions_queue=None,
        *args,
        **kwargs,
    ):
        """
        Initialize the controller with injected dependencies.

        All services are injected rather than created internally,
        enabling easy testing and configuration.
        """
        super().__init__(config, market_data_provider, actions_queue, *args, **kwargs)

        # Configuration
        self.config = config
        self.controller_id = config.id
        self.skip_order_cancellation = True

        # Injected services
        self._volume_service = volume_service
        self._boundary_service = boundary_service
        self._architect_service = architect_service
        self._risk_service = risk_service
        self._report_service = report_service

        # Injected adapters
        self._market_data = market_data
        self._order_adapter = order_adapter
        self._persistence = persistence

        # State
        self._state = StrategyState.NOT_INITIALIZED
        self._market_config: Optional[VolumePumperMarketConfig] = None
        self._last_trade_price: Decimal = Decimal("0")
        self._last_order_timestamp: float = 0
        self._random_delay: int = 0
        self._next_architect_timestamp: float = 0
        self._last_architect_action_time: float = 0
        self._pending_action_plan: Optional[OrderActionPlan] = None
        self._conflicting_orders: List = []
        self._is_refresh_task_running: bool = False

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def state(self) -> StrategyState:
        """Get the current strategy state."""
        return self._state

    @property
    def connector(self) -> ConnectorBase:
        """Get the underlying connector."""
        return self.market_data_provider.connectors[self.config.exchange]

    @property
    def current_timestamp(self) -> int:
        """Get the current Unix timestamp."""
        return int(time.time())

    @property
    def is_ready_for_volume_orders(self) -> bool:
        """Check if it's time to create volume orders."""
        elapsed = self.current_timestamp - self._last_order_timestamp
        required_delay = self.config.delay_order_time + self._random_delay
        return elapsed >= required_delay

    @property
    def is_ready_for_architect(self) -> bool:
        """Check if architect can take action."""
        if self.current_timestamp < self._next_architect_timestamp:
            return False

        if time.time() - self._last_architect_action_time < 20:
            return False

        if self._state == StrategyState.ARCHITECT_COOLDOWN:
            # the cooldown has expired - we can go back to running and removing the conflicting orders
            self._state = StrategyState.RUNNING
            self._conflicting_orders = []

        return True

    @property
    def is_ready_for_report(self) -> bool:
        """Check if periodic report should be generated."""
        return self._report_service.is_report_due()

    # =========================================================================
    # Main Execution Loop
    # =========================================================================

    async def update_processed_data(self):
        """Update processed data - required by base class."""
        pass

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Main entry point - determine actions for this tick.

        Called by the executor orchestrator each tick.

        Returns:
            List of executor actions to perform
        """
        actions = []
        actions.extend(self._create_actions())
        actions.extend(self._stop_actions())
        return actions

    def _create_actions(self) -> List[ExecutorAction]:
        """Determine actions to create new orders."""
        # Validate strategy state
        if not self._validate_state():
            return []

        # Check for periodic report
        if self.is_ready_for_report:
            self._generate_periodic_report()

        # Architect actions have priority
        if self.is_ready_for_architect:
            architect_actions = self._handle_architect()
            if architect_actions:
                self._last_architect_action_time = time.time()
                return architect_actions

        # Volume orders when architect is idle
        if self.is_ready_for_volume_orders:
            return self._handle_volume_orders()

        return []

    def _stop_actions(self) -> List[ExecutorAction]:
        """Determine actions to stop/cancel orders."""
        return self._get_orders_to_cancel()

    # =========================================================================
    # State Management
    # =========================================================================

    def _validate_state(self) -> bool:
        """
        Validate and update strategy state.

        Returns:
            True if strategy can proceed with actions
        """
        match self._state:
            case StrategyState.NOT_INITIALIZED:
                self._initialize_strategy()
                return False

            case StrategyState.STOPPED:
                return False

            case StrategyState.UNDERBALANCED:
                return False

            case StrategyState.RUNNING:
                # Check risk
                is_safe, notification = self._risk_service.is_balance_safe()
                if not is_safe:
                    self.logger().notify(notification)
                    self.logger().notify("\nStopping strategy. Canceling all orders.")
                    self._state = StrategyState.STOPPED
                    return False
                return True

            case _:
                return True

    def _initialize_strategy(self) -> None:
        """Initialize the strategy on first run."""
        # Initialize risk service with starting balance
        self._risk_service.initialize()

        # Load or create market config
        if self._persistence.config_exists():
            self._market_config = self._persistence.load_config()
        else:
            self._market_config = self._architect_service.create_initial_config()
            self._persistence.save_config(self._market_config)

        # Get initial price
        self._last_trade_price = self._market_data.get_last_trade_price()

        # Check starting balance and adjust config if needed
        self._check_and_adjust_for_balance()

        # Set state to running
        self._state = StrategyState.RUNNING

        self.logger().info(f"Strategy initialized. State: {self._state.name}")

    def _check_and_adjust_for_balance(self) -> None:
        """Check balance and adjust configuration if insufficient."""
        current_price = float(self._market_data.get_mid_price())
        quote_balance = float(self._market_data.get_available_quote_balance())
        base_balance = float(self._market_data.get_available_base_balance())

        min_balance = min(quote_balance / current_price, base_balance)
        total_required = self.config.order_upper_amount + self.config.max_allowed_depth

        if min_balance < total_required:
            proportion = min_balance / total_required

            new_upper = round(self.config.order_upper_amount * proportion)
            new_lower = round(self.config.order_lower_amount * proportion)
            new_depth = round(self.config.max_allowed_depth * proportion)

            self.logger().notify(
                f"INSUFFICIENT BALANCE - Adjusting config:\n"
                f"  order_upper_amount: {self.config.order_upper_amount} -> {new_upper}\n"
                f"  order_lower_amount: {self.config.order_lower_amount} -> {new_lower}\n"
                f"  max_allowed_depth: {self.config.max_allowed_depth} -> {new_depth}"
            )

            self.config.order_upper_amount = new_upper
            self.config.order_lower_amount = new_lower
            self.config.max_allowed_depth = new_depth

    # =========================================================================
    # Volume Order Handling
    # =========================================================================

    def _handle_volume_orders(self) -> List[ExecutorAction]:
        """Handle volume order generation."""
        # Calculate order price
        ask, bid, order_price = self._volume_service.calculate_order_price()

        # Validate spread
        if not self._volume_service.is_spread_acceptable(ask, bid):
            self._report_service.track_tight_spread()
            self._start_order_delay()
            return []

        # Check for price change
        if self._has_price_changed():
            self._start_order_delay()
            return []

        # Validate price is in spread
        if not self._volume_service.is_price_in_spread(order_price, ask, bid):
            self._report_service.track_out_of_spread()
            return []

        # Calculate amount
        order_amount = self._volume_service.calculate_order_amount(order_price)

        # Check minimum amount
        if not self._risk_service.is_amount_sufficient(order_amount):
            self._state = StrategyState.UNDERBALANCED
            self.logger().notify(
                f"Insufficient balance for minimum order.\n"
                f"Amount: {order_amount}, Minimum: {self.config.order_lower_amount}"
            )
            return []

        # Generate order pair
        order_candidates = self._volume_service.generate_order_pair(order_price, order_amount)

        # Create executor actions
        actions = [
            CreateExecutorAction(
                controller_id=self.controller_id,
                executor_config=self._create_executor_config(order),
            )
            for order in order_candidates
        ]

        # Update state
        self._last_trade_price = order_price
        self._report_service.track_trade(order_amount, order_price)
        self._start_order_delay()

        return actions

    def _has_price_changed(self) -> bool:
        """Check if the last trade price has changed."""
        current_price = self._market_data.get_last_trade_price()

        if current_price != self._last_trade_price:
            self._last_trade_price = current_price
            self.logger().info(f"Price changed to {current_price}")
            return True

        return False

    def _start_order_delay(self) -> None:
        """Start the delay timer for next order."""
        self._random_delay = randint(0, self.config.max_random_delay)
        self._last_order_timestamp = self.current_timestamp

    # =========================================================================
    # Architect Handling
    # =========================================================================

    def _handle_architect(self) -> List[ExecutorAction]:
        """Handle architect (boundary) actions."""
        if self._conflicting_orders and self._state != StrategyState.ARCHITECT_COOLDOWN:
            # Enter cooldown due to conflicting orders
            self._start_architect_cooldown()
            return []

        if self._state == StrategyState.ARCHITECT_COOLDOWN:
            # Cooldown just ended
            self._state = StrategyState.RUNNING
            self._conflicting_orders = []
            return []

        # Execute pending action plan
        if self._pending_action_plan and self._pending_action_plan.has_actions:
            plan = self._pending_action_plan
            self._pending_action_plan = None
            return self._execute_action_plan(plan)

        # Check if decision time
        if self._architect_service.should_make_decision(self._market_config):
            self._market_config = self._architect_service.make_decision(self._market_config)
            self._persistence.save_config(self._market_config)
            self.logger().info(f"New phase: {self._market_config.movement_type}")
            return []

        # Check if boundary update time
        last_updated = self._persistence.get_last_updated()
        if self._architect_service.should_update_boundaries(self._market_config, last_updated):
            self._update_boundaries()
            return []

        # Check if order book needs refresh
        if not self._boundary_service.is_order_book_valid(self._market_config):
            # Skip if refresh task is already running
            if not self._is_refresh_task_running:
                self._refresh_order_book()
                # delaying volume orders to avoid overlapping with the architecture orders
                self._start_order_delay()

            return []

        return []

    def _update_boundaries(self) -> None:
        """Update flexible boundaries."""
        new_support, new_resistance = self._boundary_service.apply_drift(self._market_config)
        self._market_config = self._market_config.with_updated_boundaries(
            flexible_support=new_support,
            flexible_resistance=new_resistance,
        )
        self._persistence.save_config(self._market_config)

    def _refresh_order_book(self) -> None:
        """
        Start async task to refresh the order book with new boundary orders.

        This is a non-blocking call that starts an async task. The task will:
        1. Fetch all open orders from the exchange (sync with exchange state)
        2. Organize orders and untrack out-of-range orders
        3. Generate new boundary orders
        4. Check for conflicts and optimize the action plan
        5. Set the pending action plan (executed on next tick)
        """
        if not self._is_refresh_task_running:
            safe_ensure_future(self._refresh_order_book_task())

    async def _refresh_order_book_task(self) -> None:
        """
        Async task to refresh order book with conflict detection.

        IMPORTANT: This task first syncs all open orders from the exchange
        to ensure accurate conflict detection.
        """
        self._is_refresh_task_running = True

        try:
            # Step 1: Sync orders from exchange and get organized orders
            # This also untracks out-of-range orders
            bids, asks = await self._order_adapter.get_organized_orders(
                static_support=self._market_config.static_support,
                static_resistance=self._market_config.static_resistance,
            )

            # Step 2: Generate new boundary orders
            new_orders = self._boundary_service.generate_boundary_orders(self._market_config)

            # Step 3: Create initial action plan
            plan = OrderActionPlan()
            for order in bids + asks:
                plan.add_cancellation(order.client_order_id)
            for order in new_orders:
                plan.add_creation(order)

            # Step 4: Optimize plan and check for conflicts
            # Note: We already synced orders above, so use sync version
            optimized_plan, conflicts = self._boundary_service.check_action_plan_conflicts(plan, self._market_config)

            # Step 5: Handle results
            if conflicts:
                # Store conflicting orders - will trigger cooldown in next _handle_architect()
                self._conflicting_orders = conflicts
                self.logger().notify(
                    f"Detected {len(conflicts)} conflicting orders from other traders. " f"Entering cooldown mode."
                )
            else:
                self._pending_action_plan = optimized_plan

        except Exception as e:
            self.logger().error(f"Error in refresh order book task: {str(e)}")

        finally:
            self._is_refresh_task_running = False

    def _start_architect_cooldown(self) -> None:
        """Start architect cooldown period."""
        interval = self._market_config.current_boundaries_update_interval
        self._next_architect_timestamp = self.current_timestamp + int(interval)
        self._state = StrategyState.ARCHITECT_COOLDOWN

        notification = "Architect paused due to conflicting orders:"
        for order in self._conflicting_orders:
            notification += f"\n  {order.order_side.name} @ {order.price}"
        self.logger().notify(notification)

    def _execute_action_plan(self, plan: OrderActionPlan) -> List[ExecutorAction]:
        """Execute an order action plan."""
        actions = []

        # Build executor lookup
        executors_by_id = {e.custom_info.get("order_id"): e for e in (self.executors_info or []) if e.custom_info}

        # Handle cancellations
        for order_id in plan.cancellations_ids:
            if order_id in executors_by_id:
                actions.append(
                    StopExecutorAction(
                        controller_id=self.controller_id,
                        executor_id=executors_by_id[order_id].id,
                        keep_position=False,
                    )
                )
            else:
                self._order_adapter.cancel_order(order_id)

        # Handle creations
        for order in plan.creations_candidates:
            actions.append(
                CreateExecutorAction(
                    controller_id=self.controller_id,
                    executor_config=self._create_executor_config(order, is_paywall=True),
                )
            )

        return actions

    # =========================================================================
    # Order Cancellation
    # =========================================================================

    def _get_orders_to_cancel(self) -> List[ExecutorAction]:
        """Get list of orders that should be cancelled."""
        executors_to_cancel = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: (
                not x.is_trading
                and x.is_active
                and self.current_timestamp - x.timestamp > self.ACTIVE_ORDER_LIFESPAN
                and not x.config.is_paywall_order
            ),
        )

        return [
            StopExecutorAction(
                controller_id=self.controller_id,
                executor_id=executor.id,
            )
            for executor in executors_to_cancel
        ]

    # =========================================================================
    # Reporting
    # =========================================================================

    def _generate_periodic_report(self) -> None:
        """Generate and log a periodic report."""
        report = self._report_service.generate_periodic_report()
        self.logger().notify(report)

    def to_format_status(self) -> List[str]:
        """Generate status lines for display."""
        status = super().to_format_status()
        status.append(self._report_service.generate_summary())
        status.append(self._format_config_status())
        status.append(self._format_market_config())
        return status

    def _format_config_status(self) -> str:
        """Format configuration status for display."""
        price_movement = self._volume_service.current_price_movement
        return (
            f"\nStrategy Config:"
            f"\n  Bot Status: {self._state.name}"
            f"\n  Exchange: {self.config.exchange}"
            f"\n  Trading Pair: {self.config.trading_pair}"
            f"\n  Order Amount Range: {self.config.order_lower_amount} - {self.config.order_upper_amount}"
            f"\n  Delay: {self.config.delay_order_time}s + Random(0-{self.config.max_random_delay}s)"
            f"\n  Min Spread: {self.config.minimum_ask_bid_spread} bps"
            f"\n  Price Movement: {price_movement}wards"
        )

    def _format_market_config(self) -> str:
        """Format market config."""
        market_config = self._market_config
        return (
            f"\nMarket Config:"
            f"\n  Flexible Support: {market_config.flexible_support}"
            f"\n  Flexible Resistance: {market_config.flexible_resistance}"
            f"\n  Static Support: {market_config.static_support}"
            f"\n  Static Resistance: {market_config.static_resistance}"
            f"\n  Phase: {market_config.movement_type}"
            f"\n  drifting price form {market_config.phase_start_price} to {market_config.phase_end_price}"
            f"\n  Current Boundaries Update Interval: {market_config.current_boundaries_update_interval}"
        )

    # =========================================================================
    # Executor Config Creation
    # =========================================================================

    def _create_executor_config(self, order_candidate, is_paywall: bool = False):
        """Create executor configuration for an order."""
        return OrderExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.exchange,
            trading_pair=self.config.trading_pair,
            price=order_candidate.price,
            amount=order_candidate.amount,
            side=order_candidate.order_side,
            execution_strategy=ExecutionStrategy.LIMIT,
            is_paywall_order=is_paywall,
        )

    def on_stop(self):
        """Called when strategy is stopped."""
        self.logger().info("Strategy stopped")


# =============================================================================
# Factory Function
# =============================================================================


def create_volume_pumper_controller(
    config: VolumePumperConfigBase,
    market_data_provider,
    actions_queue=None,
    *args,
    **kwargs,
) -> VolumePumperController:
    """
    Factory function to create a fully configured VolumePumperController.

    This function handles all dependency injection, creating all required
    adapters and services with proper configuration.

    Args:
        config: Strategy configuration
        market_data_provider: Market data provider from executor orchestrator
        actions_queue: Actions queue from executor orchestrator

    Returns:
        Fully configured VolumePumperController instance
    """
    # Get connector
    connector = market_data_provider.connectors[config.exchange]

    # Create SQL session
    client_config_map = HummingbotApplication.main_application().client_config_map
    sql_manager = SQLConnectionManager(
        client_config_map=client_config_map,
        connection_type=SQLConnectionType.TRADE_FILLS,
    )
    db_session = sql_manager.get_new_session()

    # Create adapters
    market_data = MarketDataAdapter(
        connector=connector,
        trading_pair=config.trading_pair,
    )
    order_adapter = OrderAdapter(
        connector=connector,
        trading_pair=config.trading_pair,
    )
    persistence = PersistenceAdapter(
        db_session=db_session,
        trading_pair=config.trading_pair,
        strategy_name=config.strategy_name,
    )

    # Create services
    volume_service = VolumeOrderService(
        market_data=market_data,
        order_adapter=order_adapter,
        order_lower_amount=config.order_lower_amount,
        order_upper_amount=config.order_upper_amount,
        minimum_spread_bps=config.minimum_ask_bid_spread,
    )

    boundary_service = BoundaryService(
        market_data=market_data,
        order_adapter=order_adapter,
        max_allowed_depth=config.max_allowed_depth,
        order_levels_steps=config.order_levels_steps,
    )

    architect_service = ArchitectService(
        market_data=market_data,
        persistence=persistence,
        static_support=config.static_support,
        static_resistance=config.static_resistance,
        minimum_phase_period=config.minimum_phase_period,
        maximum_phase_period=config.maximum_phase_period,
        minimum_phase_price_change_perc=config.minimum_phase_price_change_perc,
        maximum_phase_price_change_perc=config.maximum_phase_price_change_perc,
        minimum_flexible_wall_spread=config.minimum_flexible_wall_spread,
        maximum_flexible_wall_spread=config.maximum_flexible_wall_spread,
        minimum_boundaries_update_interval=config.minimum_boundaries_update_interval,
        maximum_boundaries_update_interval=config.maximum_boundaries_update_interval,
        order_levels_steps=config.order_levels_steps,
        architect_failover_delay=config.architect_failover_delay,
    )

    risk_service = RiskService(
        market_data=market_data,
        balance_loss_threshold=config.balance_loss_threshold,
        order_lower_amount=config.order_lower_amount,
    )

    report_service = ReportService(
        base=market_data.base,
        quote=market_data.quote,
        periodic_report_interval=config.periodic_report_interval,
    )

    # Initialize rate sources
    market_data_provider.initialize_rate_sources(
        [
            ConnectorPair(
                connector_name=config.exchange,
                trading_pair=config.trading_pair,
            )
        ]
    )

    # Create and return controller
    return VolumePumperController(
        config=config,
        volume_service=volume_service,
        boundary_service=boundary_service,
        architect_service=architect_service,
        risk_service=risk_service,
        report_service=report_service,
        market_data=market_data,
        order_adapter=order_adapter,
        persistence=persistence,
        market_data_provider=market_data_provider,
        actions_queue=actions_queue,
        *args,
        **kwargs,
    )
