import requests
import pandas as pd

# Stablecoins y patrones a excluir
STABLE_PATTERNS = {
    "USDT", "USDC", "BUSD", "TUSD", "DAI", "FDUSD", "PYUSD",
    "EUR", "TRY", "BRL", "GBP", "HUSDT", "BUSDT", "MUSDT",
    "XUSDT", "SUSDT", "FUSDT", "NUSDT", "AUSDT", "EUSDT"
}

MEME_KEYWORDS = ['PEPE', 'BONK', 'FART', 'PUMP', 'SHIB', 'DOGE', 'TRUMP']

def es_stablecoin_base(base: str) -> bool:
    base = base.upper()
    return base in STABLE_PATTERNS or (base.endswith("USDT") and len(base) <= 6)

def no_es_meme(pair: str) -> bool:
    return not any(meme in pair.upper() for meme in MEME_KEYWORDS)

def obtener_top_100_futures_usdt_filtrado(min_volume_usdt=2e8, min_spread=0.01):
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    response = requests.get(url)
    data = response.json()

    registros = []

    for item in data:
        symbol = item['symbol']
        if symbol.endswith("USDT"):
            base = symbol[:-4]
            if not es_stablecoin_base(base) and no_es_meme(base):
                volume_usdt = float(item['quoteVolume'])
                base_volume = float(item['volume'])
                if base_volume > 0:
                    spread = volume_usdt / base_volume
                    registros.append({
                        "pair": symbol,
                        "volume_usdt": volume_usdt,
                        "base_volume": base_volume,
                        "spread": spread
                    })

    df = pd.DataFrame(registros)
    df_filtrado = df[
        (df['volume_usdt'] >= min_volume_usdt) &
        (df['spread'] > min_spread)
    ].sort_values(by='volume_usdt', ascending=False).head(100).reset_index(drop=True)

    return df_filtrado

if __name__ == "__main__":
    top_100 = obtener_top_100_futures_usdt_filtrado()
    print(top_100.to_string(index=False))
