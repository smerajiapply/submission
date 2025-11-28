"""Vision agent for analyzing screenshots using Google Gemini Vision"""

import base64
from typing import Optional, Dict, Any, List
from pathlib import Path
import google.generativeai as genai
from src.config.base_config import settings
from src.utils.logger import log
from src.models.schemas import PageAnalysis, BrowserAction


class VisionAgent:
    """Analyzes screenshots using Google Gemini Vision to understand page layout and suggest actions"""
    
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        log.info(f"Vision agent initialized with {settings.gemini_model}")
    
    def _load_image(self, image_path: Path):
        """Load image for Gemini"""
        from PIL import Image
        return Image.open(image_path)
    
    async def analyze_page(
        self,
        screenshot_path: Path,
        goal: str,
        context: Optional[str] = None,
        hints: Optional[List[str]] = None
    ) -> PageAnalysis:
        """Analyze a screenshot to understand the page and suggest next action"""
        
        try:
            log.info(f"Analyzing screenshot for goal: {goal}")
            
            # Load image
            image = self._load_image(screenshot_path)
            
            # Build prompt
            prompt = self._build_analysis_prompt(goal, context, hints)
            
            # Call Gemini Vision
            response = self.model.generate_content([prompt, image])
            
            # Parse response
            content = response.text
            log.debug(f"Vision analysis result: {content}")
            
            # Extract structured information from response
            analysis = self._parse_analysis(content, goal)
            
            return analysis
            
        except Exception as e:
            log.error(f"Vision analysis failed: {e}")
            # Return default analysis
            return PageAnalysis(
                page_type="unknown",
                elements_found=[],
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}"
            )
    
    def _build_analysis_prompt(
        self,
        goal: str,
        context: Optional[str] = None,
        hints: Optional[List[str]] = None
    ) -> str:
        """Build the analysis prompt"""
        
        prompt = f"""You are a browser automation assistant analyzing a webpage screenshot.

GOAL: {goal}

"""
        
        if context:
            prompt += f"CONTEXT: {context}\n\n"
        
        if hints:
            prompt += f"HINTS (look for these elements): {', '.join(hints)}\n\n"
        
        prompt += """Analyze the screenshot and provide:
1. PAGE TYPE: What type of page is this? (e.g., login page, dashboard, application list, form, etc.)
2. KEY ELEMENTS: What interactive elements do you see? (buttons, input fields, links, tables, etc.)
3. SUGGESTED ACTION: What should we do next to achieve the goal?
4. TARGET: If clicking or typing, provide a specific description of the target element
5. CONFIDENCE: How confident are you? (0.0 to 1.0)
6. REASONING: Explain your analysis

Format your response clearly with these sections."""
        
        return prompt
    
    def _parse_analysis(self, content: str, goal: str) -> PageAnalysis:
        """Parse the LLM response into structured PageAnalysis"""
        
        # Simple parsing - in production, you'd want more robust parsing
        lines = content.lower()
        
        # Detect page type
        page_type = "unknown"
        if "login" in lines or "sign in" in lines:
            page_type = "login"
        elif "dashboard" in lines:
            page_type = "dashboard"
        elif "application" in lines and ("list" in lines or "table" in lines):
            page_type = "application_list"
        elif "form" in lines:
            page_type = "form"
        elif "offer" in lines or "admission" in lines:
            page_type = "offer_page"
        
        # Extract elements (simplified)
        elements_found = []
        if "button" in lines:
            elements_found.append("buttons")
        if "input" in lines or "field" in lines:
            elements_found.append("input_fields")
        if "link" in lines:
            elements_found.append("links")
        if "table" in lines:
            elements_found.append("table")
        if "download" in lines:
            elements_found.append("download_link")
        
        # Suggest action based on page type and goal
        suggested_action = None
        suggested_target = None
        
        if page_type == "login" and "login" in goal.lower():
            suggested_action = BrowserAction.TYPE
            suggested_target = "username and password fields"
        elif "click" in lines:
            suggested_action = BrowserAction.CLICK
        elif "type" in lines or "enter" in lines:
            suggested_action = BrowserAction.TYPE
        elif "download" in goal.lower() and "download" in lines:
            suggested_action = BrowserAction.DOWNLOAD
        
        # Estimate confidence
        confidence = 0.7  # Default
        if "confident" in lines or "clear" in lines:
            confidence = 0.9
        elif "unclear" in lines or "not sure" in lines:
            confidence = 0.3
        
        return PageAnalysis(
            page_type=page_type,
            elements_found=elements_found,
            suggested_action=suggested_action,
            suggested_target=suggested_target,
            confidence=confidence,
            reasoning=content
        )
    
    async def find_element_by_description(
        self,
        screenshot_path: Path,
        element_description: str
    ) -> Optional[Dict[str, Any]]:
        """Find an element on the page by describing what you're looking for"""
        
        try:
            image = self._load_image(screenshot_path)
            
            prompt = f"""Look at this webpage screenshot and find the element that matches this description:
"{element_description}"

Provide:
1. The visible text on or near the element (if any)
2. The type of element (button, link, input, etc.)
3. A CSS selector hint if possible
4. Its approximate location (top/middle/bottom, left/center/right)

Be specific and concise."""
            
            response = self.model.generate_content([prompt, image])
            content = response.text
            log.info(f"Element search result: {content}")
            
            return {
                "description": content,
                "found": "not found" not in content.lower()
            }
            
        except Exception as e:
            log.error(f"Element search failed: {e}")
            return None
    
    async def extract_information(
        self,
        screenshot_path: Path,
        what_to_extract: str
    ) -> str:
        """Extract specific information from a screenshot"""
        
        try:
            image = self._load_image(screenshot_path)
            
            prompt = f"""Look at this screenshot and extract the following information:
{what_to_extract}

Provide only the extracted information, be concise and accurate."""
            
            response = self.model.generate_content([prompt, image])
            content = response.text
            log.info(f"Extracted information: {content}")
            
            return content
            
        except Exception as e:
            log.error(f"Information extraction failed: {e}")
            return ""

