"""Workflow engine with state machine for application checking"""

from typing import Optional, Dict, Any, Union
from pathlib import Path
import yaml
from src.models.schemas import (
    WorkflowState, 
    ApplicationStatus, 
    ApplicationRequest, 
    ApplicationResult,
    SchoolConfig,
    SchoolHints,
    SchoolSelectors
)
from src.models.config_schemas import SchoolConfigV2
from src.automation.playwright_manager import PlaywrightManager
from src.agents.simple_browser_agent import SimpleBrowserAgent
from src.agents.login_agent import LoginAgent
from src.agents.navigation_agent import NavigationAgent
from src.agents.download_agent import DownloadAgent
from src.agents.vision_agent import VisionAgent
from src.config.base_config import settings
from src.utils.logger import log
from src.utils.storage import storage


class WorkflowEngine:
    """Orchestrates the complete workflow for checking applications"""
    
    def __init__(self):
        self.state = WorkflowState.INIT
        self.browser: Optional[PlaywrightManager] = None
        self.agent: Optional[SimpleBrowserAgent] = None
        self.school_config: Optional[Union[SchoolConfig, SchoolConfigV2]] = None
        self.use_v2 = False  # Flag to determine which config version
    
    def load_school_config(self, school_name: str) -> Union[SchoolConfig, SchoolConfigV2]:
        """Load school configuration from YAML file"""
        
        config_path = settings.config_dir / f"{school_name}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"School configuration not found: {config_path}\n"
                f"Please create a config file for {school_name}"
            )
        
        log.info(f"Loading school config from: {config_path}")
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Detect config version: V2 has 'login', 'navigation', 'download' keys
        if 'login' in config_data and 'navigation' in config_data and 'download' in config_data:
            log.info("Detected V2 config format (step-by-step workflows)")
            self.use_v2 = True
            school_config = SchoolConfigV2(**config_data)
        else:
            log.info("Detected V1 config format (backward compatibility)")
            self.use_v2 = False
            school_config = SchoolConfig(**config_data)
        
        log.info(f"Loaded config for: {school_config.school_name}")
        
        return school_config
    
    async def execute(self, request: ApplicationRequest) -> ApplicationResult:
        """Execute the complete workflow"""
        
        log.info(f"Starting workflow for school: {request.school}")
        
        try:
            # INIT: Load configuration
            self.state = WorkflowState.INIT
            self.school_config = self.load_school_config(request.school)
            
            # Start browser
            self.browser = PlaywrightManager(headless=settings.headless)
            await self.browser.start()
            
            # Route to appropriate workflow based on config version
            if self.use_v2:
                return await self._execute_v2(request)
            else:
                return await self._execute_v1(request)
            
        except Exception as e:
            log.error(f"Workflow failed: {e}")
            import traceback
            log.error(traceback.format_exc())
            self.state = WorkflowState.FAILED
            
            return ApplicationResult(
                success=False,
                status=ApplicationStatus.UNKNOWN,
                message=f"Workflow failed: {str(e)}"
            )
        
        finally:
            # Cleanup
            if self.browser:
                await self.browser.close()
    
    async def _execute_v2(self, request: ApplicationRequest) -> ApplicationResult:
        """Execute workflow using V2 config-driven multi-agent approach"""
        log.info("=== Using V2 Config-Driven Agents ===")
        
        # Create vision agent
        vision_agent = VisionAgent()
        
        # Create specialized agents
        login_agent = LoginAgent(self.browser, vision_agent)
        navigation_agent = NavigationAgent(self.browser, vision_agent)
        download_agent = DownloadAgent(self.browser, vision_agent)
        
        # LOGIN
        self.state = WorkflowState.LOGIN
        log.info("State: LOGIN")
        login_success = await login_agent.execute_login(
            self.school_config,
            request.username,
            request.password
        )
        
        if not login_success:
            return ApplicationResult(
                success=False,
                status=ApplicationStatus.UNKNOWN,
                message="Login failed"
            )
        
        log.info("✓ Login successful!")
        
        # NAVIGATE & FIND_APPLICATION
        self.state = WorkflowState.FIND_APPLICATION
        log.info("State: FIND_APPLICATION")
        
        nav_result = await navigation_agent.navigate_to_application(
            self.school_config,
            application_id=request.application_id,
            student_name=request.student_name,
            student_email=request.student_email
        )
        
        if not nav_result.get("success"):
            return ApplicationResult(
                success=False,
                status=ApplicationStatus.UNKNOWN,
                message="Navigation failed"
            )
        
        log.info("✓ Navigation successful!")
        
        # CHECK_STATUS
        self.state = WorkflowState.CHECK_STATUS
        log.info("State: CHECK_STATUS")
        
        status = nav_result.get("found_status", ApplicationStatus.UNKNOWN)
        status_text = nav_result.get("status_text", "")
        
        log.info(f"Application status: {status}")
        
        # DOWNLOAD
        offer_downloaded = False
        offer_path = None
        
        if status == ApplicationStatus.OFFER_READY or status == ApplicationStatus.ACCEPTED:
            self.state = WorkflowState.DOWNLOAD
            log.info("State: DOWNLOAD")
            
            download_path = await download_agent.download_offer(
                self.school_config,
                request.application_id
            )
            
            if download_path:
                log.info(f"✓ Offer downloaded: {download_path}")
                offer_downloaded = True
                offer_path = download_path
        
        # COMPLETE
        self.state = WorkflowState.COMPLETE
        log.info("State: COMPLETE")
        
        # Save metadata
        metadata = {
            "school": request.school,
            "application_id": request.application_id,
            "student_name": request.student_name,
            "status": status.value if status else "unknown",
            "status_text": status_text,
            "offer_downloaded": offer_downloaded
        }
        
        if request.application_id:
            storage.save_metadata(
                self.school_config.school_name,
                request.application_id,
                metadata
            )
        
        return ApplicationResult(
            success=True,
            status=status,
            offer_downloaded=offer_downloaded,
            offer_path=str(offer_path) if offer_path else None,
            message=f"Successfully checked application. Status: {status.value if status else 'unknown'}",
            metadata=metadata
        )
    
    async def _execute_v1(self, request: ApplicationRequest) -> ApplicationResult:
        """Execute workflow using V1 SimpleBrowserAgent (backward compatibility)"""
        log.info("=== Using V1 SimpleBrowserAgent (Legacy) ===")
        
        # Create agent
        self.agent = SimpleBrowserAgent(self.browser, self.school_config)
        
        # LOGIN: Authenticate
        self.state = WorkflowState.LOGIN
        log.info("State: LOGIN")
        login_success = await self.agent.login(request.username, request.password)
        
        if not login_success:
            return ApplicationResult(
                success=False,
                status=ApplicationStatus.UNKNOWN,
                message="Login failed"
            )
        
        log.info("Login successful!")
        
        # NAVIGATE & FIND_APPLICATION: Locate the application
        self.state = WorkflowState.FIND_APPLICATION
        log.info("State: FIND_APPLICATION")
        
        find_result = await self.agent.find_application(
            application_id=request.application_id,
            student_name=request.student_name,
            student_email=request.student_email
        )
        
        if not find_result.get("success"):
            return ApplicationResult(
                success=False,
                status=ApplicationStatus.UNKNOWN,
                message="Could not find application"
            )
        
        # CHECK_STATUS: Extract status
        self.state = WorkflowState.CHECK_STATUS
        log.info("State: CHECK_STATUS")
        
        status_text = find_result.get("status_text", "").lower()
        status = self._parse_status(status_text)
        
        log.info(f"Application status: {status}")
        
        # DOWNLOAD: Try to download offer if available
        offer_downloaded = False
        offer_path = None
        
        if status == ApplicationStatus.OFFER_READY or "offer" in status_text or "accepted" in status_text:
            self.state = WorkflowState.DOWNLOAD
            log.info("State: DOWNLOAD")
            
            download_result = await self.agent.download_offer(
                application_id=request.application_id,
                school_name=self.school_config.school_name
            )
            
            if download_result:
                # Check if it's a Path object or dict
                if isinstance(download_result, Path):
                    log.info(f"Offer downloaded successfully: {download_result}")
                    offer_downloaded = True
                    offer_path = download_result
                elif isinstance(download_result, dict) and download_result.get("success"):
                    log.info("Offer download successful")
                    offer_downloaded = True
        
        # COMPLETE
        self.state = WorkflowState.COMPLETE
        log.info("State: COMPLETE")
        
        # Save metadata
        metadata = {
            "school": request.school,
            "application_id": request.application_id,
            "student_name": request.student_name,
            "status": status.value,
            "status_text": status_text,
            "offer_downloaded": offer_downloaded
        }
        
        if request.application_id:
            storage.save_metadata(
                self.school_config.school_name,
                request.application_id,
                metadata
            )
        
        return ApplicationResult(
            success=True,
            status=status,
            offer_downloaded=offer_downloaded,
            offer_path=str(offer_path) if offer_path else None,
            message=f"Successfully checked application. Status: {status.value}",
            metadata=metadata
        )
    
    def _parse_status(self, status_text: str) -> ApplicationStatus:
        """Parse status text into ApplicationStatus enum"""
        
        status_text = status_text.lower()
        
        if "accepted" in status_text or "admitted" in status_text:
            return ApplicationStatus.ACCEPTED
        elif "rejected" in status_text or "denied" in status_text:
            return ApplicationStatus.REJECTED
        elif "waitlist" in status_text:
            return ApplicationStatus.WAITLISTED
        elif "offer" in status_text or "admission letter" in status_text:
            return ApplicationStatus.OFFER_READY
        elif "review" in status_text or "reviewing" in status_text:
            return ApplicationStatus.UNDER_REVIEW
        elif "pending" in status_text or "submitted" in status_text:
            return ApplicationStatus.PENDING
        else:
            return ApplicationStatus.UNKNOWN
    
    async def onboard_school(
        self,
        school_name: str,
        portal_url: str,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """Interactive onboarding workflow for a new school"""
        
        log.info(f"Starting onboarding for: {school_name}")
        
        try:
            # Create minimal config
            config_data = {
                "school_name": school_name,
                "portal_url": portal_url,
                "hints": {
                    "login_page_indicators": ["Sign in", "Login", "Username"],
                    "dashboard_indicators": ["Dashboard", "Applications"],
                    "application_status_indicators": ["Status", "Decision"],
                    "offer_indicators": ["Offer", "Download", "Admission Letter"]
                },
                "selectors": {},
                "timeout": 30,
                "notes": f"Auto-generated config during onboarding"
            }
            
            # Save config
            config_path = settings.config_dir / f"{school_name.lower().replace(' ', '_')}.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
            
            log.info(f"Created config file: {config_path}")
            
            # Test the config with a test run
            self.school_config = SchoolConfig(**config_data)
            
            self.browser = PlaywrightManager(headless=False)  # Visible for onboarding
            await self.browser.start()
            
            self.agent = SimpleBrowserAgent(self.browser, self.school_config)
            
            # Test login
            login_success = await self.agent.login(username, password)
            
            if login_success:
                log.info("✓ Login successful!")
                
                # Analyze dashboard
                analysis = await self.agent.analyze_current_page("Understand the dashboard layout")
                
                log.info(f"Dashboard analysis: {analysis}")
                
                return {
                    "success": True,
                    "config_path": str(config_path),
                    "message": f"Successfully onboarded {school_name}",
                    "dashboard_analysis": analysis
                }
            else:
                return {
                    "success": False,
                    "message": "Login failed during onboarding",
                    "config_path": str(config_path)
                }
        
        except Exception as e:
            log.error(f"Onboarding failed: {e}")
            return {
                "success": False,
                "message": f"Onboarding failed: {str(e)}"
            }
        
        finally:
            if self.browser:
                await self.browser.close()

