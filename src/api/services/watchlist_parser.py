"""
Watchlist parser - Extract symbols from TradingView watchlist URLs.
"""
import re
import httpx
from typing import Optional
from bs4 import BeautifulSoup


async def parse_tradingview_watchlist_url(url: str) -> dict:
    """
    Parse a TradingView public watchlist URL and extract symbols.
    
    Example URL: https://www.tradingview.com/watchlists/195100384/
    
    Returns:
        {
            "name": "Watchlist Name",
            "symbols": [
                {"symbol": "BTCUSDT.P", "exchange": "BYBIT", "full_symbol": "BYBIT:BTCUSDT.P", "category": "crypto"},
                ...
            ]
        }
    """
    # Validate URL format
    if not re.match(r'https?://(?:www\.)?tradingview\.com/watchlists/\d+/?', url):
        raise ValueError("Invalid TradingView watchlist URL")
    
    # Fetch the page
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try to get watchlist name
    name = "TradingView Watchlist"
    title_elem = soup.find('h1') or soup.find('title')
    if title_elem:
        name = title_elem.get_text().strip()
        # Clean up "XYZ - TradingView" format
        if " - TradingView" in name:
            name = name.split(" - TradingView")[0].strip()
    
    symbols = []
    
    # Extract symbols from links
    # TradingView watchlist pages have links like /symbols/BYBIT-BTCUSDT.P/
    symbol_links = soup.find_all('a', href=re.compile(r'/symbols/[A-Z0-9_-]+/'))
    
    seen = set()
    for link in symbol_links:
        href = link.get('href', '')
        match = re.search(r'/symbols/([A-Z0-9_-]+)/?', href)
        if match:
            raw_symbol = match.group(1)
            
            # Skip duplicates
            if raw_symbol in seen:
                continue
            seen.add(raw_symbol)
            
            # Parse exchange and symbol from different formats:
            # - BYBIT-BTCUSDT.P -> exchange=BYBIT, symbol=BTCUSDT.P
            # - NASDAQ-AAPL -> exchange=NASDAQ, symbol=AAPL
            # - BTCUSD -> exchange="", symbol=BTCUSD
            
            if '-' in raw_symbol:
                parts = raw_symbol.split('-', 1)
                exchange = parts[0]
                symbol = parts[1]
            else:
                exchange = ""
                symbol = raw_symbol
            
            # Determine category
            category = categorize_symbol(symbol, exchange)
            
            full_symbol = f"{exchange}:{symbol}" if exchange else symbol
            
            symbols.append({
                "symbol": symbol,
                "exchange": exchange,
                "full_symbol": full_symbol,
                "category": category
            })
    
    # Fallback: try to find symbols in data attributes or script tags
    if not symbols:
        symbols = extract_symbols_from_scripts(html)
    
    return {
        "name": name,
        "symbols": symbols
    }


def categorize_symbol(symbol: str, exchange: str) -> str:
    """Categorize a symbol based on naming patterns and exchange."""
    symbol_upper = symbol.upper()
    exchange_upper = exchange.upper()
    
    # Crypto exchanges
    crypto_exchanges = {'BYBIT', 'BINANCE', 'COINBASE', 'KRAKEN', 'BITSTAMP', 'BITFINEX', 'KUCOIN', 'OKX', 'MEXC'}
    if exchange_upper in crypto_exchanges:
        return "crypto"
    
    # Crypto patterns
    if any(symbol_upper.endswith(x) for x in ['USDT', 'USDC', 'USD', 'BTC', 'ETH', 'BUSD']):
        return "crypto"
    if symbol_upper.endswith('.P'):  # Perpetuals
        return "crypto"
    
    # Indices
    index_keywords = ['INDEX', 'US100', 'US500', 'US30', 'NAS100', 'SPX', 'NDX', 'DJI', 'HK50', 'GER30', 'UK100', 'JP225']
    if any(kw in symbol_upper for kw in index_keywords):
        return "index"
    
    # Commodities
    commodities = ['GOLD', 'SILVER', 'PLATINUM', 'PALLADIUM', 'COPPER', 'WTI', 'BRENT', 'NATGAS', 'XAUUSD', 'XAGUSD']
    if any(comm in symbol_upper for comm in commodities):
        return "commodity"
    
    # Forex
    forex_pairs = ['EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
    if len(symbol_upper) == 6 and any(pair in symbol_upper for pair in forex_pairs):
        return "forex"
    
    # Stock exchanges
    stock_exchanges = {'NYSE', 'NASDAQ', 'AMEX', 'LSE', 'TSE', 'HKEX', 'SSE', 'NSE', 'BSE'}
    if exchange_upper in stock_exchanges:
        return "stock"
    
    # Default to stock for short symbols
    if len(symbol) <= 5 and symbol.isalpha():
        return "stock"
    
    return "other"


def extract_symbols_from_scripts(html: str) -> list:
    """Fallback: Extract symbols from inline JSON or script data."""
    symbols = []
    
    # Look for symbol arrays in scripts
    # Pattern: "symbol":"EXCHANGE:TICKER" or similar
    pattern = r'"symbol"\s*:\s*"([A-Z0-9_]+:[A-Z0-9_.]+)"'
    matches = re.findall(pattern, html, re.IGNORECASE)
    
    seen = set()
    for full_symbol in matches:
        if full_symbol in seen:
            continue
        seen.add(full_symbol)
        
        if ':' in full_symbol:
            exchange, symbol = full_symbol.split(':', 1)
        else:
            exchange = ""
            symbol = full_symbol
        
        category = categorize_symbol(symbol, exchange)
        
        symbols.append({
            "symbol": symbol,
            "exchange": exchange,
            "full_symbol": full_symbol,
            "category": category
        })
    
    return symbols
