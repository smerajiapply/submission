"""Main browser agent with LLM decision-making"""

from typing import Optional, Dict, Any, List
from pathlib import Path
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from src.automation.playwright_manager import PlaywrightManager
from src.agents.tools import create_browser_tools
from src.agents.vision_agent import VisionAgent
from src.models.schemas import WorkflowState, SchoolConfig
from src.config.base_config import settings
from src.utils.logger import log


class BrowserAgent:
    """LLM-powered browser automation agent with ReAct reasoning"""
    
    def __init__(
        self,
        browser: PlaywrightManager,
        school_config: SchoolConfig
    ):
        self.browser = browser
        self.school_config = school_config
        self.vision_agent = VisionAgent()
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Create LLM with Google Gemini
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=0.1,
            google_api_key=settings.gemini_api_key,
            convert_system_message_to_human=True
        )
        
        log.info(f"Browser agent initialized with {settings.gemini_model}")
        
        # Create tools
        self.tools = create_browser_tools(browser)
        
        # Create agent
        self.agent_executor = self._create_agent()
    
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent with tools"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=15,
            handle_parsing_errors=True
        )
        
        return agent_executor
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent"""
        
        return f"""You are an expert browser automation agent helping to navigate a school portal.

SCHOOL: {self.school_config.school_name}
PORTAL URL: {self.school_config.portal_url}

CAPABILITIES:
You have access to browser automation tools including:
- navigate: Go to a URL
- click: Click elements by CSS selector or visible text
- type: Type text into input fields
- wait: Wait for page to load or elements to appear
- scroll: Scroll the page
- get_page_text: Get visible text from the page
- screenshot: Take a screenshot for debugging
- go_back: Navigate back to previous page

APPROACH:
1. Think step-by-step about what you need to do
2. ALWAYS use get_page_text FIRST to understand what's on the current page
3. Take actions one at a time
4. After each action, verify it worked by checking the page content
5. If something doesn't work, try an alternative approach
6. Be patient - wait after actions that trigger page loads
7. When clicking, prefer using visible text over CSS selectors

HINTS FOR THIS SCHOOL:
{self._format_hints()}

IMPORTANT RULES:
- Always get_page_text first to see what's on the page
- Use text-based clicking when possible (more reliable than selectors)
- Wait after clicking buttons that trigger navigation
- If login fails, check for error messages
- Be methodical and don't rush

Your goal is to successfully complete the assigned task."""
    
    def _format_hints(self) -> str:
        """Format school-specific hints"""
        hints = []
        
        if self.school_config.hints.login_page_indicators:
            hints.append(f"Login page indicators: {', '.join(self.school_config.hints.login_page_indicators)}")
        
        if self.school_config.hints.dashboard_indicators:
            hints.append(f"Dashboard indicators: {', '.join(self.school_config.hints.dashboard_indicators)}")
        
        if self.school_config.hints.application_status_indicators:
            hints.append(f"Application status indicators: {', '.join(self.school_config.hints.application_status_indicators)}")
        
        if self.school_config.selectors.username_field:
            hints.append(f"Username field selector: {self.school_config.selectors.username_field}")
        
        if self.school_config.selectors.password_field:
            hints.append(f"Password field selector: {self.school_config.selectors.password_field}")
        
        return "\n".join(hints) if hints else "No specific hints available"
    
    async def execute_task(self, task: str, max_retries: int = 2) -> Dict[str, Any]:
        """Execute a task with the agent"""
        
        log.info(f"Executing task: {task}")
        
        for attempt in range(max_retries + 1):
            try:
                # Take initial screenshot
                screenshot = await self.browser.capture_screenshot("before_task")
                
                # Run the agent
                result = await self.agent_executor.ainvoke({
                    "input": task
                })
                
                log.info(f"Task completed: {result.get('output', 'No output')}")
                
                return {
                    "success": True,
                    "output": result.get("output", ""),
                    "intermediate_steps": result.get("intermediate_steps", [])
                }
                
            except Exception as e:
                log.error(f"Task execution failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                
                if attempt < max_retries:
                    log.info("Retrying task...")
                    await self.browser.capture_screenshot(f"error_attempt_{attempt}")
                else:
                    return {
                        "success": False,
                        "error": str(e),
                        "output": ""
                    }
    
    async def login(self, username: str, password: str) -> bool:
        """Execute login workflow"""
        
        task = f"""Navigate to the portal and log in with the provided credentials.

Steps:
1. Navigate to {self.school_config.portal_url}
2. Wait for the page to load
3. Get the page text to see what's available
4. Find the username field and type: {username}
5. Find the password field and type: {password}
6. Find and click the login/submit button
7. Wait for the dashboard to load
8. Verify login was successful by checking the page content

Report success or failure clearly."""
        
        result = await self.execute_task(task)
        return result.get("success", False)
    
    async def find_application(
        self,
        application_id: Optional[str] = None,
        student_name: Optional[str] = None,
        student_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Find a specific application"""
        
        search_criteria = []
        if application_id:
            search_criteria.append(f"Application ID: {application_id}")
        if student_name:
            search_criteria.append(f"Student Name: {student_name}")
        if student_email:
            search_criteria.append(f"Student Email: {student_email}")
        
        criteria_text = "\n".join(search_criteria)
        
        task = f"""Find the application with these details:
{criteria_text}

Steps:
1. Get the current page text to see what's available
2. Look for a link or button to view applications (check hints)
3. Navigate to the applications page
4. Search for or filter to find the specific application
5. Click on the application to view details
6. Get the page text to extract application status

Report what you found."""
        
        result = await self.execute_task(task)
        
        if result.get("success"):
            # Try to extract status from the output using vision
            screenshot = await self.browser.capture_screenshot("application_found")
            status_text = await self.vision_agent.extract_information(
                screenshot,
                "Application status (e.g., Pending, Under Review, Accepted, Rejected, Offer Ready)"
            )
            
            result["status_text"] = status_text
        
        return result
    
    async def download_offer(self) -> Optional[Path]:
        """Download the offer letter if available"""
        
        task = """Look for and download the offer letter.

Steps:
1. Get the current page text
2. Look for a download button, link, or "Offer Letter" section
3. Click the download button/link
4. Verify the download started

Report the outcome."""
        
        result = await self.execute_task(task)
        
        if result.get("success"):
            # Try to download the file
            # Note: This is a simplified approach
            # In production, you'd want more sophisticated download handling
            log.info("Download task completed by agent")
        
        return result
    
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
            "reasoning": analysis.reasoning,
            "suggested_action": analysis.suggested_action,
            "suggested_target": analysis.suggested_target
        }

