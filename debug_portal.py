"""Debug script to understand what's on the page after login"""

import asyncio
from pathlib import Path
from src.automation.playwright_manager import PlaywrightManager
from src.agents.vision_agent import VisionAgent
from src.config.base_config import settings

async def debug_page():
    """Login and see what's on the page"""
    
    async with PlaywrightManager(headless=False) as browser:
        # Login
        await browser.navigate("https://norquest.vasuniverse.com/auth/signin")
        await browser.wait(2)
        
        # Type username
        await browser.type_text("input[id*='username']", "applications@applyboard.com")
        await browser.wait(0.5)
        
        # Type password
        await browser.type_text("input[type='password']", "gjm!vre-GPV6wym4nhy")
        await browser.wait(0.5)
        
        # Click Sign in
        await browser.click_element(text="Sign in")
        await browser.wait(5)  # Wait longer for page to load
        
        # Take screenshot
        screenshot = await browser.capture_screenshot("debug_after_login")
        
        # Get page text
        page_text = await browser.get_page_text()
        print(f"\n=== Page Text (length: {len(page_text)}) ===")
        print(page_text[:500])
        print("...")
        
        # Click A button
        await browser.click_element(text="A")
        await browser.wait(3)
        
        screenshot2 = await browser.capture_screenshot("debug_after_a_click")
        page_text2 = await browser.get_page_text()
        print(f"\n=== Page Text After 'A' Click (length: {len(page_text2)}) ===")
        print(page_text2)
        
        # Use vision to analyze
        vision = VisionAgent()
        analysis = await vision.extract_information(
            screenshot2,
            "What menu items, links, or buttons are visible on this page? List everything you can see."
        )
        print(f"\n=== Vision Analysis ===")
        print(analysis)
        
        input("\nPress Enter to close browser...")

if __name__ == "__main__":
    asyncio.run(debug_page())


