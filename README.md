# Application Portal Automation - Config-Driven Architecture

## Summary

This system automates student application status checks and offer letter downloads from school portals using an LLM-based agentic approach.

## Key Features

### ✅ Config-Driven Multi-Agent Architecture (V2)
- **LoginAgent**: Handles authentication workflows
- **NavigationAgent**: Navigates to applications
- **DownloadAgent**: Downloads offer letters
- **ActionExecutor**: Generic action interpreter for all agents
- **Step-by-step YAML configs**: All workflows defined in config files

### ✅ Backward Compatibility (V1)
- Maintains support for old SimpleBrowserAgent approach
- Automatic detection of config format

### ✅ Production Features
- Screenshot capture at each step
- Detailed logging
- Retry logic with exponential backoff
- Vision-based fallback when selectors fail
- Support for different UI patterns (dropdown, modal, tabs)

## Quick Start

### 1. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure Environment

Create `.env` file:
```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash-exp
HEADLESS=false
```

### 3. Check Application

```bash
python run.py check-application \
  --school norquest \
  --username "your_username" \
  --password "your_password" \
  --app-id "380631"
```

## Configuration Guide

### V2 Config Format (Recommended)

Schools are configured using YAML files with step-by-step workflows:

```yaml
school_name: SchoolName
portal_url: https://portal.example.com/login

# Login workflow
login:
  steps:
    - action: find_and_fill
      target_type: input_field
      selectors: ['input[name="username"]']
      hints: ['Username', 'Email']
      value: '{username}'
      description: 'Fill username field'
    
    - action: find_and_click
      target_type: button
      selectors: ['button[type="submit"]']
      hints: ['Sign in', 'Login']
      description: 'Click login button'
  
  max_retries: 3
  retry_delay: 2

# Navigation workflow
navigation:
  steps:
    - action: find_and_click
      target_type: dropdown
      hints: ['Applications']
      description: 'Open applications menu'
    
    - action: find_and_click
      hints: ['{application_id}']
      opens_new_tab: true
      description: 'Click application ID'
  
  max_retries: 3
  retry_delay: 2

# Download workflow
download:
  steps:
    - action: find_and_click
      hints: ['Print Offer', 'Download Offer']
      triggers_download: true
      description: 'Trigger offer download'
  
  max_retries: 3
  retry_delay: 2

# Status detection patterns
status_detection:
  offer_ready: ['Conditional offer', 'Offer ready']
  accepted: ['Accepted', 'Enrolled']
  rejected: ['Rejected', 'Declined']
  pending: ['Pending', 'Under review']
```

### Supported Actions

| Action | Description | Key Parameters |
|--------|-------------|----------------|
| `find_and_fill` | Find input and type value | `selectors`, `hints`, `value` |
| `find_and_click` | Find element and click | `selectors`, `hints`, `opens_new_tab`, `triggers_download` |
| `wait_for_load` | Wait for page load | `timeout` |
| `wait_for_navigation` | Wait and verify navigation | `success_indicators` |
| `capture_download` | Capture file download | `expected_extension` |
| `press_key` | Press keyboard key | `value` |
| `scroll` | Scroll to bottom | - |
| `wait` | Simple wait | `timeout` |

### Parameter Substitution

Use `{parameter}` in config values for runtime substitution:
- `{username}` - Login username
- `{password}` - Login password
- `{application_id}` - Application ID
- `{student_name}` - Student name
- `{student_email}` - Student email

## Architecture

```
run.py
  └─> WorkflowEngine
        ├─> Config Detection (V1 or V2)
        │
        ├─> V2 Path (Config-Driven)
        │     ├─> LoginAgent → ActionExecutor
        │     ├─> NavigationAgent → ActionExecutor  
        │     └─> DownloadAgent → ActionExecutor
        │
        └─> V1 Path (Legacy)
              └─> SimpleBrowserAgent (backward compat)

ActionExecutor
  ├─> Try selectors
  ├─> Try hints with Playwright
  └─> Fallback to Vision (if needed)
```

## Onboarding New Schools

1. Create YAML config file: `src/config/schools/school_name.yaml`
2. Define login steps (fill username, password, click submit)
3. Define navigation steps (reach applications page)
4. Define download steps (trigger PDF download)
5. Add status detection patterns
6. Test: `python run.py check-application --school school_name ...`

## Files Structure

```
src/
├── agents/
│   ├── login_agent.py          # Handles authentication
│   ├── navigation_agent.py     # Navigates to applications
│   ├── download_agent.py       # Downloads offers
│   ├── action_executor.py      # Generic action interpreter
│   ├── vision_agent.py         # Gemini Vision integration
│   └── simple_browser_agent.py # Legacy V1 agent
├── automation/
│   ├── playwright_manager.py   # Browser control
│   └── workflows.py            # Workflow orchestration
├── config/
│   ├── base_config.py          # Settings
│   └── schools/                # School configs (YAML)
│       ├── norquest.yaml
│       └── ocas.yaml
├── models/
│   ├── schemas.py              # Core data models
│   └── config_schemas.py       # V2 config models
└── utils/
    ├── logger.py               # Logging
    └── storage.py              # File storage
```

## Benefits of Config-Driven Approach

1. **Easy Onboarding**: New schools via YAML only, no code changes
2. **Maintainable**: Clear separation of concerns
3. **Testable**: Each agent can be tested independently
4. **Debuggable**: Detailed logging at each step
5. **Scalable**: Easy to add new action types
6. **Cost-effective**: Vision only used as fallback

## Example: Both Schools Working

### NorQuest
- **Login**: Single-step (username + password)
- **Navigation**: Dropdown → View applications → Click ID (opens new tab)
- **Download**: Click "Print Offer" (triggers download)
- **✅ Full PDF downloaded**: 91KB

### OCAS
- **Login**: Two-step (username → next → password → agency selection)
- **Navigation**: Left modal → Offers → Click ID
- **Download**: Click "View Letter" (opens PDF in new tab)
- **✅ Full PDF downloaded**: 117KB

## Future Enhancements

- [ ] Add more action types (switch_iframe, handle_captcha, etc.)
- [ ] Support for MFA/2FA workflows
- [ ] Parallel processing for multiple applications
- [ ] Dashboard for monitoring
- [ ] API endpoints for integration

## Credits

- **LLM**: Google Gemini 2.0 Flash Exp
- **Browser**: Playwright (Chromium)
- **Framework**: LangChain (partial), Custom agents

---

For detailed usage examples, see [USAGE.md](USAGE.md)
