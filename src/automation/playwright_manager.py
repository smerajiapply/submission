"""Playwright browser manager with async support"""

import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, ElementHandle
from src.config.base_config import settings
from src.utils.logger import log
from src.utils.storage import storage


class PlaywrightManager:
    """Manages Playwright browser instance and interactions"""
    
    def __init__(self, headless: bool = None):
        self.headless = headless if headless is not None else settings.headless
        self.timeout = settings.browser_timeout
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._action_count = 0
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def start(self):
        """Initialize browser and create context"""
        log.info("Starting Playwright browser...")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--start-maximized']
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Set default timeout
        self.context.set_default_timeout(self.timeout)
        
        self.page = await self.context.new_page()
        
        log.info(f"Browser started (headless={self.headless})")
    
    async def close(self):
        """Close browser and cleanup"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        log.info("Browser closed")
    
    async def navigate(self, url: str) -> bool:
        """Navigate to a URL"""
        try:
            log.info(f"Navigating to: {url}")
            response = await self.page.goto(url, wait_until='networkidle')
            await self.capture_screenshot("after_navigate")
            return response.ok
        except Exception as e:
            log.error(f"Navigation failed: {e}")
            return False
    
    async def capture_screenshot(self, prefix: str = "screenshot") -> Path:
        """Capture and save screenshot"""
        try:
            self._action_count += 1
            screenshot_bytes = await self.page.screenshot(full_page=False)
            screenshot_path = storage.save_screenshot(
                screenshot_bytes,
                prefix=f"{prefix}_{self._action_count:03d}"
            )
            return screenshot_path
        except Exception as e:
            log.error(f"Screenshot failed: {e}")
            return None
    
    async def get_page_content(self) -> str:
        """Get current page HTML content"""
        try:
            return await self.page.content()
        except Exception as e:
            log.error(f"Failed to get page content: {e}")
            return ""
    
    async def get_page_text(self) -> str:
        """Get visible text from the page"""
        try:
            return await self.page.inner_text('body')
        except Exception as e:
            log.error(f"Failed to get page text: {e}")
            return ""
    
    async def click_element(
        self,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        timeout: Optional[int] = None,
        force: bool = False
    ) -> bool:
        """Click an element by selector or text"""
        try:
            timeout_ms = timeout * 1000 if timeout else self.timeout
            
            if selector:
                log.info(f"Clicking element: {selector}{' (force)' if force else ''}")
                await self.page.click(selector, timeout=timeout_ms, force=force)
            elif text:
                log.info(f"Clicking element with text: {text}{' (force)' if force else ''}")
                await self.page.click(f"text={text}", timeout=timeout_ms, force=force)
            else:
                log.error("No selector or text provided for click")
                return False
            
            await self.page.wait_for_load_state('networkidle', timeout=timeout_ms)
            await self.capture_screenshot("after_click")
            return True
            
        except Exception as e:
            log.error(f"Click failed: {e}")
            await self.capture_screenshot("click_failed")
            return False
    
    async def type_text(
        self,
        selector: str,
        text: str,
        clear: bool = True,
        delay: int = 50
    ) -> bool:
        """Type text into an input field"""
        try:
            log.info(f"Typing into: {selector}")
            
            if clear:
                await self.page.fill(selector, "")
            
            await self.page.type(selector, text, delay=delay)
            await self.capture_screenshot("after_type")
            return True
            
        except Exception as e:
            log.error(f"Type failed: {e}")
            return False
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: str = "visible"
    ) -> bool:
        """Wait for an element to appear"""
        try:
            timeout_ms = timeout * 1000 if timeout else self.timeout
            await self.page.wait_for_selector(selector, timeout=timeout_ms, state=state)
            log.info(f"Element found: {selector}")
            return True
        except Exception as e:
            log.warning(f"Wait for selector failed: {e}")
            return False
    
    async def find_elements_by_text(self, text: str) -> List[ElementHandle]:
        """Find elements containing specific text"""
        try:
            elements = await self.page.query_selector_all(f"text={text}")
            return elements
        except Exception as e:
            log.error(f"Find by text failed: {e}")
            return []
    
    async def scroll_to_bottom(self):
        """Scroll to the bottom of the page"""
        try:
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            await self.capture_screenshot("after_scroll")
        except Exception as e:
            log.error(f"Scroll failed: {e}")
    
    async def go_back(self):
        """Navigate back in browser history"""
        try:
            await self.page.go_back(wait_until='networkidle')
            await self.capture_screenshot("after_back")
        except Exception as e:
            log.error(f"Go back failed: {e}")
    
    async def download_file(self, trigger_selector: Optional[str] = None) -> Optional[Path]:
        """Download a file by clicking a download button"""
        try:
            async with self.page.expect_download() as download_info:
                if trigger_selector:
                    await self.page.click(trigger_selector)
                else:
                    log.warning("No trigger selector provided for download")
                    return None
            
            download = await download_info.value
            
            # Save to temporary location first
            temp_path = Path(f"/tmp/{download.suggested_filename}")
            await download.save_as(temp_path)
            
            log.info(f"File downloaded: {download.suggested_filename}")
            return temp_path
            
        except Exception as e:
            log.error(f"Download failed: {e}")
            return None
    
    async def get_element_screenshot(self, selector: str) -> Optional[bytes]:
        """Capture screenshot of a specific element"""
        try:
            element = await self.page.query_selector(selector)
            if element:
                return await element.screenshot()
            return None
        except Exception as e:
            log.error(f"Element screenshot failed: {e}")
            return None
    
    async def evaluate_js(self, script: str) -> Any:
        """Execute JavaScript in the page context"""
        try:
            return await self.page.evaluate(script)
        except Exception as e:
            log.error(f"JavaScript evaluation failed: {e}")
            return None
    
    async def get_current_url(self) -> str:
        """Get the current page URL"""
        return self.page.url
    
    async def wait(self, seconds: float):
        """Wait for a specified number of seconds"""
        await asyncio.sleep(seconds)
        log.debug(f"Waited for {seconds} seconds")


