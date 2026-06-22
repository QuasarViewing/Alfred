import yfinance as yf
import pandas as pd
import pandas_ta as ta
from database import get_connection

def get_ticker_info(ticker):
    try:

        stock = yf.Ticker(ticker)
        info = stock.info

        current_price = info.get("currentPrice", "N/A")
        pe_ratio = info.get("trailingPE", "N/A")
        market_cap = info.get("marketCap", "N/A")
        week_high = info.get("fiftyTwoWeekHigh", "N/A")
        week_low = info.get("fiftyTwoWeekLow", "N/A")

        hist = stock.history(period="3mo")
        close = hist["Close"]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]

        ma20_signal = "Above" if current_price > ma20 else "Below"
        ma50_signal = "Above" if current_price > ma50 else "Below"
        rsi = ta.rsi(close, length=14).iloc[-1] if not close.empty else "N/A"
        if isinstance(rsi, float):
            if rsi < 30:
                rsi_signal = "oversold"
            elif rsi > 70:
                rsi_signal = "overbought"
            else:
                rsi_signal = "neutral"
        else:
            rsi_signal = "N/A"

        return (
            f"{ticker.upper()} - ${current_price}\n"
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
            current_price = stock.info.get("currentPrice", 0)
            position_value = current_price * shares
            position_cost = avg_buy_price * shares
            pnl = position_value - position_cost
            pnl_percent = (pnl / position_cost) * 100 if position_cost > 0 else 0
            
            total_value += position_value
            total_cost += position_cost

            lines.append(
                f"{ticker}: {shares} shares @ ${avg_buy_price} | "
                f"Now ${current_price} |"
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