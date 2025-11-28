"""
Configuration schemas for step-by-step workflow definitions.

This module defines Pydantic models for config-driven automation workflows.
Each school's YAML config contains step-by-step instructions for login,
navigation, and download operations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ActionType(str, Enum):
    """Types of actions that can be performed"""
    FIND_AND_CLICK = "find_and_click"
    FIND_AND_FILL = "find_and_fill"
    WAIT_FOR_LOAD = "wait_for_load"
    WAIT_FOR_NAVIGATION = "wait_for_navigation"
    CAPTURE_DOWNLOAD = "capture_download"
    SWITCH_TO_NEW_TAB = "switch_to_new_tab"
    PRESS_KEY = "press_key"
    SCROLL = "scroll"
    WAIT = "wait"


class TargetType(str, Enum):
    """Types of UI elements to interact with"""
    BUTTON = "button"
    INPUT_FIELD = "input_field"
    DROPDOWN = "dropdown"
    MENU_ITEM = "menu_item"
    LINK = "link"
    TEXT = "text"
    ANY = "any"


class ActionStep(BaseModel):
    """
    Represents a single action in a workflow.
    
    Actions are executed sequentially and can use parameters like {username},
    {password}, {application_id} that get substituted at runtime.
    """
    action: ActionType = Field(..., description="Type of action to perform")
    target_type: Optional[TargetType] = Field(None, description="Type of UI element to target")
    selectors: List[str] = Field(default_factory=list, description="CSS/XPath selectors to try in order")
    hints: List[str] = Field(default_factory=list, description="Text hints for finding element (used with vision)")
    value: Optional[str] = Field(None, description="Value to use (supports {param} substitution)")
    timeout: int = Field(default=30, description="Timeout in seconds")
    opens_new_tab: bool = Field(default=False, description="Whether action opens a new tab/window")
    triggers_download: bool = Field(default=False, description="Whether action triggers file download")
    use_javascript: bool = Field(default=False, description="Use JavaScript click instead of native")
    success_indicators: List[str] = Field(default_factory=list, description="Text to verify success")
    expected_extension: Optional[str] = Field(None, description="Expected file extension for downloads")
    description: Optional[str] = Field(None, description="Human-readable description of step")
    optional: bool = Field(default=False, description="Whether step failure should be ignored")
    

class WorkflowConfig(BaseModel):
    """Configuration for a complete workflow (login, navigation, or download)"""
    steps: List[ActionStep] = Field(..., description="Ordered list of steps to execute")
    max_retries: int = Field(default=3, description="Max retries for entire workflow")
    retry_delay: int = Field(default=2, description="Delay between retries in seconds")


class StatusDetectionConfig(BaseModel):
    """Patterns for detecting application status"""
    offer_ready: List[str] = Field(default_factory=list)
    accepted: List[str] = Field(default_factory=list)
    rejected: List[str] = Field(default_factory=list)
    pending: List[str] = Field(default_factory=list)


class SchoolConfigV2(BaseModel):
    """
    Enhanced school configuration with step-by-step workflows.
    
    This replaces the old approach of hard-coded login_type and navigation_type
    with explicit step-by-step instructions.
    """
    school_name: str
    portal_url: str
    
    # Step-by-step workflows
    login: WorkflowConfig = Field(..., description="Login workflow steps")
    navigation: WorkflowConfig = Field(..., description="Navigation workflow steps")
    download: WorkflowConfig = Field(..., description="Download workflow steps")
    
    # Status detection
    status_detection: StatusDetectionConfig = Field(
        default_factory=StatusDetectionConfig,
        description="Patterns for detecting application status"
    )
    
    # General settings
    timeout: int = Field(default=30, description="Default timeout in seconds")
    notes: Optional[str] = Field(None, description="Additional notes about this school")
    
    class Config:
        extra = "allow"  # Allow additional fields for backward compatibility


class ActionContext(BaseModel):
    """Runtime context passed to action executor"""
    username: Optional[str] = None
    password: Optional[str] = None
    application_id: Optional[str] = None
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    school_name: Optional[str] = None
    
    def substitute(self, value: str) -> str:
        """Substitute parameters in value string (e.g., {username} -> actual username)"""
        if not value:
            return value
        
        result = value
        if self.username:
            result = result.replace("{username}", self.username)
        if self.password:
            result = result.replace("{password}", self.password)
        if self.application_id:
            result = result.replace("{application_id}", self.application_id)
        if self.student_name:
            result = result.replace("{student_name}", self.student_name)
        if self.student_email:
            result = result.replace("{student_email}", self.student_email)
        
        return result

