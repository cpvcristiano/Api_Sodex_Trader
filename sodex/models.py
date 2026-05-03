from enum import IntEnum


class OrderSide(IntEnum):
    BUY = 1
    SELL = 2


class OrderType(IntEnum):
    LIMIT = 1
    MARKET = 2


class TimeInForce(IntEnum):
    GTC = 1   # Good Till Cancel
    FOK = 2   # Fill or Kill (unsupported)
    IOC = 3   # Immediate or Cancel
    GTX = 4   # Good Till Crossing (Post-Only)


class OrderStatus(IntEnum):
    NEW = 1
    PARTIALLY_FILLED = 2
    FILLED = 3
    CANCELED = 4
    REJECTED = 5
    EXPIRED = 6
    TRIGGERED = 10


class TransferAssetType(IntEnum):
    EVM_DEPOSIT = 0
    PERPS_DEPOSIT = 1
    EVM_WITHDRAW = 2
    PERPS_WITHDRAW = 3
    INTERNAL = 4
    SPOT_WITHDRAW = 5
    SPOT_DEPOSIT = 6


class MarginMode(IntEnum):
    ISOLATED = 1
    CROSS = 2


class PositionSide(IntEnum):
    BOTH = 1
    LONG = 2
    SHORT = 3


class OrderModifier(IntEnum):
    NORMAL = 1
    STOP = 2
    BRACKET = 3
    ATTACHED_STOP = 4


class StopType(IntEnum):
    STOP_LOSS = 1
    TAKE_PROFIT = 2


class TriggerType(IntEnum):
    LAST_PRICE = 1
    MARK_PRICE = 2
    INDEX_PRICE = 3
