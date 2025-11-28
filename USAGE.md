# Usage Guide

## Quick Start

### 1. Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up environment
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 2. Test Your Setup

```bash
python run.py test-setup
```

This will verify:
- Python version (3.11+)
- OpenAI API key is configured
- Directories are created
- Playwright is installed

### 3. Onboard Your First School

```bash
python run.py onboard \
  --school-name "Example University" \
  --url "https://portal.example.edu" \
  --username "your_username" \
  --password "your_password"
```

This will:
- Create a config file in `src/config/schools/`
- Test login to verify credentials
- Analyze the dashboard layout
- Provide recommendations for refinement

### 4. Check an Application

```bash
python run.py check-application \
  --school example_university \
  --username your_username \
  --password your_password \
  --app-id 12345 \
  --student-name "John Doe" \
  --student-email "john@example.com"
```

The system will:
1. Log into the portal
2. Navigate to applications
3. Find the specific application
4. Extract the status
5. Download offer letter if available
6. Save all artifacts to `outputs/`

## Available Commands

### check-application
Check the status of a student application

Required options:
- `--school`: School identifier (matches config filename)
- `--username`: Portal login username
- `--password`: Portal login password

At least one of:
- `--app-id`: Application ID number
- `--student-name`: Student's full name
- `--student-email`: Student's email address

### onboard
Onboard a new school portal

Required options:
- `--school-name`: Full name of the school
- `--url`: Portal URL
- `--username`: Test username
- `--password`: Test password

### list-schools
List all configured schools

```bash
python run.py list-schools
```

### show-config
Display configuration for a specific school

```bash
python run.py show-config --school example_university
```

### test-setup
Verify environment configuration

```bash
python run.py test-setup
```

## Configuration Files

School configuration files are stored in `src/config/schools/` as YAML files.

Example structure:

```yaml
school_name: "Example University"
portal_url: "https://portal.example.edu"
timeout: 30

hints:
  login_page_indicators:
    - "Sign in"
    - "Login"
  dashboard_indicators:
    - "Dashboard"
    - "Applications"
  application_status_indicators:
    - "Status"
    - "Decision"
  offer_indicators:
    - "Offer Letter"
    - "Download"

selectors:
  # Optional - agent will discover if not provided
  username_field: "input[name='username']"
  password_field: "input[name='password']"

notes: |
  Additional notes about this school's portal
```

## Output Files

All outputs are saved to the `outputs/` directory:

### Offer Letters
- Location: `outputs/offers/{school_name}/{app_id}_{timestamp}.pdf`
- Includes downloaded offer letters

### Metadata
- Location: `outputs/offers/{school_name}/{app_id}_{timestamp}_metadata.json`
- Contains application status, timestamps, and other metadata

### Logs
- Location: `outputs/logs/automation.log`
- Detailed execution logs with debugging information

### Screenshots
- Location: `outputs/logs/screenshots/`
- Screenshots taken at each step for debugging and verification

## Tips for Success

### 1. Start with Headful Mode
For your first test with a new school, use headful mode to see what's happening:

```python
# In .env file
HEADLESS=false
```

### 2. Review Screenshots
After each run, check the screenshots in `outputs/logs/screenshots/` to understand what the agent saw and did.

### 3. Refine Configuration
After the first run, you can refine the config file:
- Add more specific selectors if the agent struggled to find elements
- Update hints based on actual page content
- Adjust timeout if pages load slowly

### 4. Test Incrementally
Test each part of the workflow:
1. First, just test login
2. Then test finding applications
3. Finally test the complete workflow with download

### 5. Monitor Logs
Watch the logs in real-time:

```bash
tail -f outputs/logs/automation.log
```

## Troubleshooting

### Login Fails
- Verify credentials are correct
- Check if portal has CAPTCHA (not currently supported)
- Review login page screenshot
- Add more specific selectors for username/password fields

### Application Not Found
- Verify the application ID/name/email is correct
- Check if applications are in a different section
- Add navigation hints to config file
- Review page screenshots to see where agent got stuck

### Download Fails
- Check if offer is actually available
- Verify download button/link is visible
- May need to add specific selector for download button

### Timeout Errors
- Increase timeout in config file
- Check internet connection
- Portal may be slow - add wait steps

## Advanced Usage

### Custom LLM Model
Edit `src/agents/browser_agent.py` to use a different model:

```python
self.llm = ChatOpenAI(
    model="gpt-4-turbo-preview",  # or another model
    temperature=0.1,
)
```

### Batch Processing
Create a script to process multiple applications:

```python
import asyncio
from src.automation.workflows import WorkflowEngine
from src.models.schemas import ApplicationRequest

async def process_batch(applications):
    engine = WorkflowEngine()
    results = []
    for app in applications:
        request = ApplicationRequest(**app)
        result = await engine.execute(request)
        results.append(result)
    return results
```

### Custom Workflows
Extend the `WorkflowEngine` class to add custom steps or modify behavior.

## Next Steps

After successfully testing with one school:

1. Document school-specific quirks in the config `notes` field
2. Set up monitoring for production use
3. Create batch processing scripts for multiple applications
4. Add error notifications (email, Slack, etc.)
5. Consider adding support for MFA if needed

## Support

For issues or questions:
1. Check the logs in `outputs/logs/`
2. Review screenshots to see what happened
3. Verify configuration is correct
4. Test with headful mode to see browser actions


