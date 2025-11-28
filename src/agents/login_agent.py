"""
Login agent for handling authentication workflows.

This agent executes login workflows defined in school configs.
"""

from typing import Optional, Dict, Any
import asyncio

from src.models.config_schemas import SchoolConfigV2, ActionContext
from src.automation.playwright_manager import PlaywrightManager
from src.agents.vision_agent import VisionAgent
from src.agents.action_executor import ActionExecutor
from src.utils.logger import log


class LoginAgent:
    """Specialized agent for handling login workflows"""
    
    def __init__(self, browser: PlaywrightManager, vision_agent: VisionAgent):
        self.browser = browser
        self.vision_agent = vision_agent
        self.executor = ActionExecutor(browser, vision_agent)
    
    async def execute_login(
        self,
        config: SchoolConfigV2,
        username: str,
        password: str,
        max_retries: Optional[int] = None
    ) -> bool:
        """
        Execute the login workflow from config.
        
        Args:
            config: School configuration with login workflow
            username: Username/email for login
            password: Password for login
            max_retries: Override config's max_retries
        
        Returns:
            bool: True if login successful, False otherwise
        """
        retries = max_retries if max_retries is not None else config.login.max_retries
        
        for attempt in range(1, retries + 1):
            try:
                log.info(f"=== Login Attempt {attempt}/{retries} for {config.school_name} ===")
                
                # Navigate to portal
                log.info(f"Navigating to: {config.portal_url}")
                await self.browser.navigate(config.portal_url)
                await self.browser.wait(2)
                
                # Create context with credentials
                context = ActionContext(
                    username=username,
                    password=password,
                    school_name=config.school_name
                )
                
                # Execute each step in the login workflow
                for i, step in enumerate(config.login.steps, 1):
                    log.info(f"Login step {i}/{len(config.login.steps)}: {step.action.value}")
                    
                    result = await self.executor.execute_action(step, context)
                    
                    if not result["success"]:
                        if step.optional:
                            log.warning(f"Optional step failed, continuing...")
                            continue
                        else:
                            log.error(f"Required step failed: {step.action.value}")
                            raise Exception(f"Login step {i} failed")
                    
                    # Small delay between steps
                    await self.browser.wait(1)
                
                # Verify login success
                await self.browser.capture_screenshot("after_login")
                page_text = await self.browser.get_page_text()
                
                log.info(f"Page text after login: {len(page_text)} characters")
                
                # Check if we're still on login page (failed login)
                if any(indicator in page_text.lower() for indicator in ["sign in", "login", "username", "password"]):
                    # But also check for dashboard indicators
                    if not any(indicator in page_text.lower() for indicator in ["dashboard", "welcome", "applications", "logout"]):
                        log.warning("Still on login page, login may have failed")
                        raise Exception("Login verification failed - still on login page")
                
                log.info("✓ Login successful!")
                return True
            
            except Exception as e:
                log.error(f"Login attempt {attempt} failed: {e}")
                
                if attempt < retries:
                    log.info(f"Retrying in {config.login.retry_delay} seconds...")
                    await asyncio.sleep(config.login.retry_delay)
                else:
                    log.error(f"All {retries} login attempts failed")
                    return False
        
        return False
    
    async def verify_login_success(self, success_indicators: list[str]) -> bool:
        """
        Verify login was successful by checking for indicators.
        
        Args:
            success_indicators: List of strings that indicate successful login
        
        Returns:
            bool: True if any indicator found
        """
        try:
            page_text = await self.browser.get_page_text()
            page_lower = page_text.lower()
            
            for indicator in success_indicators:
                if indicator.lower() in page_lower:
                    log.info(f"✓ Found login success indicator: {indicator}")
                    return True
            
            log.warning("No login success indicators found")
            return False
        
        except Exception as e:
            log.error(f"Login verification failed: {e}")
            return False

