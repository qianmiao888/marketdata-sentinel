# Fixture provenance and distribution

`cex.csv` contains the first 60 one-minute ETHUSDT spot candles on 2025-01-01 UTC, extracted from Binance's public daily ZIP. Its official ZIP SHA256 was fetched and checked before extraction; URLs, archive checksum and slice are in `cex_provenance.json`, and the distributed slice checksum is in `cex_manifest.json`. Timestamps are microseconds under Binance's documented spot contract from 2025-01-01. No market-cause labels are supplied. Public data is distributed for a small reproducible demonstration; upstream terms apply: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md .

`dex.json` is entirely synthetic and authored for this project; it is freely redistributable under the repository license. It uses the configured Ethereum mainnet USDC/WETH 0.3% Uniswap v3 pool, chain ID 1, token0 USDC (6 decimals), token1 WETH (18 decimals). Block numbers are a fixed historical range, but event values, timestamps, transaction hashes and block hashes are artificial. It MUST NOT be represented as actual historical swaps. Connected collection verifies metadata and block hashes over the user's configured RPC before accepting real events.

Official schema references:
- https://github.com/binance/binance-public-data
- https://developers.uniswap.org/docs/sdks/v3/guides/pool-data
- https://github.com/Uniswap/v3-core/blob/main/contracts/interfaces/pool/IUniswapV3PoolEvents.sol
- https://ethereum.org/developers/docs/apis/json-rpc/
