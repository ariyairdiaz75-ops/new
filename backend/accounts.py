from backend.binance_client import BinanceFuturesClient
from backend.config import settings

main_client = BinanceFuturesClient(
    label=settings.main_label,
    api_key=settings.main_api_key,
    api_secret=settings.main_api_secret,
    testnet=settings.binance_testnet,
)

sub_client = BinanceFuturesClient(
    label=settings.sub_label,
    api_key=settings.sub_api_key,
    api_secret=settings.sub_api_secret,
    testnet=settings.binance_testnet,
)

ACCOUNTS = {"main": main_client, "sub": sub_client}


async def close_all():
    await main_client.aclose()
    await sub_client.aclose()
