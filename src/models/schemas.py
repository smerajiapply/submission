"""Pydantic models for data validation and configuration"""

from enum import Enum
from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class WorkflowState(str, Enum):
    """Workflow execution states"""
    INIT = "init"
    LOGIN = "login"
    NAVIGATE = "navigate"
    FIND_APPLICATION = "find_application"
    CHECK_STATUS = "check_status"
    DOWNLOAD = "download"
    COMPLETE = "complete"
    FAILED = "failed"


class ApplicationStatus(str, Enum):
    """Application status types"""
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WAITLISTED = "waitlisted"
    OFFER_READY = "offer_ready"
    UNKNOWN = "unknown"


class BrowserAction(str, Enum):
    """Available browser actions"""
    CLICK = "click"
    TYPE = "type"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    DOWNLOAD = "download"
    GO_BACK = "go_back"


class SchoolSelectors(BaseModel):
    """Optional CSS selectors for common elements"""
    username_field: Optional[str] = None
    password_field: Optional[str] = None
    login_button: Optional[str] = None
    application_list: Optional[str] = None
    application_status: Optional[str] = None
    offer_download: Optional[str] = None


class SchoolHints(BaseModel):
    """Hints to help the agent navigate the portal"""
    login_page_indicators: List[str] = Field(default_factory=list)
    dashboard_indicators: List[str] = Field(default_factory=list)
    application_status_indicators: List[str] = Field(default_factory=list)
    offer_indicators: List[str] = Field(default_factory=list)


class SchoolConfig(BaseModel):
    """Configuration for a specific school portal"""
    school_name: str
    portal_url: str
    
    # Behavior configuration - determines which methods to use
    login_type: str = Field(default="single_step", description="Login flow type: 'single_step' or 'two_step'")
    navigation_type: str = Field(default="dropdown", description="Navigation UI type: 'dropdown' or 'left_modal'")
    
    hints: SchoolHints = Field(default_factory=SchoolHints)
    selectors: SchoolSelectors = Field(default_factory=SchoolSelectors)
    timeout: int = Field(default=30, description="Timeout in seconds")
    notes: Optional[str] = None


class ApplicationRequest(BaseModel):
    """Request to check an application"""
    school: str
    username: str
    password: str
    application_id: Optional[str] = None
    student_name: Optional[str] = None
    student_email: Optional[str] = None


class ApplicationResult(BaseModel):
    """Result of application check"""
    success: bool
    status: ApplicationStatus
    offer_downloaded: bool = False
    offer_path: Optional[str] = None
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class ActionResult(BaseModel):
    """Result of a browser action"""
    success: bool
    action: BrowserAction
    message: str
    screenshot_path: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class PageAnalysis(BaseModel):
    """LLM analysis of a page"""
    page_type: str
    elements_found: List[str]
    suggested_action: Optional[BrowserAction] = None
    suggested_target: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


