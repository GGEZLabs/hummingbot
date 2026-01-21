"""Protocols layer - Interface definitions using Python Protocol classes."""

from hummingbot.strategy_v2.volume_pumper.protocols.interfaces import (
    IArchitectService,
    IBoundaryService,
    IMarketDataProvider,
    IOrderAdapter,
    IPersistenceAdapter,
    IReportService,
    IRiskService,
    IVolumeOrderService,
)

__all__ = [
    "IMarketDataProvider",
    "IOrderAdapter",
    "IPersistenceAdapter",
    "IVolumeOrderService",
    "IBoundaryService",
    "IArchitectService",
    "IRiskService",
    "IReportService",
]
