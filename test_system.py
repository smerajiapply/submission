"""
Simple test script to verify the setup before using real credentials
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.base_config import settings
from src.utils.logger import log


async def test_imports():
    """Test that all imports work"""
    try:
        log.info("Testing imports...")
        
        # Test Playwright
        from playwright.async_api import async_playwright
        log.info("✓ Playwright imported")
        
        # Test LangChain
        from langchain.agents import AgentExecutor
        from langchain_google_genai import ChatGoogleGenerativeAI
        log.info("✓ LangChain imported")
        
        # Test Google Gemini
        import google.generativeai as genai
        log.info("✓ Google Gemini imported")
        
        # Test our modules
        from src.automation.playwright_manager import PlaywrightManager
        from src.agents.browser_agent import BrowserAgent
        from src.agents.vision_agent import VisionAgent
        from src.automation.workflows import WorkflowEngine
        log.info("✓ Custom modules imported")
        
        log.info("\n✓ All imports successful!")
        return True
        
    except Exception as e:
        log.error(f"✗ Import failed: {e}")
        return False


async def test_browser():
    """Test browser startup"""
    try:
        log.info("\nTesting browser startup...")
        from src.automation.playwright_manager import PlaywrightManager
        
        async with PlaywrightManager(headless=True) as browser:
            await browser.navigate("https://www.google.com")
            log.info("✓ Browser navigation works")
            
            text = await browser.get_page_text()
            if "Google" in text:
                log.info("✓ Page text extraction works")
            else:
                log.warning("⚠ Page text extraction may have issues")
        
        log.info("✓ Browser test successful!")
        return True
        
    except Exception as e:
        log.error(f"✗ Browser test failed: {e}")
        return False


async def test_config():
    """Test configuration loading"""
    try:
        log.info("\nTesting configuration...")
        
        # Check directories
        log.info(f"Output dir: {settings.output_dir}")
        log.info(f"Config dir: {settings.config_dir}")
        
        if not settings.output_dir.exists():
            log.error("✗ Output directory not created")
            return False
        
        if not settings.config_dir.exists():
            log.error("✗ Config directory not created")
            return False
        
        # Check Gemini key
        if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
            log.warning("⚠ Gemini API key not configured in .env file")
            return False
        
        log.info("✓ Configuration test successful!")
        return True
        
    except Exception as e:
        log.error(f"✗ Configuration test failed: {e}")
        return False


async def main():
    """Run all tests"""
    log.info("=" * 60)
    log.info("School Portal Automation - System Test")
    log.info("=" * 60)
    
    results = []
    
    # Test imports
    results.append(await test_imports())
    
    # Test config
    results.append(await test_config())
    
    # Test browser (if imports passed)
    if results[0]:
        results.append(await test_browser())
    
    # Summary
    log.info("\n" + "=" * 60)
    if all(results):
        log.info("✓ ALL TESTS PASSED! System is ready.")
        log.info("\nNext steps:")
        log.info("1. Ensure your .env file has a valid GEMINI_API_KEY")
        log.info("2. Run: python run.py test-setup")
        log.info("3. Run: python run.py onboard --help")
    else:
        log.error("✗ Some tests failed. Please fix the issues above.")
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

