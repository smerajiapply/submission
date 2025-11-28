"""
Generic action executor for config-driven workflows.

This module provides a generic way to execute actions defined in school configs.
It handles element finding, interaction, and falls back to vision when needed.
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Any, Dict
from playwright.async_api import Page, ElementHandle

from src.models.config_schemas import ActionStep, ActionType, TargetType, ActionContext
from src.automation.playwright_manager import PlaywrightManager
from src.agents.vision_agent import VisionAgent
from src.utils.logger import log


class ActionExecutor:
    """Executes individual actions from workflow configs"""
    
    def __init__(self, browser: PlaywrightManager, vision_agent: VisionAgent):
        self.browser = browser
        self.vision_agent = vision_agent
        self.current_download = None
    
    async def execute_action(
        self,
        step: ActionStep,
        context: ActionContext
    ) -> Dict[str, Any]:
        """
        Execute a single action step.
        
        Returns:
            Dict with 'success': bool and optional 'data': Any
        """
        try:
            log.info(f"Executing action: {step.action.value}")
            if step.description:
                log.info(f"  Description: {step.description}")
            
            # Substitute parameters in value and hints
            value = context.substitute(step.value) if step.value else None
            hints = [context.substitute(h) for h in step.hints]
            
            # Route to appropriate handler
            if step.action == ActionType.FIND_AND_CLICK:
                success = await self._find_and_click(
                    step.selectors, hints, step.target_type, 
                    step.use_javascript, step.opens_new_tab, step.timeout
                )
                return {"success": success}
            
            elif step.action == ActionType.FIND_AND_FILL:
                success = await self._find_and_fill(
                    step.selectors, hints, value, step.timeout
                )
                return {"success": success}
            
            elif step.action == ActionType.WAIT_FOR_LOAD:
                await self.browser.page.wait_for_load_state('networkidle', timeout=step.timeout * 1000)
                await self.browser.wait(2)
                return {"success": True}
            
            elif step.action == ActionType.WAIT_FOR_NAVIGATION:
                success = await self._wait_for_navigation(step.success_indicators, step.timeout)
                return {"success": success}
            
            elif step.action == ActionType.CAPTURE_DOWNLOAD:
                file_path = await self._capture_download(
                    step.triggers_download, step.expected_extension, step.timeout
                )
                return {"success": file_path is not None, "data": file_path}
            
            elif step.action == ActionType.SWITCH_TO_NEW_TAB:
                success = await self._switch_to_new_tab(step.timeout)
                return {"success": success}
            
            elif step.action == ActionType.PRESS_KEY:
                await self.browser.page.keyboard.press(value)
                return {"success": True}
            
            elif step.action == ActionType.SCROLL:
                await self.browser.scroll_to_bottom()
                return {"success": True}
            
            elif step.action == ActionType.WAIT:
                await self.browser.wait(step.timeout)
                return {"success": True}
            
            else:
                log.error(f"Unknown action type: {step.action}")
                return {"success": False}
        
        except Exception as e:
            log.error(f"Action execution failed: {e}")
            if step.optional:
                log.info("Step marked as optional, continuing...")
                return {"success": True}
            return {"success": False, "error": str(e)}
    
    async def _find_and_click(
        self,
        selectors: List[str],
        hints: List[str],
        target_type: Optional[TargetType],
        use_javascript: bool,
        opens_new_tab: bool,
        timeout: int
    ) -> bool:
        """Find element and click it"""
        try:
            # Try selectors first
            for selector in selectors:
                try:
                    if opens_new_tab:
                        # Check for popup
                        try:
                            async with self.browser.page.expect_popup(timeout=2000) as popup_info:
                                if use_javascript:
                                    await self.browser.evaluate_js(f'document.querySelector("{selector}").click()')
                                else:
                                    await self.browser.page.click(selector, timeout=timeout * 1000)
                            
                            # New tab opened - switch to it
                            new_tab = await popup_info.value
                            log.info(f"✓ New tab opened: {new_tab.url}")
                            self.browser.page = new_tab
                            await new_tab.wait_for_load_state('networkidle', timeout=timeout * 1000)
                            return True
                        except:
                            # No popup, regular click
                            if use_javascript:
                                await self.browser.evaluate_js(f'document.querySelector("{selector}").click()')
                            else:
                                await self.browser.page.click(selector, timeout=timeout * 1000)
                            return True
                    else:
                        if use_javascript:
                            await self.browser.evaluate_js(f'document.querySelector("{selector}").click()')
                        else:
                            await self.browser.page.click(selector, timeout=timeout * 1000)
                        log.info(f"✓ Clicked using selector: {selector}")
                        return True
                except Exception as e:
                    log.debug(f"Selector '{selector}' failed: {e}")
                    continue
            
            # Try hints with Playwright's text selector
            for hint in hints:
                try:
                    if opens_new_tab:
                        try:
                            async with self.browser.page.expect_popup(timeout=2000) as popup_info:
                                await self.browser.click_element(text=hint, timeout=timeout)
                            new_tab = await popup_info.value
                            log.info(f"✓ New tab opened: {new_tab.url}")
                            self.browser.page = new_tab
                            await new_tab.wait_for_load_state('networkidle', timeout=timeout * 1000)
                            return True
                        except:
                            await self.browser.click_element(text=hint, timeout=timeout)
                            return True
                    else:
                        await self.browser.click_element(text=hint, timeout=timeout)
                        log.info(f"✓ Clicked using hint: {hint}")
                        return True
                except Exception as e:
                    log.debug(f"Hint '{hint}' failed: {e}")
                    continue
            
            # Fallback to vision
            log.warning("All selectors and hints failed, trying vision...")
            screenshot = await self.browser.capture_screenshot("find_element_fallback")
            vision_result = await self.vision_agent.extract_information(
                screenshot,
                f"Find and describe the location of a {target_type.value if target_type else 'element'} with text: {', '.join(hints)}. Is it clickable? Where is it?"
            )
            log.info(f"Vision result: {vision_result}")
            
            # Try one more time with broader selectors
            if target_type == TargetType.BUTTON:
                await self.browser.page.click('button', timeout=timeout * 1000)
                return True
            
            return False
        
        except Exception as e:
            log.error(f"Find and click failed: {e}")
            return False
    
    async def _find_and_fill(
        self,
        selectors: List[str],
        hints: List[str],
        value: str,
        timeout: int
    ) -> bool:
        """Find input field and fill it"""
        try:
            # Try selectors first
            for selector in selectors:
                try:
                    await self.browser.page.fill(selector, value, timeout=timeout * 1000)
                    log.info(f"✓ Filled using selector: {selector}")
                    return True
                except Exception as e:
                    log.debug(f"Selector '{selector}' failed: {e}")
                    continue
            
            # Try hints
            for hint in hints:
                try:
                    await self.browser.type_text(text=hint, value=value, timeout=timeout)
                    log.info(f"✓ Filled using hint: {hint}")
                    return True
                except Exception as e:
                    log.debug(f"Hint '{hint}' failed: {e}")
                    continue
            
            log.error("Could not find input field with any selector or hint")
            return False
        
        except Exception as e:
            log.error(f"Find and fill failed: {e}")
            return False
    
    async def _wait_for_navigation(
        self,
        success_indicators: List[str],
        timeout: int
    ) -> bool:
        """Wait for navigation and verify success"""
        try:
            await self.browser.page.wait_for_load_state('networkidle', timeout=timeout * 1000)
            await self.browser.wait(2)
            
            # Check for success indicators
            if success_indicators:
                page_text = await self.browser.get_page_text()
                page_lower = page_text.lower()
                
                for indicator in success_indicators:
                    if indicator.lower() in page_lower:
                        log.info(f"✓ Found success indicator: {indicator}")
                        return True
                
                log.warning(f"No success indicators found in page text")
                return False
            
            return True
        
        except Exception as e:
            log.error(f"Wait for navigation failed: {e}")
            return False
    
    async def _capture_download(
        self,
        already_triggered: bool,
        expected_extension: Optional[str],
        timeout: int
    ) -> Optional[Path]:
        """Capture a file download"""
        try:
            async with self.browser.page.expect_download(timeout=timeout * 1000) as download_info:
                if not already_triggered:
                    # Need to wait for previous action to trigger download
                    await self.browser.wait(2)
            
            download = await download_info.value
            log.info(f"✓ Download captured: {download.suggested_filename}")
            
            # Save to temp location
            temp_path = Path(f"/tmp/{download.suggested_filename}")
            await download.save_as(temp_path)
            
            # Verify extension if specified
            if expected_extension and not temp_path.suffix.endswith(expected_extension):
                log.warning(f"Downloaded file extension {temp_path.suffix} doesn't match expected {expected_extension}")
            
            return temp_path
        
        except Exception as e:
            log.error(f"Capture download failed: {e}")
            return None
    
    async def _switch_to_new_tab(self, timeout: int) -> bool:
        """Switch to a newly opened tab"""
        try:
            await self.browser.wait(2)
            all_pages = self.browser.context.pages
            
            if len(all_pages) > 1:
                new_page = all_pages[-1]
                log.info(f"✓ Switching to new tab: {new_page.url}")
                self.browser.page = new_page
                await new_page.wait_for_load_state('networkidle', timeout=timeout * 1000)
                return True
            
            log.warning("No new tab found")
            return False
        
        except Exception as e:
            log.error(f"Switch to new tab failed: {e}")
            return False

