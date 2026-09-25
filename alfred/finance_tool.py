import yfinance as yf
import pandas_ta as ta
from database import get_connection


def get_current_price(stock, hist=None):
    """currentPrice is missing for ETFs and indices, so fall back
    to regularMarketPrice, then to the last close in the history."""
    info = stock.info
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price:
        return float(price)
    if hist is None:
        hist = stock.history(period="5d")
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])


def get_ticker_info(ticker):
    try:

        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")
        if hist.empty:
            return f"No price data found for {ticker.upper()}. Is the symbol right? NZX stocks end in .NZ (e.g. FPH.NZ)."

        current_price = get_current_price(stock, hist)
        pe_ratio = info.get("trailingPE", "N/A")
        market_cap = info.get("marketCap")
        week_high = info.get("fiftyTwoWeekHigh", "N/A")
        week_low = info.get("fiftyTwoWeekLow", "N/A")
        currency = info.get("currency", "")

        close = hist["Close"]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]

        ma20_signal = "Above" if current_price > ma20 else "Below"
        ma50_signal = "Above" if current_price > ma50 else "Below"
        rsi = ta.rsi(close, length=14).iloc[-1]
        if rsi < 30:
            rsi_signal = "oversold"
        elif rsi > 70:
            rsi_signal = "overbought"
        else:
            rsi_signal = "neutral"

        return (
            f"{ticker.upper()} - ${current_price:.2f} {currency}\n"
            f"P/E: {pe_ratio} | Market Cap: {f'${market_cap:,}' if isinstance(market_cap, int) else 'N/A'}\n"
            f"52W High: ${week_high} | 52W Low: ${week_low}\n"
            f"20-day MA: ${ma20:.2f} (price is {ma20_signal})\n"
            f"50-day MA: ${ma50:.2f} (price is {ma50_signal})\n"
            f"14-day RSI: {rsi:.2f} ({rsi_signal})"
        )
    except Exception as e:
        return f"Error fetching data for {ticker}: {e}"

def add_to_portfolio(ticker, shares, avg_buy_price):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO portfolio (ticker, shares, avg_buy_price, date_added)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(ticker) DO UPDATE SET
                shares = excluded.shares,
                avg_buy_price = excluded.avg_buy_price
            """,
            (ticker.upper(), shares, avg_buy_price),
        )
        conn.commit()
        conn.close()
        return f"{ticker.upper()} added to portfolio - {shares} shares at ${avg_buy_price}"
    except Exception as e:
        return f"Error adding to portfolio: {e}"


def remove_from_portfolio(ticker):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker.upper(),))
        removed = cursor.rowcount
        conn.commit()
        conn.close()
        if removed == 0:
            return f"{ticker.upper()} isn't in your portfolio."
        return f"{ticker.upper()} removed from portfolio."
    except Exception as e:
        return f"Error removing from portfolio: {e}"

def get_portfolio_summary():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ticker, shares, avg_buy_price FROM portfolio")
        positions = cursor.fetchall()
        conn.close()

        if not positions:
            return "Your portfolio is empty."

        lines = []
        total_value = 0
        total_cost = 0

        for ticker, shares, avg_buy_price in positions:
            stock = yf.Ticker(ticker)
            current_price = get_current_price(stock)
            if current_price is None:
                lines.append(f"{ticker}: no price data available")
                continue
            position_value = current_price * shares
            position_cost = avg_buy_price * shares
            pnl = position_value - position_cost
            pnl_percent = (pnl / position_cost) * 100 if position_cost > 0 else 0

            total_value += position_value
            total_cost += position_cost

            lines.append(
                f"{ticker}: {shares} shares @ ${avg_buy_price} | "
                f"Now ${current_price:.2f} | "
                f"P&L: ${pnl:.2f} ({pnl_percent:+.1f}%)"
            )

        total_pnl = total_value - total_cost
        total_pnl_percent = (total_pnl / total_cost) * 100 if total_cost > 0 else 0
        lines.append(f"\nTotal Value: ${total_value:,.2f} | Total P&L: ${total_pnl:+.2f} ({total_pnl_percent:+.1f}%)")

        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching portfolio summary: {e}"

def add_to_watchlist(ticker, threshold_percent=5.0):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
              INSERT INTO watchlist (ticker, alert_threshold_percent, date_added)
              VALUES (?, ?, datetime('now'))
              ON CONFLICT(ticker) DO UPDATE SET
                  alert_threshold_percent = excluded.alert_threshold_percent
              """,
              (ticker.upper(), threshold_percent),
        )
        conn.commit()
        conn.close()
        return f"{ticker.upper()} added to watchlist — will alert if price moves {threshold_percent}% in a day"
    except Exception as e:
        return f"Error adding to watchlist: {e}"


def remove_from_watchlist(ticker):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper(),))
        removed = cursor.rowcount
        conn.commit()
        conn.close()
        if removed == 0:
            return f"{ticker.upper()} isn't on your watchlist."
        return f"{ticker.upper()} removed from watchlist."
    except Exception as e:
        return f"Error removing from watchlist: {e}"


def get_watchlist():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, alert_threshold_percent FROM watchlist ORDER BY ticker")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return "Your watchlist is empty."
    return "\n".join(f"{t} (alert at ±{p}%)" for t, p in rows)


def get_tracked_tickers():
    """Everything Alfred should scan: watchlist + portfolio, no duplicates."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM watchlist UNION SELECT ticker FROM portfolio")
    tickers = sorted(row[0] for row in cursor.fetchall())
    conn.close()
    return tickers


def check_watchlist():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ticker, alert_threshold_percent FROM watchlist")
        watchlist = cursor.fetchall()
        conn.close()

        if not watchlist:
            return None

        alerts = []

        for ticker, threshold_percent in watchlist:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d")

            if len(hist) < 2:
                continue

            previous_close = hist["Close"].iloc[-2]
            current_price = hist["Close"].iloc[-1]
            percent_change = ((current_price - previous_close) / previous_close) * 100

            if abs(percent_change) >= threshold_percent:
                direction = "up" if percent_change > 0 else "down"
                alerts.append(
                    f"{ticker}: {direction} {abs(percent_change):.1f}% "
                    f"(${previous_close:.2f} → ${current_price:.2f})"
                )

        return alerts if alerts else None

    except Exception as e:
        return [f"Error checking watchlist: {e}"]
