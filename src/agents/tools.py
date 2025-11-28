"""LangChain custom tools for browser automation"""

from typing import Optional, Type, Any
from langchain.tools import BaseTool
from langchain.pydantic_v1 import BaseModel, Field
from src.automation.playwright_manager import PlaywrightManager
from src.utils.logger import log


# Tool input schemas
class NavigateInput(BaseModel):
    """Input for navigate tool"""
    url: str = Field(description="The URL to navigate to")


class ClickInput(BaseModel):
    """Input for click tool"""
    selector: Optional[str] = Field(None, description="CSS selector of element to click")
    text: Optional[str] = Field(None, description="Text content of element to click")


class TypeInput(BaseModel):
    """Input for type tool"""
    selector: str = Field(description="CSS selector of input field")
    text: str = Field(description="Text to type into the field")
    clear: bool = Field(True, description="Clear field before typing")


class WaitInput(BaseModel):
    """Input for wait tool"""
    seconds: float = Field(description="Number of seconds to wait")


class ScrollInput(BaseModel):
    """Input for scroll tool"""
    direction: str = Field("down", description="Direction to scroll: 'down' or 'up'")


class ScreenshotInput(BaseModel):
    """Input for screenshot tool"""
    prefix: str = Field("screenshot", description="Prefix for screenshot filename")


class GetTextInput(BaseModel):
    """Input for get text tool"""
    full_page: bool = Field(True, description="Get full page text or just visible")


# Custom tools
class NavigateTool(BaseTool):
    """Tool to navigate to a URL"""
    name: str = "navigate"
    description: str = "Navigate to a specific URL in the browser"
    args_schema: Type[BaseModel] = NavigateInput
    browser: PlaywrightManager = Field(exclude=True)
    
    def _run(self, url: str) -> str:
        """Not implemented for async tool"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, url: str) -> str:
        """Navigate to URL"""
        success = await self.browser.navigate(url)
        if success:
            return f"Successfully navigated to {url}"
        return f"Failed to navigate to {url}"


class ClickTool(BaseTool):
    """Tool to click an element"""
    name: str = "click"
    description: str = "Click an element on the page by CSS selector or visible text. Provide either selector OR text, not both."
    args_schema: Type[BaseModel] = ClickInput
    browser: PlaywrightManager = Field(exclude=True)
    
    def _run(self, selector: Optional[str] = None, text: Optional[str] = None) -> str:
        """Not implemented for async tool"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, selector: Optional[str] = None, text: Optional[str] = None) -> str:
        """Click element"""
        if not selector and not text:
            return "Error: Must provide either selector or text"
        
        success = await self.browser.click_element(selector=selector, text=text)
        if success:
            target = selector or f"text='{text}'"
            return f"Successfully clicked element: {target}"
        return f"Failed to click element"


class TypeTool(BaseTool):
    """Tool to type text into an input field"""
    name: str = "type"
    description: str = "Type text into an input field specified by CSS selector"
    args_schema: Type[BaseModel] = TypeInput
    browser: PlaywrightManager = Field(exclude=True)
    
    def _run(self, selector: str, text: str, clear: bool = True) -> str:
        """Not implemented for async tool"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, selector: str, text: str, clear: bool = True) -> str:
        """Type text into field"""
        success = await self.browser.type_text(selector, text, clear=clear)
        if success:
            return f"Successfully typed text into {selector}"
        return f"Failed to type into {selector}"


class WaitTool(BaseTool):
    """Tool to wait for a specified time"""
    name: str = "wait"
    description: str = "Wait for a specified number of seconds. Use this after actions that may take time to load."
    args_schema: Type[BaseModel] = WaitInput
    browser: PlaywrightManager = Field(exclude=True)
    
    def _run(self, seconds: float) -> str:
        """Not implemented for async tool"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, seconds: float) -> str:
        """Wait for seconds"""
        await self.browser.wait(seconds)
        return f"Waited for {seconds} seconds"


class ScrollTool(BaseTool):
    """Tool to scroll the page"""
    name: str = "scroll"
    description: str = "Scroll the page down to load more content or see elements below the fold"
    args_schema: Type[BaseModel] = ScrollInput
    browser: PlaywrightManager = Field(exclude=True)
    
    def _run(self, direction: str = "down") -> str:
        """Not implemented for async tool"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, direction: str = "down") -> str:
        """Scroll page"""
        if direction == "down":
            await self.browser.scroll_to_bottom()
            return "Scrolled to bottom of page"
        return "Scroll direction not implemented"


class ScreenshotTool(BaseTool):
    """Tool to take a screenshot"""
    name: str = "screenshot"
    description: str = "Take a screenshot of the current page for analysis"
    args_schema: Type[BaseModel] = ScreenshotInput
    browser: PlaywrightManager = Field(exclude=True)
    
    def _run(self, prefix: str = "screenshot") -> str:
        """Not implemented for async tool"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, prefix: str = "screenshot") -> str:
        """Take screenshot"""
        path = await self.browser.capture_screenshot(prefix)
        if path:
            return f"Screenshot saved to {path}"
        return "Failed to take screenshot"


class GetPageTextTool(BaseTool):
    """Tool to get page text content"""
    name: str = "get_page_text"
    description: str = "Get all visible text content from the current page. Useful for understanding what's on the page."
    args_schema: Type[BaseModel] = GetTextInput
    browser: PlaywrightManager = Field(exclude=True)
    
    def _run(self, full_page: bool = True) -> str:
        """Not implemented for async tool"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, full_page: bool = True) -> str:
        """Get page text"""
        text = await self.browser.get_page_text()
        if text:
            # Truncate if too long
            max_length = 5000
            if len(text) > max_length:
                text = text[:max_length] + f"\n... (truncated, total length: {len(text)} chars)"
            return f"Page text content:\n{text}"
        return "Failed to get page text"


class GoBackTool(BaseTool):
    """Tool to go back in browser history"""
    name: str = "go_back"
    description: str = "Navigate back to the previous page in browser history"
    browser: PlaywrightManager = Field(exclude=True)
    
    def _run(self) -> str:
        """Not implemented for async tool"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self) -> str:
        """Go back"""
        await self.browser.go_back()
        return "Navigated back to previous page"


def create_browser_tools(browser: PlaywrightManager) -> list:
    """Create a list of browser automation tools"""
    
    tools = [
        NavigateTool(browser=browser),
        ClickTool(browser=browser),
        TypeTool(browser=browser),
        WaitTool(browser=browser),
        ScrollTool(browser=browser),
        ScreenshotTool(browser=browser),
        GetPageTextTool(browser=browser),
        GoBackTool(browser=browser),
    ]
    
    log.info(f"Created {len(tools)} browser tools")
    return tools


