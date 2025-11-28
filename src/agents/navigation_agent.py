"""
Navigation agent for finding and accessing applications.

This agent executes navigation workflows defined in school configs.
"""

from typing import Optional, Dict, Any
import asyncio

from src.models.config_schemas import SchoolConfigV2, ActionContext
from src.models.schemas import ApplicationStatus
from src.automation.playwright_manager import PlaywrightManager
from src.agents.vision_agent import VisionAgent
from src.agents.action_executor import ActionExecutor
from src.utils.logger import log


class NavigationAgent:
    """Specialized agent for navigating to applications"""
    
    def __init__(self, browser: PlaywrightManager, vision_agent: VisionAgent):
        self.browser = browser
        self.vision_agent = vision_agent
        self.executor = ActionExecutor(browser, vision_agent)
    
    async def navigate_to_application(
        self,
        config: SchoolConfigV2,
        application_id: Optional[str] = None,
        student_name: Optional[str] = None,
        student_email: Optional[str] = None,
        max_retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Navigate to a specific application using the configured workflow.
        
        Args:
            config: School configuration with navigation workflow
            application_id: Application ID to find
            student_name: Student name (alternative identifier)
            student_email: Student email (alternative identifier)
            max_retries: Override config's max_retries
        
        Returns:
            Dict with 'success', 'status_text', and 'found_status'
        """
        retries = max_retries if max_retries is not None else config.navigation.max_retries
        
        for attempt in range(1, retries + 1):
            try:
                log.info(f"=== Navigation Attempt {attempt}/{retries} ===")
                
                # Create context
                context = ActionContext(
                    application_id=application_id,
                    student_name=student_name,
                    student_email=student_email,
                    school_name=config.school_name
                )
                
                # Execute each step in the navigation workflow
                for i, step in enumerate(config.navigation.steps, 1):
                    log.info(f"Navigation step {i}/{len(config.navigation.steps)}: {step.action.value}")
                    
                    result = await self.executor.execute_action(step, context)
                    
                    if not result["success"]:
                        if step.optional:
                            log.warning(f"Optional step failed, continuing...")
                            continue
                        else:
                            log.error(f"Required step failed: {step.action.value}")
                            raise Exception(f"Navigation step {i} failed")
                    
                    # Small delay between steps
                    await self.browser.wait(1)
                
                # Extract status from current page
                status_result = await self.extract_status(config)
                
                log.info(f"✓ Navigation successful! Status: {status_result['found_status']}")
                return {
                    "success": True,
                    "status_text": status_result["status_text"],
                    "found_status": status_result["found_status"]
                }
            
            except Exception as e:
                log.error(f"Navigation attempt {attempt} failed: {e}")
                
                if attempt < retries:
                    log.info(f"Retrying in {config.navigation.retry_delay} seconds...")
                    await asyncio.sleep(config.navigation.retry_delay)
                else:
                    log.error(f"All {retries} navigation attempts failed")
                    return {
                        "success": False,
                        "status_text": str(e),
                        "found_status": None
                    }
        
        return {
            "success": False,
            "status_text": "Max retries exceeded",
            "found_status": None
        }
    
    async def extract_status(self, config: SchoolConfigV2) -> Dict[str, Any]:
        """
        Extract application status from current page.
        
        Args:
            config: School configuration with status detection patterns
        
        Returns:
            Dict with 'status_text' and 'found_status'
        """
        try:
            # Take screenshot and get page text
            screenshot = await self.browser.capture_screenshot("application_status")
            page_text = await self.browser.get_page_text()
            page_lower = page_text.lower()
            
            log.info(f"Extracting status from page ({len(page_text)} chars)")
            
            # Check status detection patterns
            found_status = None
            
            # Check each status type in order of priority
            for status_value in [ApplicationStatus.OFFER_READY, ApplicationStatus.ACCEPTED, 
                                ApplicationStatus.REJECTED, ApplicationStatus.PENDING]:
                patterns = getattr(config.status_detection, status_value.value, [])
                
                for pattern in patterns:
                    if pattern.lower() in page_lower:
                        log.info(f"✓ Found status indicator: '{pattern}' -> {status_value.value}")
                        found_status = status_value
                        break
                
                if found_status:
                    break
            
            # Use vision to extract detailed status
            vision_result = await self.vision_agent.extract_information(
                screenshot,
                "What is the application status? Look for offer status, decision, acceptance, rejection, or pending status. Provide a concise summary."
            )
            
            log.info(f"Vision extracted status: {vision_result}")
            
            # If no pattern matched, try to infer from vision result
            if not found_status:
                vision_lower = vision_result.lower()
                if any(word in vision_lower for word in ["offer", "conditional", "unconditional", "acceptance"]):
                    found_status = ApplicationStatus.OFFER_READY
                elif any(word in vision_lower for word in ["accepted", "enrolled", "deposit"]):
                    found_status = ApplicationStatus.ACCEPTED
                elif any(word in vision_lower for word in ["rejected", "declined", "not accepted"]):
                    found_status = ApplicationStatus.REJECTED
                else:
                    found_status = ApplicationStatus.PENDING
                
                log.info(f"Inferred status from vision: {found_status.value}")
            
            return {
                "status_text": vision_result,
                "found_status": found_status
            }
        
        except Exception as e:
            log.error(f"Status extraction failed: {e}")
            return {
                "status_text": str(e),
                "found_status": ApplicationStatus.PENDING
            }

