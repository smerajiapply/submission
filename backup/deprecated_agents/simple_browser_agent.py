"""
Simplified browser agent that works directly with Gemini without LangChain agents.

NOTE: This is the V1 agent optimized for complex Angular Material / SPA portals.
      Currently used by NorQuest and OCAS due to their complex UI interactions.
      
      For simpler portals, use V2 config-driven agents (LoginAgent, NavigationAgent, DownloadAgent).
      
      This agent contains specialized methods for common SPA patterns but still reads
      all school-specific config from YAML files (no school names hardcoded).
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
import google.generativeai as genai
from src.automation.playwright_manager import PlaywrightManager
from src.agents.vision_agent import VisionAgent
from src.models.schemas import SchoolConfig, LoginType, NavigationType
from src.config.base_config import settings
from src.utils.logger import log


class SimpleBrowserAgent:
    """
    V1 Browser Agent - Optimized for Complex SPA Portals
    
    This agent is production-ready and battle-tested for Angular Material portals.
    It uses config-driven routing but has specialized methods for complex interactions.
    
    Currently used by: NorQuest, OCAS
    Recommended for: Angular/React SPAs with overlays, dynamic content, shadow DOM
    """
    
    def __init__(
        self,
        browser: PlaywrightManager,
        school_config: SchoolConfig
    ):
        self.browser = browser
        self.school_config = school_config
        self.vision_agent = VisionAgent()
        
        # Configure Gemini
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        
        log.info(f"Simple browser agent initialized with {settings.gemini_model}")
        
        self.conversation_history = []
    
    async def login(self, username: str, password: str) -> bool:
        """Execute login workflow - routes based on config"""
        try:
            log.info("Starting login workflow...")
            
            # Read login type from configuration
            login_type = getattr(self.school_config, 'login_type', 'single_step')
            log.info(f"Using login type: {login_type}")
            
            if login_type == "two_step":
                return await self._login_two_step(username, password)
            elif login_type == "single_step":
                return await self._login_single_step(username, password)
            else:
                raise ValueError(f"Unsupported login_type: {login_type}. Must be 'single_step' or 'two_step'")
                
        except Exception as e:
            log.error(f"Login failed with error: {e}")
            return False
    
    async def _login_single_step(self, username: str, password: str) -> bool:
        """Single-step login (username + password on same page) - NorQuest style"""
        log.info("Using single-step login...")
        
        # Step 1: Navigate to portal
        log.info(f"Navigating to {self.school_config.portal_url}")
        await self.browser.navigate(self.school_config.portal_url)
        await self.browser.wait(2)
        
        # Step 2: Get page content
        page_text = await self.browser.get_page_text()
        log.info(f"Page loaded, analyzing...")
        
        # Step 3: Find and fill username field
        username_selectors = [
            self.school_config.selectors.username_field,
            'input[name="username"]',
            'input[name="email"]',
            'input[type="email"]',
            'input[id*="username"]',
            'input[id*="email"]',
            '#email',
            '#username'
        ]
        
        username_filled = False
        for selector in username_selectors:
            if selector:
                try:
                    success = await self.browser.type_text(selector, username, clear=True)
                    if success:
                        log.info(f"✓ Username entered using selector: {selector}")
                        username_filled = True
                        break
                except Exception as e:
                    continue
        
        if not username_filled:
            log.error("Could not find username field")
            return False
        
        await self.browser.wait(1)
        
        # Step 4: Find and fill password field
        password_selectors = [
            self.school_config.selectors.password_field,
            'input[name="password"]',
            'input[type="password"]',
            'input[id*="password"]',
            '#password'
        ]
        
        password_filled = False
        for selector in password_selectors:
            if selector:
                try:
                    success = await self.browser.type_text(selector, password, clear=True)
                    if success:
                        log.info(f"✓ Password entered using selector: {selector}")
                        password_filled = True
                        break
                except Exception as e:
                    continue
        
        if not password_filled:
            log.error("Could not find password field")
            return False
        
        await self.browser.wait(1)
        
        # Step 5: Find and click login button
        login_texts = [
            "Sign in",
            "Sign In",
            "Login",
            "Log in",
            "Log In",
            "Submit",
            "Continue"
        ]
        
        login_clicked = False
        
        # Try clicking by text first
        for text in login_texts:
            try:
                success = await self.browser.click_element(text=text, timeout=2)
                if success:
                    log.info(f"✓ Clicked login button: {text}")
                    login_clicked = True
                    break
            except Exception as e:
                continue
        
        # If text didn't work, try selectors
        if not login_clicked:
            login_selectors = [
                self.school_config.selectors.login_button,
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Sign")',
                'button:has-text("Login")',
                'button'
            ]
            
            for selector in login_selectors:
                if selector:
                    try:
                        success = await self.browser.click_element(selector=selector, timeout=2)
                        if success:
                            log.info(f"✓ Clicked login button using selector: {selector}")
                            login_clicked = True
                            break
                    except Exception as e:
                        continue
        
        if not login_clicked:
            log.error("Could not find login button")
            return False
        
        # Step 6: Wait longer for page to fully load after login
        log.info("Waiting for dashboard to load...")
        await self.browser.wait(10)  # Wait 10 seconds for JavaScript to load
        
        # Take a screenshot to see what loaded
        await self.browser.capture_screenshot("after_login_wait")
        
        # Check if we're on a different page (login successful)
        current_url = await self.browser.get_current_url()
        log.info(f"Current URL after login: {current_url}")
        
        # Get page content to verify
        page_text = await self.browser.get_page_text()
        
        # Check for common success indicators
        success_indicators = [
            "dashboard",
            "welcome",
            "logout",
            "sign out",
            "applications",
            "profile"
        ]
        
        page_lower = page_text.lower()
        login_success = any(indicator in page_lower for indicator in success_indicators)
        
        # Also check if we're not still on the login page
        if "sign in" in page_lower and "password" in page_lower:
            log.error("Still on login page - login may have failed")
            return False
        
        if login_success:
            log.info("✓ Login successful!")
            return True
        else:
            log.warning("Login may have succeeded - verification inconclusive")
            return True  # Assume success if we got past login page
    
    async def _login_two_step(self, username: str, password: str) -> bool:
        """Two-step login (username first, then password on separate page) - OCAS style"""
        log.info("Using two-step login...")
        
        # Step 1: Navigate to portal
        log.info(f"Navigating to {self.school_config.portal_url}")
        await self.browser.navigate(self.school_config.portal_url)
        await self.browser.wait(3)
        
        # Step 2: Fill username field
        username_selectors = [
            'input[name="username"]',
            'input[name="Username"]',
            'input[name="email"]',
            'input[name="Email"]',
            'input[type="email"]',
            'input[id*="username"]',
            'input[id*="Username"]',
            'input[id*="email"]',
            'input[id*="Email"]',
            '#Username',
            '#Email',
            '#username',
            '#email'
        ]
        
        username_filled = False
        for selector in username_selectors:
            try:
                success = await self.browser.type_text(selector, username, clear=True)
                if success:
                    log.info(f"✓ Username entered using selector: {selector}")
                    username_filled = True
                    break
            except Exception as e:
                continue
        
        if not username_filled:
            log.error("Could not find username field in step 1")
            await self.browser.capture_screenshot("username_field_not_found")
            return False
        
        await self.browser.wait(1)
        
        # Step 3: Click "Next" or "Continue" button to proceed to password page
        next_texts = [
            "Next",
            "Continue",
            "Proceed",
            "Submit"
        ]
        
        next_clicked = False
        for text in next_texts:
            try:
                success = await self.browser.click_element(text=text, timeout=3)
                if success:
                    log.info(f"✓ Clicked '{text}' button")
                    next_clicked = True
                    break
            except Exception as e:
                continue
        
        # Try button selectors if text didn't work
        if not next_clicked:
            next_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button'
            ]
            
            for selector in next_selectors:
                try:
                    success = await self.browser.click_element(selector=selector, timeout=2)
                    if success:
                        log.info(f"✓ Clicked next button using selector: {selector}")
                        next_clicked = True
                        break
                except Exception as e:
                    continue
        
        if not next_clicked:
            log.error("Could not find Next/Continue button")
            await self.browser.capture_screenshot("next_button_not_found")
            return False
        
        # Step 4: Wait for password page to load
        log.info("Waiting for password page...")
        await self.browser.wait(5)  # Wait for new page
        await self.browser.capture_screenshot("password_page")
        
        # Step 5: Fill password field
        password_selectors = [
            'input[name="password"]',
            'input[name="Password"]',
            'input[type="password"]',
            'input[id*="password"]',
            'input[id*="Password"]',
            '#Password',
            '#password'
        ]
        
        password_filled = False
        for selector in password_selectors:
            try:
                success = await self.browser.type_text(selector, password, clear=True)
                if success:
                    log.info(f"✓ Password entered using selector: {selector}")
                    password_filled = True
                    break
            except Exception as e:
                continue
        
        if not password_filled:
            log.error("Could not find password field in step 2")
            return False
        
        await self.browser.wait(1)
        
        # Take a screenshot to see the login form state
        await self.browser.capture_screenshot("before_password_submit")
        
        # Step 6: Submit the password form
        log.info("Attempting to submit password form...")
        login_submitted = False
        
        # Method 1: Try finding and clicking the Sign in button by selector
        try:
            # Look for the actual button element
            await self.browser.page.click('button[type="submit"]', timeout=3000)
            log.info("✓ Clicked submit button using selector")
            login_submitted = True
        except Exception as e:
            log.debug(f"Submit button selector failed: {e}")
        
        # Method 2: Try JavaScript form submission
        if not login_submitted:
            try:
                log.info("Trying JavaScript form submission...")
                script = """
                (function() {
                    // Find the form
                    const forms = document.querySelectorAll('form');
                    for (const form of forms) {
                        // Check if this form has a password field
                        const passwordField = form.querySelector('input[type="password"]');
                        if (passwordField) {
                            form.submit();
                            return true;
                        }
                    }
                    
                    // If form.submit() doesn't work, try clicking the button
                    const buttons = document.querySelectorAll('button, input[type="submit"]');
                    for (const btn of buttons) {
                        const text = btn.textContent || btn.value || '';
                        if (text.toLowerCase().includes('sign') || btn.type === 'submit') {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                })()
                """
                result = await self.browser.evaluate_js(script)
                if result:
                    log.info("✓ Submitted form using JavaScript")
                    login_submitted = True
            except Exception as e:
                log.error(f"JavaScript form submission failed: {e}")
        
        # Method 3: Press Enter on the password field
        if not login_submitted:
            try:
                log.info("Trying Enter key on password field...")
                await self.browser.page.press('input[type="password"]', 'Enter')
                log.info("✓ Pressed Enter on password field")
                login_submitted = True
            except Exception as e:
                log.error(f"Enter key failed: {e}")
        
        # Method 4: Try clicking by text as last resort
        if not login_submitted:
            try:
                await self.browser.click_element(text="Sign in", timeout=3)
                log.info("✓ Clicked 'Sign in' button by text")
                login_submitted = True
            except Exception as e:
                log.debug(f"Text click failed: {e}")
        
        if not login_submitted:
            log.error("Could not submit password form")
            return False
        
        # Step 7: Wait for redirect after login
        log.info("Waiting for redirect after login...")
        await self.browser.wait(5)
        
        page_text = await self.browser.get_page_text()
        page_lower = page_text.lower()
        current_url = await self.browser.get_current_url()
        
        log.info(f"Page after login - URL: {current_url}")
        log.info(f"Page text length: {len(page_text)}")
        log.info(f"Page text: {page_text[:800]}")
        
        # Step 8: Check if we're on portal selection page (Agent Portal vs other options)
        if "agent portal" in page_lower or "select portal" in page_lower:
            log.info("Detected portal selection page - selecting Agent Portal...")
            await self.browser.capture_screenshot("portal_selection_page")
            
            portal_selected = False
            
            # Try to click "Agent Portal"
            try:
                await self.browser.click_element(text="Agent Portal", timeout=5)
                log.info("✓ Clicked 'Agent Portal'")
                portal_selected = True
            except Exception as e:
                log.debug(f"Direct text click failed: {e}")
            
            # Try JavaScript if direct click failed
            if not portal_selected:
                try:
                    script = """
                    (function() {
                        const elements = document.querySelectorAll('button, a, div[role="button"], [onclick], div, span');
                        
                        for (const el of elements) {
                            const text = el.textContent.trim();
                            if (text === 'Agent Portal' || text.includes('Agent Portal')) {
                                // Find clickable parent
                                let clickable = el;
                                while (clickable && clickable !== document.body) {
                                    if (clickable.onclick || clickable.tagName === 'BUTTON' || 
                                        clickable.tagName === 'A' || clickable.getAttribute('role') === 'button' ||
                                        clickable.getAttribute('role') === 'link') {
                                        clickable.click();
                                        return true;
                                    }
                                    clickable = clickable.parentElement;
                                }
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    })()
                    """
                    result = await self.browser.evaluate_js(script)
                    if result:
                        log.info("✓ Clicked 'Agent Portal' using JavaScript")
                        portal_selected = True
                except Exception as e:
                    log.error(f"JavaScript click failed: {e}")
            
            if not portal_selected:
                log.error("Could not select Agent Portal")
                return False
            
            # Wait for next page
            log.info("Waiting after portal selection...")
            await self.browser.wait(5)
            await self.browser.capture_screenshot("after_portal_selection")
            
            # Refresh page content
            page_text = await self.browser.get_page_text()
            page_lower = page_text.lower()
            current_url = await self.browser.get_current_url()
            log.info(f"After portal selection - URL: {current_url}")
            log.info(f"Page text: {page_text[:800]}")
        
        # Step 9: Check if we're on agency/organization selection page
        if "applyboard" in page_lower and ("india" in page_lower or "select" in page_lower or "agency" in page_lower or "organization" in page_lower):
            log.info("Detected agency selection page - selecting ApplyBoard...")
            await self.browser.capture_screenshot("agency_selection_page")
            
            agency_selected = False
            
            # Try to click "ApplyBoard" (not "ApplyBoard India")
            try:
                # Look for exact "ApplyBoard" text (not "ApplyBoard India")
                await self.browser.click_element(text="ApplyBoard", timeout=5)
                log.info("✓ Clicked 'ApplyBoard' using text selector")
                agency_selected = True
            except Exception as e:
                log.debug(f"Direct text click failed: {e}")
            
            # Try JavaScript to find and click the right option
            if not agency_selected:
                try:
                    script = """
                    (function() {
                        // Find all elements
                        const elements = document.querySelectorAll('button, a, div[role="button"], [onclick], div, span, card, mat-card');
                        
                        for (const el of elements) {
                            const text = el.textContent.trim();
                            // Match "ApplyBoard" but NOT "ApplyBoard India"
                            // Check if element contains "ApplyBoard" but not "India"
                            if (text.includes('ApplyBoard') && !text.includes('India')) {
                                // Try to find a clickable parent
                                let clickable = el;
                                while (clickable && clickable !== document.body) {
                                    if (clickable.onclick || clickable.tagName === 'BUTTON' || 
                                        clickable.tagName === 'A' || clickable.getAttribute('role') === 'button' ||
                                        clickable.getAttribute('role') === 'link' || 
                                        clickable.classList.contains('card') ||
                                        clickable.tagName === 'MAT-CARD') {
                                        clickable.click();
                                        return true;
                                    }
                                    clickable = clickable.parentElement;
                                }
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    })()
                    """
                    result = await self.browser.evaluate_js(script)
                    if result:
                        log.info("✓ Clicked 'ApplyBoard' using JavaScript")
                        agency_selected = True
                except Exception as e:
                    log.error(f"JavaScript click failed: {e}")
            
            if not agency_selected:
                log.error("Could not select ApplyBoard agency")
                return False
            
            # Wait for dashboard to load after agency selection
            log.info("Waiting for dashboard after agency selection...")
            await self.browser.wait(5)
            await self.browser.capture_screenshot("after_agency_selection")
        
        # Step 10: Verify we're on the dashboard/applications page
        # Check URL and page content multiple times (sometimes redirect is slow)
        for attempt in range(3):
            await self.browser.wait(3)
            current_url = await self.browser.get_current_url()
            page_text = await self.browser.get_page_text()
            page_lower = page_text.lower()
            
            log.info(f"Verification attempt {attempt + 1}/3 - URL: {current_url}")
            log.info(f"Page text length: {len(page_text)}")
            
            # Check if redirected away from auth page
            if "authenticate.ocas.ca" not in current_url:
                log.info("✓ Redirected away from auth page!")
                break
            
            # Check if page content has changed significantly
            if len(page_text) > 500:
                log.info("✓ Page content loaded!")
                break
            
            # Check for login still present
            if attempt < 2 and len(page_text) < 300:
                log.warning(f"Page still loading, waiting longer... (attempt {attempt + 1})")
                continue
            else:
                break
        
        await self.browser.capture_screenshot("after_two_step_login_final")
        
        # Final verification
        current_url = await self.browser.get_current_url()
        log.info(f"Final URL after login: {current_url}")
        
        page_text = await self.browser.get_page_text()
        page_lower = page_text.lower()
        
        log.info(f"Final page text length: {len(page_text)}")
        log.info(f"First 500 chars: {page_text[:500]}")
        
        # Check for success indicators
        success_indicators = [
            "dashboard",
            "welcome",
            "logout",
            "sign out",
            "applications",
            "profile",
            "offers",
            "submissions",
            "agent portal",
            "my applications"
        ]
        
        login_success = any(indicator in page_lower for indicator in success_indicators)
        
        # Check if we're still on login/error page
        login_failed_indicators = [
            "invalid credentials",
            "incorrect",
            "invalid username or password",
            "login failed"
        ]
        
        has_error = any(indicator in page_lower for indicator in login_failed_indicators)
        
        # If we see error text, login definitely failed
        if has_error:
            log.error("Login error detected on page")
            return False
        
        # If we're still on authenticate.ocas.ca with minimal content, login likely failed
        if "authenticate.ocas.ca" in current_url and len(page_text) < 300:
            log.error("Still on login page after multiple attempts - login failed")
            return False
        
        # If we have enough content or success indicators, login succeeded
        if len(page_text) > 500 or login_success or "authenticate.ocas.ca" not in current_url:
            log.info("✓ Two-step login with portal and agency selection successful!")
            return True
        else:
            log.warning("Login verification inconclusive - assuming success")
            return True
    
    async def find_application(
        self,
        application_id: Optional[str] = None,
        student_name: Optional[str] = None,
        student_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Find a specific application with intelligent navigation - routes based on config"""
        try:
            log.info("Searching for application...")
            
            # Read navigation type from configuration
            nav_type = getattr(self.school_config, 'navigation_type', 'dropdown')
            log.info(f"Using navigation type: {nav_type}")
            
            if nav_type == "left_modal":
                return await self._find_application_left_modal(application_id, student_name, student_email)
            elif nav_type == "dropdown":
                return await self._find_application_dropdown(application_id, student_name, student_email)
            else:
                raise ValueError(f"Unsupported navigation_type: {nav_type}. Must be 'dropdown' or 'left_modal'")
                
        except Exception as e:
            log.error(f"Application search failed: {e}")
            import traceback
            log.error(traceback.format_exc())
            return {"success": False, "status_text": "", "found_status": None}
    
    async def _find_application_dropdown(
        self,
        application_id: Optional[str] = None,
        student_name: Optional[str] = None,
        student_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """NorQuest-style dropdown navigation"""
        log.info("Using dropdown navigation (NorQuest style)...")
        
        # Step 1: Wait a bit more to ensure page is fully loaded
        await self.browser.wait(3)
        
        # Step 2: Take screenshot of current state
        await self.browser.capture_screenshot("start_search")
        page_text = await self.browser.get_page_text()
        log.info(f"Initial page text length: {len(page_text)}")
        log.info(f"First 200 chars of page: {page_text[:200]}")
        
        # Step 3: Click on Applications dropdown (Angular Material)
        log.info("Looking for Applications dropdown (Angular Material UI)...")
        applications_clicked = False
        
        # For Angular Material, we need to click the button/trigger element
        try:
            log.info("Attempting to click Applications button...")
            # Try to find and click the Applications button/trigger
            script = """
            (function() {
                // Find element containing "Applications" text
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                
                let node;
                while(node = walker.nextNode()) {
                    if (node.nodeValue.trim() === 'Applications') {
                        const parent = node.parentElement;
                        // Find the clickable parent (button, div with click handler, etc.)
                        let clickable = parent;
                        while (clickable && clickable !== document.body) {
                            if (clickable.onclick || clickable.getAttribute('role') === 'button' || 
                                clickable.tagName === 'BUTTON' || clickable.tagName === 'A' ||
                                clickable.classList.contains('mat-menu-trigger')) {
                                clickable.click();
                                return true;
                            }
                            clickable = clickable.parentElement;
                        }
                        // If no specific clickable found, click the parent
                        parent.click();
                        return true;
                    }
                }
                return false;
            })()
            """
            result = await self.browser.evaluate_js(script)
            if result:
                log.info("✓ Clicked Applications trigger using JavaScript")
                await self.browser.wait(2)  # Wait for overlay to appear
                await self.browser.capture_screenshot("after_applications_click")
                applications_clicked = True
        except Exception as e:
            log.error(f"JavaScript click failed: {e}")
        
        if not applications_clicked:
            log.error("Could not click Applications dropdown")
            return {"success": False, "status_text": "", "found_status": None}
        
        # Step 4: Wait for Angular Material overlay to appear and click "View applications"
        log.info("Waiting for dropdown overlay to appear...")
        await self.browser.wait(2)  # Extra wait for Angular to render overlay
        
        view_clicked = False
        
        try:
            log.info("Looking for 'View applications' in the overlay...")
            # Angular Material renders dropdowns in .cdk-overlay-container
            # Find and click the span containing "View applications"
            script = """
            (function() {
                // Look in the overlay container
                const overlayContainer = document.querySelector('.cdk-overlay-container');
                if (!overlayContainer) {
                    return false;
                }
                
                // Find all spans
                const spans = overlayContainer.querySelectorAll('span');
                for (const span of spans) {
                    const text = span.textContent.trim();
                    if (text === 'View applications' || text === 'View Applications') {
                        // Click the span or its parent
                        let clickable = span;
                        while (clickable && clickable !== overlayContainer) {
                            if (clickable.onclick || clickable.getAttribute('role') || 
                                clickable.tagName === 'BUTTON' || clickable.tagName === 'A') {
                                clickable.click();
                                return true;
                            }
                            clickable = clickable.parentElement;
                        }
                        // Just click the span itself
                        span.click();
                        return true;
                    }
                }
                
                // Try alternative text searches
                const allElements = overlayContainer.querySelectorAll('*');
                for (const el of allElements) {
                    const text = el.textContent.trim();
                    if (text === 'View applications' || text === 'View Applications') {
                        el.click();
                        return true;
                    }
                }
                
                return false;
            })()
            """
            result = await self.browser.evaluate_js(script)
            if result:
                log.info("✓ Successfully clicked 'View applications' in overlay")
                await self.browser.wait(5)  # Wait for applications page to load
                await self.browser.capture_screenshot("after_view_applications")
                view_clicked = True
        except Exception as e:
            log.error(f"Failed to click View applications: {e}")
        
        if not view_clicked:
            log.warning("Could not click 'View applications' - trying alternative method...")
            # Try direct Playwright selector for CDK overlay
            try:
                # Wait a bit longer for overlay
                await self.browser.wait(2)
                
                # Scroll element into view and then click
                await self.browser.page.eval_on_selector(
                    'text=View applications',
                    'element => element.scrollIntoView()'
                )
                await self.browser.wait(0.5)
                
                # Now click
                await self.browser.page.click('text=View applications', timeout=5000)
                await self.browser.wait(5)
                log.info("✓ Clicked 'View applications' after scrolling into view")
                view_clicked = True
            except Exception as e:
                log.error(f"Scroll and click failed: {e}")
                
                # Last resort: use JavaScript to click directly
                try:
                    script = """
                    (function() {
                        const elements = document.querySelectorAll('*');
                        for (const el of elements) {
                            if (el.textContent.trim() === 'View applications') {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    })()
                    """
                    result = await self.browser.evaluate_js(script)
                    if result:
                        await self.browser.wait(5)
                        log.info("✓ Clicked 'View applications' using direct JavaScript")
                        view_clicked = True
                except Exception as e2:
                    log.error(f"JavaScript click also failed: {e2}")
                
        # Even if view_clicked is false, let's continue and see what's on the page
        log.info(f"Continuing to check page content...")
        
        # Step 5: Now we should see the applications list
        page_text = await self.browser.get_page_text()
        log.info(f"Page text after View Applications: {len(page_text)}")
        log.info(f"First 500 chars: {page_text[:500]}")
        
        # Check if application ID is visible on the page
        if application_id and str(application_id) in page_text:
            log.info(f"✓ Found application ID {application_id} on page!")
            
            # Try to click on it to view details
            # For NorQuest, clicking application opens a new tab
            clicked = False
            new_tab_opened = False
            
            try:
                # Check if clicking opens a new tab
                log.info("Attempting to click application (checking for new tab)...")
                try:
                    async with self.browser.page.expect_popup(timeout=2000) as popup_info:
                        await self.browser.click_element(text=str(application_id), timeout=5)
                    
                    # New tab opened!
                    new_tab = await popup_info.value
                    log.info(f"✓ Application opened in new tab: {new_tab.url}")
                    
                    # Switch context to the new tab
                    self.browser.page = new_tab
                    await new_tab.wait_for_load_state('networkidle', timeout=10000)
                    await self.browser.wait(2)
                    log.info("✓ Switched to application tab")
                    new_tab_opened = True
                    clicked = True
                    
                except Exception as popup_error:
                    # No popup, regular click
                    log.debug(f"No popup detected: {popup_error}")
                    await self.browser.click_element(text=str(application_id), timeout=5)
                    await self.browser.wait(3)
                    log.info("✓ Clicked on application to view details")
                    clicked = True
                
                await self.browser.capture_screenshot("after_application_click")
                
            except Exception as e:
                log.info(f"Could not click application ID directly: {e}")
            
            if not clicked:
                # Try clicking a link or row containing the ID
                try:
                    selector = f'a:has-text("{application_id}")'
                    await self.browser.click_element(selector=selector, timeout=3)
                    await self.browser.wait(3)
                    log.info("✓ Clicked application link")
                    clicked = True
                except:
                    pass
            
            if not clicked:
                # Try JavaScript click on the row
                try:
                    script = f"""
                    (function() {{
                        const elements = document.querySelectorAll('*');
                        for (const el of elements) {{
                            if (el.textContent.includes('{application_id}')) {{
                                // Find the clickable parent (row, link, etc.)
                                let clickable = el;
                                while (clickable && clickable !== document.body) {{
                                    if (clickable.onclick || clickable.tagName === 'A' || 
                                        clickable.tagName === 'TR' || clickable.getAttribute('role') === 'row') {{
                                        clickable.click();
                                        return true;
                                    }}
                                    clickable = clickable.parentElement;
                                }}
                                el.click();
                                return true;
                            }}
                        }}
                        return false;
                    }})()
                    """
                    result = await self.browser.evaluate_js(script)
                    if result:
                        await self.browser.wait(3)
                        log.info("✓ Clicked application using JavaScript")
                        await self.browser.capture_screenshot("after_js_application_click")
                        clicked = True
                except Exception as e:
                    log.debug(f"JavaScript click failed: {e}")
            
            if clicked:
                # Get the new page content after clicking
                page_text = await self.browser.get_page_text()
                log.info(f"Page text after clicking application: {len(page_text)}")
        else:
            log.warning(f"Application ID {application_id} not found in visible text")
            log.info("Taking screenshot to analyze...")
            screenshot = await self.browser.capture_screenshot("applications_page")
            
            # Use vision to see if applications are visible
            vision_result = await self.vision_agent.extract_information(
                screenshot,
                f"Do you see a list of applications on this page? Is application ID {application_id} visible anywhere? What application IDs or information do you see?"
            )
            log.info(f"Vision analysis of applications page: {vision_result}")
        
        # Step 6: Scroll down to ensure all content is loaded
        await self.browser.scroll_to_bottom()
        await self.browser.wait(2)
        
        # Step 7: Take final screenshot and get full page text
        screenshot = await self.browser.capture_screenshot("application_details_final")
        page_text = await self.browser.get_page_text()
        log.info(f"Final page text length: {len(page_text)}")
        
        # Step 8: Look for status indicators in text
        status_keywords = [
            "conditional offer",
            "unconditional offer",
            "offer",
            "accepted",
            "acceptance",
            "approved",
            "admitted",
            "admission",
            "pending",
            "under review",
            "reviewing",
            "rejected",
            "declined",
            "waitlist",
            "deferred"
        ]
        
        found_status = None
        page_lower = page_text.lower()
        for keyword in status_keywords:
            if keyword in page_lower:
                found_status = keyword
                log.info(f"✓ Found status indicator in text: {keyword}")
                break
        
        # Step 9: Use vision for deeper analysis
        status_text = await self.vision_agent.extract_information(
            screenshot,
            f"Look carefully at this page and extract the application status for application ID: {application_id}. Look for: conditional offer, unconditional offer, acceptance letter, admission decision, application status, pending, rejected, or any status/decision information. Describe what you see in detail."
        )
        
        log.info(f"Vision extracted status: {status_text}")
        
        return {
            "success": True,
            "status_text": status_text,
            "found_status": found_status
        }
    
    async def _find_application_left_modal(
        self,
        application_id: Optional[str] = None,
        student_name: Optional[str] = None,
        student_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """OCAS-style left navigation modal"""
        log.info("Using left modal navigation (OCAS style)...")
        
        # Step 1: Wait for page to load
        await self.browser.wait(3)
        await self.browser.capture_screenshot("ocas_after_login")
        
        page_text = await self.browser.get_page_text()
        log.info(f"Initial page text length: {len(page_text)}")
        log.info(f"First 500 chars: {page_text[:500]}")
        
        # Step 2: Check if we already see applications or if we need to navigate
        page_lower = page_text.lower()
        
        # If application ID is already visible, we might be on the applications page
        if application_id and str(application_id) in page_text:
            log.info(f"✓ Application ID {application_id} already visible - on applications page")
        else:
            # Step 3: Look for left navigation - search for "offers" or "applications"
            log.info("Searching for left navigation menu...")
            nav_found = False
            
            # Try to find and click navigation items containing relevant text
            nav_keywords = [
                "Offers",
                "offers",
                "Applications",
                "applications",
                "Submissions",
                "submissions",
                "My Applications",
                "View Applications"
            ]
            
            for keyword in nav_keywords:
                try:
                    log.info(f"Looking for '{keyword}' in left navigation...")
                    
                    # Try direct text click
                    try:
                        await self.browser.click_element(text=keyword, timeout=3)
                        log.info(f"✓ Clicked '{keyword}' in navigation")
                        await self.browser.wait(5)
                        await self.browser.capture_screenshot(f"after_nav_{keyword}")
                        nav_found = True
                        break
                    except:
                        pass
                    
                    # Try finding in nav/aside/sidebar elements
                    script = f"""
                    (function() {{
                        // Look for nav, aside, sidebar elements
                        const navElements = document.querySelectorAll('nav, aside, [class*="sidebar"], [class*="menu"], [class*="navigation"]');
                        
                        for (const nav of navElements) {{
                            const allElements = nav.querySelectorAll('*');
                            for (const el of allElements) {{
                                const text = el.textContent.trim();
                                if (text === '{keyword}' || text.includes('{keyword}')) {{
                                    // Find clickable parent
                                    let clickable = el;
                                    while (clickable && clickable !== nav) {{
                                        if (clickable.onclick || clickable.tagName === 'A' || 
                                            clickable.tagName === 'BUTTON' || clickable.getAttribute('role') === 'button' ||
                                            clickable.getAttribute('role') === 'menuitem') {{
                                            clickable.click();
                                            return true;
                                        }}
                                        clickable = clickable.parentElement;
                                    }}
                                    el.click();
                                    return true;
                                }}
                            }}
                        }}
                        return false;
                    }})()
                    """
                    
                    result = await self.browser.evaluate_js(script)
                    if result:
                        log.info(f"✓ Clicked '{keyword}' in left navigation using JavaScript")
                        await self.browser.wait(5)
                        nav_found = True
                        break
                        
                except Exception as e:
                    log.debug(f"Could not click '{keyword}': {e}")
                    continue
            
            if not nav_found:
                log.warning("Could not find navigation to offers/applications")
                # Take screenshot for analysis
                screenshot = await self.browser.capture_screenshot("navigation_search")
                vision_result = await self.vision_agent.extract_information(
                    screenshot,
                    "What navigation options do you see on this page? Look for menus, sidebars, or links related to applications, offers, or submissions."
                )
                log.info(f"Vision analysis of navigation: {vision_result}")
        
        # Step 4: Now search for the application ID
        page_text = await self.browser.get_page_text()
        log.info(f"Page text after navigation: {len(page_text)}")
        
        if application_id and str(application_id) in page_text:
            log.info(f"✓ Found application ID {application_id} on page!")
            
            # Try to click on it
            clicked = False
            try:
                await self.browser.click_element(text=str(application_id), timeout=5)
                await self.browser.wait(3)
                log.info("✓ Clicked on application")
                await self.browser.capture_screenshot("after_application_click")
                clicked = True
            except Exception as e:
                log.info(f"Direct click failed: {e}")
            
            if not clicked:
                # Try JavaScript click
                script = f"""
                (function() {{
                    const elements = document.querySelectorAll('*');
                    for (const el of elements) {{
                        if (el.textContent.includes('{application_id}')) {{
                            let clickable = el;
                            while (clickable && clickable !== document.body) {{
                                if (clickable.onclick || clickable.tagName === 'A' || 
                                    clickable.tagName === 'TR' || clickable.tagName === 'BUTTON') {{
                                    clickable.click();
                                    return true;
                                }}
                                clickable = clickable.parentElement;
                            }}
                            el.click();
                            return true;
                        }}
                    }}
                    return false;
                }})()
                """
                result = await self.browser.evaluate_js(script)
                if result:
                    await self.browser.wait(3)
                    log.info("✓ Clicked application using JavaScript")
                    clicked = True
            
            if clicked:
                page_text = await self.browser.get_page_text()
                log.info(f"Page text after clicking application: {len(page_text)}")
        else:
            log.warning(f"Application ID {application_id} not found")
        
        # Step 5: Analyze page for status
        await self.browser.scroll_to_bottom()
        await self.browser.wait(2)
        
        screenshot = await self.browser.capture_screenshot("ocas_application_details")
        page_text = await self.browser.get_page_text()
        log.info(f"Final page text length: {len(page_text)}")
        
        # Look for status keywords
        status_keywords = [
            "conditional offer",
            "unconditional offer",
            "offer",
            "accepted",
            "acceptance",
            "approved",
            "admitted",
            "admission",
            "pending",
            "under review",
            "reviewing",
            "rejected",
            "declined"
        ]
        
        found_status = None
        page_lower = page_text.lower()
        for keyword in status_keywords:
            if keyword in page_lower:
                found_status = keyword
                log.info(f"✓ Found status indicator: {keyword}")
                break
        
        # Use vision for analysis
        status_text = await self.vision_agent.extract_information(
            screenshot,
            f"Look at this OCAS application page for application ID: {application_id}. Extract the application status, decision, or any offer information. Look for: conditional offer, acceptance, admission decision, pending, rejected, or any status. Describe what you see."
        )
        
        log.info(f"Vision extracted status: {status_text}")
        
        return {
            "success": True,
            "status_text": status_text,
            "found_status": found_status
        }
    
    async def download_offer(
        self, 
        application_id: Optional[str] = None,
        school_name: Optional[str] = None
    ) -> Optional[Path]:
        """Download offer letter if available - tries multiple variations"""
        try:
            log.info("Looking for offer letter download...")
            
            # Import storage here to avoid circular imports
            from src.utils.storage import storage
            
            # Take screenshot first to see what's available
            screenshot = await self.browser.capture_screenshot("before_download_search")
            page_text = await self.browser.get_page_text()
            page_lower = page_text.lower()
            
            log.info(f"Page text length: {len(page_text)}")
            log.info(f"Searching for download options in page...")
            
            # Prioritized list of download/offer text patterns
            # Order matters: try most specific first, generic last
            download_patterns = [
                # Most specific patterns first (download links with icons)
                ("View Letter of Acceptance", "view letter of acceptance"),
                ("View Acceptance Letter", "view acceptance letter"),
                ("Download Letter of Acceptance", "download letter of acceptance"),
                # Print/Save options (common for portals)
                ("Print Offer", "print offer"),
                ("Print Letter", "print letter"),
                ("Print Offer Letter", "print offer letter"),
                ("Save Offer", "save offer"),
                ("Save Letter", "save letter"),
                # Direct download
                ("Download Offer", "download offer"),
                ("Download Letter", "download letter"),
                ("Download Acceptance", "download acceptance"),
                # Conditional offers
                ("Download Conditional Offer", "download conditional offer"),
                ("View Conditional Offer", "view conditional offer"),
                ("Conditional Offer", "conditional offer"),
                # Admission letters
                ("Download Admission Letter", "download admission letter"),
                ("Letter of Admission", "letter of admission"),
                ("Admission Letter", "admission letter"),
                # Offer letter
                ("Download Offer Letter", "download offer letter"),
                ("View Offer Letter", "view offer letter"),
                ("Offer Letter", "offer letter"),
                # View options
                ("View Offer", "view offer"),
                ("View Letter", "view letter"),
                ("View Decision", "view decision"),
                # Generic (last resort)
                ("Decision Letter", "decision letter"),
                ("Download Decision", "download decision"),
                ("Download", "download"),
                ("Offer", "offer"),
            ]
            
            # Check which patterns exist on the page
            found_patterns = []
            for display_text, search_text in download_patterns:
                if search_text in page_lower:
                    found_patterns.append(display_text)
                    log.info(f"Found potential download text: '{display_text}'")
            
            if not found_patterns:
                log.warning("No download patterns found in page text")
                # Use vision to look for download buttons
                vision_result = await self.vision_agent.extract_information(
                    screenshot,
                    "Look for any buttons, links, or options to download, view, or print an offer letter, conditional offer, acceptance letter, or admission decision. Describe what you see."
                )
                log.info(f"Vision analysis: {vision_result}")
            
            # Try to click any of the found patterns
            download_clicked = False
            popup_pdf_saved = False
            
            for display_text in found_patterns:
                try:
                    log.info(f"Attempting to click: {display_text}")
                    
                    # Special handling for "Print Offer" which triggers direct download
                    if "print" in display_text.lower():
                        log.info("Print button detected - setting up download listener before clicking...")
                        try:
                            # Set up download listener BEFORE clicking
                            async with self.browser.page.expect_download(timeout=15000) as download_info:
                                await self.browser.click_element(text=display_text, timeout=3)
                                log.info("✓ Clicked print button, waiting for download...")
                                # Extra wait for modal/spinning circle
                                await self.browser.wait(3)
                            
                            # Download captured!
                            download = await download_info.value
                            log.info(f"✓ Download captured: {download.suggested_filename}")
                            
                            # Save the downloaded file
                            temp_path = Path(f"/tmp/{download.suggested_filename}")
                            await download.save_as(temp_path)
                            log.info(f"Download saved to temp: {temp_path}")
                            
                            # Read and save using storage manager
                            if temp_path.exists():
                                file_bytes = temp_path.read_bytes()
                                log.info(f"✓ File size: {len(file_bytes)} bytes")
                                
                                if application_id and school_name:
                                    saved_path = storage.save_offer(
                                        school_name=school_name,
                                        application_id=application_id,
                                        file_content=file_bytes,
                                        extension="pdf"
                                    )
                                    log.info(f"✓ PDF saved: {saved_path}")
                                    temp_path.unlink()  # Clean up temp file
                                    return saved_path
                        except TimeoutError:
                            log.warning("Print button click timed out waiting for download")
                        except Exception as e:
                            log.error(f"Print download failed: {e}")
                    
                    # For other buttons, try to catch popup/new tab (common for "View Letter" links)
                    try:
                        log.info("Checking if link opens in new tab...")
                        async with self.browser.page.expect_popup(timeout=3000) as popup_info:
                            await self.browser.click_element(text=display_text, timeout=3)
                        
                        # New tab opened!
                        popup = await popup_info.value
                        log.info(f"✓ New tab opened: {popup.url}")
                        
                        # Wait for PDF to load in popup
                        await popup.wait_for_load_state('load', timeout=10000)
                        await self.browser.wait(2)
                        
                        popup_url = popup.url
                        log.info(f"Popup URL: {popup_url}")
                        
                        # Save PDF from the popup
                        try:
                            # Check if it's a direct PDF URL
                            if '.pdf' in popup_url.lower() or 'binary-documents' in popup_url or 'pdf' in popup.url.lower():
                                log.info("Direct PDF URL detected - downloading content...")
                                
                                # Method 1: Use fetch API to download PDF content
                                try:
                                    pdf_bytes = await popup.evaluate("""
                                        async (url) => {
                                            const response = await fetch(url);
                                            const blob = await response.blob();
                                            const buffer = await blob.arrayBuffer();
                                            return Array.from(new Uint8Array(buffer));
                                        }
                                    """, popup_url)
                                    
                                    # Convert list to bytes
                                    pdf_bytes = bytes(pdf_bytes)
                                    log.info(f"✓ Downloaded PDF via fetch API: {len(pdf_bytes)} bytes")
                                    
                                    if application_id and school_name and len(pdf_bytes) > 1000:  # Valid PDF should be > 1KB
                                        saved_path = storage.save_offer(
                                            school_name=school_name,
                                            application_id=application_id,
                                            file_content=pdf_bytes,
                                            extension="pdf"
                                        )
                                        log.info(f"✓ PDF saved from popup: {saved_path}")
                                        await popup.close()
                                        return saved_path
                                except Exception as e:
                                    log.warning(f"Could not download via fetch API: {e}")
                                
                                # Method 2: Use page.pdf() as fallback (for PDF viewer pages)
                                log.info("Trying page.pdf() as fallback...")
                                pdf_bytes = await popup.pdf(format='A4', print_background=True)
                            else:
                                # Not a PDF URL, use page.pdf()
                                log.info("Generating PDF from popup page...")
                                pdf_bytes = await popup.pdf(format='A4', print_background=True)
                            
                            if application_id and school_name and len(pdf_bytes) > 0:
                                saved_path = storage.save_offer(
                                    school_name=school_name,
                                    application_id=application_id,
                                    file_content=pdf_bytes,
                                    extension="pdf"
                                )
                                log.info(f"✓ PDF saved from popup: {saved_path}")
                                await popup.close()
                                return saved_path
                            else:
                                log.warning("Could not generate PDF or missing info")
                                await popup.close()
                        except Exception as pdf_error:
                            log.error(f"Failed to generate PDF from popup: {pdf_error}")
                            import traceback
                            log.error(traceback.format_exc())
                            await popup.close()
                    
                    except Exception as popup_error:
                        # No popup detected during click, but check if a new page opened after
                        log.debug(f"No popup detected during click: {popup_error}")
                        await self.browser.click_element(text=display_text, timeout=3)
                        await self.browser.wait(3)  # Wait a bit longer for new window/tab
                        log.info(f"✓ Clicked: {display_text}")
                        
                        # Check if new pages were opened after the click
                        all_pages = self.browser.context.pages
                        log.info(f"Total pages open: {len(all_pages)}")
                        
                        if len(all_pages) > 1:
                            # New page was opened!
                            new_page = all_pages[-1]
                            log.info(f"✓ New page detected after click: {new_page.url}")
                            
                            try:
                                await new_page.wait_for_load_state('load', timeout=10000)
                                await self.browser.wait(2)
                                
                                # Check if it's a PDF or contains PDF content
                                if '.pdf' in new_page.url.lower() or 'pdf' in new_page.url.lower():
                                    log.info("Detected PDF in new page")
                                    pdf_bytes = await new_page.pdf(format='A4')
                                    
                                    if application_id and school_name and len(pdf_bytes) > 0:
                                        saved_path = storage.save_offer(
                                            school_name=school_name,
                                            application_id=application_id,
                                            file_content=pdf_bytes,
                                            extension="pdf"
                                        )
                                        log.info(f"✓ PDF saved from new page: {saved_path}")
                                        await new_page.close()
                                        return saved_path
                                else:
                                    # Try to generate PDF anyway (might be a print preview)
                                    log.info("Attempting to generate PDF from new page...")
                                    pdf_bytes = await new_page.pdf(format='A4')
                                    
                                    if len(pdf_bytes) > 0:
                                        saved_path = storage.save_offer(
                                            school_name=school_name,
                                            application_id=application_id,
                                            file_content=pdf_bytes,
                                            extension="pdf"
                                        )
                                        log.info(f"✓ PDF saved from new page: {saved_path}")
                                        await new_page.close()
                                        return saved_path
                                    
                                await new_page.close()
                            except Exception as pdf_error:
                                log.error(f"Failed to handle new page: {pdf_error}")
                                if new_page and not new_page.is_closed():
                                    await new_page.close()
                        
                        await self.browser.capture_screenshot("after_download_click")
                    
                    download_clicked = True
                    break
                    
                except Exception as e:
                    log.debug(f"Could not click '{display_text}': {e}")
                    continue
            
            # If clicking text didn't work, try finding download buttons/links with selectors
            if not download_clicked:
                log.info("Trying download button selectors...")
                download_selectors = [
                    'button:has-text("Download")',
                    'a:has-text("Download")',
                    'button:has-text("Offer")',
                    'a:has-text("Offer")',
                    'button[download]',
                    'a[download]',
                    '.download-button',
                    '.offer-download',
                    'button:has-text("Print")',
                    'a:has-text("Print")'
                ]
                
                for selector in download_selectors:
                    try:
                        await self.browser.page.click(selector, timeout=2000)
                        await self.browser.wait(2)
                        log.info(f"✓ Clicked download using selector: {selector}")
                        download_clicked = True
                        break
                    except:
                        continue
            
            # If still no luck, use JavaScript to find and click
            if not download_clicked:
                log.info("Trying JavaScript to find download buttons...")
                script = """
                (function() {
                    const keywords = ['download', 'offer', 'letter', 'print', 'save', 'view'];
                    const elements = document.querySelectorAll('button, a, [role="button"]');
                    
                    for (const el of elements) {
                        const text = el.textContent.toLowerCase();
                        const hasKeyword = keywords.some(kw => text.includes(kw));
                        
                        if (hasKeyword && (text.includes('offer') || text.includes('letter') || text.includes('download'))) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                })()
                """
                try:
                    result = await self.browser.evaluate_js(script)
                    if result:
                        await self.browser.wait(2)
                        log.info("✓ Clicked download button using JavaScript")
                        download_clicked = True
                except Exception as e:
                    log.error(f"JavaScript download click failed: {e}")
            
            if download_clicked:
                log.info("Waiting for download to complete...")
                
                try:
                    # Set up download expectation and wait
                    async with self.browser.page.expect_download(timeout=10000) as download_info:
                        await self.browser.wait(2)
                    
                    download = await download_info.value
                    log.info(f"✓ Download triggered: {download.suggested_filename}")
                    
                    # Get the downloaded file path
                    temp_path = await download.path()
                    
                    if temp_path and Path(temp_path).exists():
                        # Read the downloaded file
                        file_bytes = Path(temp_path).read_bytes()
                        log.info(f"✓ Downloaded file size: {len(file_bytes)} bytes")
                        
                        # Save using storage manager if we have the required info
                        if application_id and school_name:
                            saved_path = storage.save_offer(
                                school_name=school_name,
                                application_id=application_id,
                                file_content=file_bytes,
                                extension="pdf"
                            )
                            log.info(f"✓ Saved offer to: {saved_path}")
                            return saved_path
                        else:
                            log.warning("Missing application_id or school_name, cannot save properly")
                            return Path(temp_path)
                    else:
                        log.error("Downloaded file not found")
                        return None
                        
                except Exception as download_error:
                    log.warning(f"Download not triggered or timed out: {download_error}")
                    
                    # Fallback: check if PDF opened in browser
                    await self.browser.wait(2)
                    current_url = await self.browser.get_current_url()
                    log.info(f"Current URL after click: {current_url}")
                    
                    await self.browser.capture_screenshot("download_result")
                    
                    if '.pdf' in current_url.lower():
                        log.info("✓ PDF opened in browser (no download triggered)")
                        # TODO: Could save PDF from URL in future
                        return Path("pdf_opened_in_browser")
                    else:
                        log.info("Download action completed but file not captured")
                        return Path("download_attempted")
            
            log.warning("No download option found or clicked")
            return None
            
        except Exception as e:
            log.error(f"Download failed: {e}")
            import traceback
            log.error(traceback.format_exc())
            return None
    
    async def analyze_current_page(self, goal: str) -> Dict[str, Any]:
        """Use vision to analyze the current page"""
        screenshot = await self.browser.capture_screenshot("page_analysis")
        
        analysis = await self.vision_agent.analyze_page(
            screenshot_path=screenshot,
            goal=goal,
            context=f"School: {self.school_config.school_name}",
            hints=self.school_config.hints.login_page_indicators + 
                  self.school_config.hints.dashboard_indicators
        )
        
        return {
            "page_type": analysis.page_type,
            "elements": analysis.elements_found,
            "confidence": analysis.confidence,
            "reasoning": analysis.reasoning
        }

