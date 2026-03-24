"""
TradingView Browser Controller
==============================
Playwright-based browser automation for TradingView chart and Pine Editor interaction.
Features robust selector fallbacks and exponential backoff waits.
"""

import asyncio
import time
import os
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from playwright.async_api import async_playwright, Browser, Page, BrowserContext


logger = logging.getLogger(__name__)


class SelectorStrategy(Enum):
    """Selector matching strategies."""
    CSS = "css"
    XPATH = "xpath"
    TEXT = "text"
    ROLE = "role"


@dataclass
class SelectorChain:
    """A chain of fallback selectors for a single element."""
    name: str
    selectors: List[Tuple[SelectorStrategy, str]]
    description: str = ""
    
    def __iter__(self):
        return iter(self.selectors)


class SelectorRegistry:
    """
    Registry of all TradingView selectors with fallback chains.
    When TradingView updates their UI, update selectors here.
    """
    
    # Pine Editor selectors
    PINE_EDITOR_TAB = SelectorChain(
        name="pine_editor_tab",
        description="Pine Editor tab at bottom of chart",
        selectors=[
            (SelectorStrategy.CSS, '[data-name="pine-editor"]'),
            (SelectorStrategy.CSS, 'button[aria-label*="Pine"]'),
            (SelectorStrategy.XPATH, '//button[contains(text(), "Pine Editor")]'),
            (SelectorStrategy.TEXT, "Pine Editor"),
        ]
    )
    
    PINE_EDITOR_CONTENT = SelectorChain(
        name="pine_editor_content",
        description="Pine Editor code input area",
        selectors=[
            (SelectorStrategy.CSS, '.pine-editor-content textarea'),
            (SelectorStrategy.CSS, '[class*="monaco-editor"]'),
            (SelectorStrategy.CSS, '.view-lines'),
            (SelectorStrategy.XPATH, '//div[contains(@class, "editor")]//textarea'),
        ]
    )
    
    COMPILE_BUTTON = SelectorChain(
        name="compile_button",
        description="Add to chart / Compile button",
        selectors=[
            (SelectorStrategy.CSS, '[data-name="add-script-to-chart"]'),
            (SelectorStrategy.CSS, 'button[aria-label*="Add to chart"]'),
            (SelectorStrategy.TEXT, "Add to chart"),
            (SelectorStrategy.XPATH, '//button[contains(text(), "Add to chart")]'),
        ]
    )
    
    # Strategy Tester selectors
    STRATEGY_TESTER_TAB = SelectorChain(
        name="strategy_tester_tab",
        description="Strategy Tester tab",
        selectors=[
            (SelectorStrategy.CSS, '[data-name="backtesting"]'),
            (SelectorStrategy.CSS, 'button[aria-label*="Strategy Tester"]'),
            (SelectorStrategy.TEXT, "Strategy Tester"),
            (SelectorStrategy.XPATH, '//button[contains(text(), "Strategy Tester")]'),
        ]
    )
    
    OVERVIEW_TAB = SelectorChain(
        name="overview_tab",
        description="Overview tab in Strategy Tester",
        selectors=[
            (SelectorStrategy.CSS, '[data-name="performance-summary"]'),
            (SelectorStrategy.TEXT, "Overview"),
            (SelectorStrategy.XPATH, '//button[text()="Overview"]'),
        ]
    )
    
    PERFORMANCE_SUMMARY = SelectorChain(
        name="performance_summary",
        description="Performance summary panel",
        selectors=[
            (SelectorStrategy.CSS, '[data-name="performance-summary-content"]'),
            (SelectorStrategy.CSS, '.backtesting-content-wrapper'),
            (SelectorStrategy.CSS, '[class*="strategyReport"]'),
            (SelectorStrategy.XPATH, '//div[contains(@class, "report")]'),
        ]
    )
    
    # Symbol search selectors
    SYMBOL_SEARCH_BUTTON = SelectorChain(
        name="symbol_search_button",
        description="Symbol search button in header",
        selectors=[
            (SelectorStrategy.CSS, '[data-name="symbol-search"]'),
            (SelectorStrategy.CSS, '[aria-label*="Symbol Search"]'),
            (SelectorStrategy.CSS, '.chart-controls-bar button:first-child'),
        ]
    )
    
    SYMBOL_SEARCH_INPUT = SelectorChain(
        name="symbol_search_input",
        description="Symbol search input field",
        selectors=[
            (SelectorStrategy.CSS, '[data-name="symbol-search-input"] input'),
            (SelectorStrategy.CSS, 'input[data-role="search"]'),
            (SelectorStrategy.CSS, '.symbol-search-input input'),
            (SelectorStrategy.XPATH, '//input[@placeholder="Search"]'),
        ]
    )
    
    # Error indicators
    PINE_ERROR = SelectorChain(
        name="pine_error",
        description="Pine Script compilation error",
        selectors=[
            (SelectorStrategy.CSS, '[class*="error"]'),
            (SelectorStrategy.CSS, '.pine-editor-error'),
            (SelectorStrategy.XPATH, '//div[contains(@class, "error")]'),
        ]
    )


class BrowserController:
    """
    Controls TradingView browser interactions.
    Handles page navigation, Pine Editor, and Strategy Tester.
    """
    
    def __init__(self, headless: bool = False, timeout: int = 60000):
        self.headless = headless
        self.timeout = timeout
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._selectors = SelectorRegistry()
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self) -> None:
        """Start the browser."""
        self.playwright = await async_playwright().start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout)
        
        logger.info("Browser started successfully")
    
    async def close(self) -> None:
        """Close the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed")
    
    async def navigate_to_chart(self, symbol: str = "BYBIT:BTCUSDT.P", 
                                 timeframe: str = "15") -> bool:
        """Navigate to TradingView chart for given symbol."""
        
        # Build chart URL
        exchange, ticker = self._parse_symbol(symbol)
        url = f"https://www.tradingview.com/chart/?symbol={exchange}:{ticker}&interval={timeframe}"
        
        logger.info(f"Navigating to {url}")
        
        try:
            await self.page.goto(url, wait_until='networkidle')
            await asyncio.sleep(3)  # Allow chart to fully load
            
            # Close any popups
            await self._close_popups()
            
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
    
    async def change_symbol(self, symbol: str) -> bool:
        """Change the current chart symbol."""
        
        try:
            # Click symbol search
            search_btn = await self._find_element(self._selectors.SYMBOL_SEARCH_BUTTON)
            if search_btn:
                await search_btn.click()
                await asyncio.sleep(0.5)
            
            # Type symbol
            search_input = await self._find_element(self._selectors.SYMBOL_SEARCH_INPUT)
            if search_input:
                await search_input.fill(symbol)
                await asyncio.sleep(1)
                await search_input.press('Enter')
                await asyncio.sleep(2)
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to change symbol: {e}")
            return False
    
    async def open_pine_editor(self) -> bool:
        """Open the Pine Editor panel."""
        
        try:
            editor_tab = await self._find_element(self._selectors.PINE_EDITOR_TAB)
            if editor_tab:
                await editor_tab.click()
                await asyncio.sleep(1)
                return True
            
            # Try keyboard shortcut
            await self.page.keyboard.press('Control+.')
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Failed to open Pine Editor: {e}")
            return False
    
    async def paste_pine_script(self, script: str) -> bool:
        """
        Paste Pine Script into the editor.
        Uses clipboard method for reliability.
        """
        
        try:
            # Open Pine Editor
            await self.open_pine_editor()
            await asyncio.sleep(1)
            
            # Find editor content area
            editor = await self._find_element(self._selectors.PINE_EDITOR_CONTENT)
            if not editor:
                # Try clicking in the editor area first
                await self.page.click('.pine-editor', timeout=5000)
                await asyncio.sleep(0.5)
            
            # Select all existing content
            await self.page.keyboard.press('Control+a')
            await asyncio.sleep(0.2)
            
            # Use clipboard to paste
            await self.page.evaluate(f'navigator.clipboard.writeText({repr(script)})')
            await self.page.keyboard.press('Control+v')
            await asyncio.sleep(1)
            
            logger.info("Pine Script pasted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to paste Pine Script: {e}")
            
            # Fallback: Try typing directly (slow but reliable)
            try:
                await self.page.keyboard.type(script, delay=10)
                return True
            except:
                return False
    
    async def compile_script(self) -> Tuple[bool, Optional[str]]:
        """
        Compile the Pine Script (Add to chart).
        Returns (success, error_message).
        """
        
        try:
            # Find and click compile button
            compile_btn = await self._find_element(self._selectors.COMPILE_BUTTON)
            if compile_btn:
                await compile_btn.click()
                await asyncio.sleep(3)  # Wait for compilation
            else:
                # Try keyboard shortcut
                await self.page.keyboard.press('Control+Enter')
                await asyncio.sleep(3)
            
            # Check for errors
            error_el = await self._find_element(self._selectors.PINE_ERROR, timeout=2000)
            if error_el:
                error_text = await error_el.text_content()
                logger.error(f"Compilation error: {error_text}")
                return False, error_text
            
            logger.info("Script compiled successfully")
            return True, None
            
        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            return False, str(e)
    
    async def open_strategy_tester(self) -> bool:
        """Open the Strategy Tester panel."""
        
        try:
            tester_tab = await self._find_element(self._selectors.STRATEGY_TESTER_TAB)
            if tester_tab:
                await tester_tab.click()
                await asyncio.sleep(1)
                return True
            
            # Try keyboard shortcut
            await self.page.keyboard.press('Control+.')
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Failed to open Strategy Tester: {e}")
            return False
    
    async def get_backtest_metrics(self) -> Dict[str, Any]:
        """
        Extract backtest metrics from Strategy Tester.
        Returns dictionary of metrics.
        """
        
        # Open Strategy Tester
        await self.open_strategy_tester()
        await asyncio.sleep(2)
        
        # Click Overview tab
        overview_tab = await self._find_element(self._selectors.OVERVIEW_TAB)
        if overview_tab:
            await overview_tab.click()
            await asyncio.sleep(1)
        
        # Wait for metrics to load
        await self._wait_for_metrics()
        
        # Extract metrics using multiple methods
        metrics = {}
        
        # Method 1: Try structured selectors
        metrics = await self._extract_metrics_structured()
        
        # Method 2: Fallback to page content parsing
        if not metrics:
            metrics = await self._extract_metrics_regex()
        
        logger.info(f"Extracted metrics: {metrics}")
        return metrics
    
    async def take_screenshot(self, path: str) -> bool:
        """Take a screenshot of the current page."""
        try:
            await self.page.screenshot(path=path, full_page=False)
            logger.info(f"Screenshot saved: {path}")
            return True
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False
    
    # ============== Private Methods ==============
    
    async def _find_element(self, selector_chain: SelectorChain, 
                            timeout: int = 5000):
        """
        Find element using fallback selector chain.
        Returns first matching element or None.
        """
        
        for strategy, selector in selector_chain:
            try:
                if strategy == SelectorStrategy.CSS:
                    el = await self.page.wait_for_selector(selector, timeout=timeout)
                elif strategy == SelectorStrategy.XPATH:
                    el = await self.page.wait_for_selector(f'xpath={selector}', timeout=timeout)
                elif strategy == SelectorStrategy.TEXT:
                    el = await self.page.get_by_text(selector).first.element_handle()
                elif strategy == SelectorStrategy.ROLE:
                    el = await self.page.get_by_role(selector).first.element_handle()
                
                if el:
                    logger.debug(f"Found {selector_chain.name} using {strategy.value}: {selector}")
                    return el
            except:
                continue
        
        logger.warning(f"Could not find element: {selector_chain.name}")
        return None
    
    async def _close_popups(self) -> None:
        """Close any modal popups."""
        
        popup_selectors = [
            '[class*="close-button"]',
            '[aria-label="Close"]',
            'button:has-text("No thanks")',
            'button:has-text("Maybe later")',
            '[class*="dialog"] button:first-child',
        ]
        
        for selector in popup_selectors:
            try:
                el = await self.page.wait_for_selector(selector, timeout=1000)
                if el:
                    await el.click()
                    await asyncio.sleep(0.5)
            except:
                pass
    
    async def _wait_for_metrics(self, max_wait: int = 30) -> bool:
        """Wait for backtest metrics to be calculated."""
        
        start = time.time()
        
        while time.time() - start < max_wait:
            # Check for loading indicator
            try:
                loading = await self.page.wait_for_selector(
                    '[class*="loading"]', timeout=1000
                )
                if loading:
                    await asyncio.sleep(1)
                    continue
            except:
                pass
            
            # Check for metrics content
            try:
                content = await self.page.text_content('[class*="report"]')
                if content and 'Net Profit' in content:
                    return True
            except:
                pass
            
            await asyncio.sleep(1)
        
        return False
    
    async def _extract_metrics_structured(self) -> Dict[str, Any]:
        """Extract metrics using structured DOM queries."""
        
        metrics = {}
        
        # Metric patterns to look for
        metric_patterns = {
            'net_profit': ['Net Profit', 'Net P/L'],
            'total_trades': ['Total Closed Trades', 'Total Trades'],
            'win_rate': ['Percent Profitable', 'Win Rate', 'Win %'],
            'profit_factor': ['Profit Factor'],
            'max_drawdown': ['Max Drawdown', 'Maximum Drawdown'],
            'sharpe_ratio': ['Sharpe Ratio'],
            'avg_trade': ['Avg Trade', 'Average Trade'],
        }
        
        try:
            # Get all text content from strategy tester
            content = await self.page.text_content('[class*="strategyReport"]')
            if not content:
                content = await self.page.text_content('.backtesting-content-wrapper')
            
            if content:
                metrics = self._parse_metrics_text(content, metric_patterns)
        except Exception as e:
            logger.debug(f"Structured extraction failed: {e}")
        
        return metrics
    
    async def _extract_metrics_regex(self) -> Dict[str, Any]:
        """Extract metrics using regex on page content."""
        
        import re
        
        metrics = {}
        
        try:
            # Get full page text
            content = await self.page.content()
            
            # Regex patterns
            patterns = {
                'net_profit': r'Net (?:Profit|P/L)[:\s]+([−-]?\$?[\d,]+\.?\d*%?)',
                'total_trades': r'Total (?:Closed )?Trades[:\s]+(\d+)',
                'win_rate': r'(?:Percent Profitable|Win Rate|Win %)[:\s]+([\d.]+)%?',
                'profit_factor': r'Profit Factor[:\s]+([\d.]+)',
                'max_drawdown': r'Max(?:imum)? Drawdown[:\s]+([−-]?\$?[\d,]+\.?\d*%?)',
                'sharpe_ratio': r'Sharpe Ratio[:\s]+([−-]?[\d.]+)',
            }
            
            for key, pattern in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    metrics[key] = match.group(1).strip()
        
        except Exception as e:
            logger.debug(f"Regex extraction failed: {e}")
        
        return metrics
    
    def _parse_metrics_text(self, text: str, patterns: Dict) -> Dict[str, Any]:
        """Parse metrics from text content."""
        
        import re
        
        metrics = {}
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            for key, names in patterns.items():
                for name in names:
                    if name.lower() in line.lower():
                        # Try to get value from same line or next line
                        value_match = re.search(r'([−-]?\$?[\d,]+\.?\d*%?)', line)
                        if not value_match and i + 1 < len(lines):
                            value_match = re.search(r'([−-]?\$?[\d,]+\.?\d*%?)', lines[i+1])
                        
                        if value_match:
                            metrics[key] = value_match.group(1).strip()
                        break
        
        return metrics
    
    def _parse_symbol(self, symbol: str) -> Tuple[str, str]:
        """Parse symbol into exchange and ticker."""
        
        if ':' in symbol:
            parts = symbol.split(':')
            return parts[0], parts[1]
        return 'BYBIT', symbol


async def run_backtest(script: str, symbol: str, timeframe: str = "15",
                       headless: bool = False) -> Dict[str, Any]:
    """
    Convenience function to run a complete backtest.
    Returns metrics dictionary.
    """
    
    async with BrowserController(headless=headless) as browser:
        # Navigate to chart
        await browser.navigate_to_chart(symbol, timeframe)
        
        # Paste and compile script
        await browser.paste_pine_script(script)
        success, error = await browser.compile_script()
        
        if not success:
            return {"error": error, "success": False}
        
        # Get metrics
        metrics = await browser.get_backtest_metrics()
        metrics["success"] = True
        metrics["symbol"] = symbol
        metrics["timeframe"] = timeframe
        
        return metrics


if __name__ == "__main__":
    import asyncio
    
    # Test basic functionality
    async def test():
        async with BrowserController(headless=False) as browser:
            await browser.navigate_to_chart("BYBIT:BTCUSDT.P", "15")
            await asyncio.sleep(5)
            print("Navigation test complete")
    
    asyncio.run(test())
