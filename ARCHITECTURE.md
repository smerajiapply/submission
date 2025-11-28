# School Portal Automation System - Technical Summary

## Overview

An LLM-powered automation system that logs into school portals, checks application status, and downloads offer letters. Built with a **config-driven architecture** where all school-specific logic lives in YAML files - no code changes needed to onboard new schools.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  YAML Config    │────▶│  V2 Agents       │────▶│  Playwright     │
│  (per school)   │     │  (generic)       │     │  (browser)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Gemini Vision   │
                        │  (fallback)      │
                        └──────────────────┘
```

### Core Components

| Component | Purpose |
|-----------|---------|
| `ActionExecutor` | Generic action interpreter - handles clicks, fills, waits, downloads |
| `LoginAgent` | Executes login steps from config |
| `NavigationAgent` | Navigates to application, extracts status |
| `DownloadAgent` | Downloads offer letters (direct or PDF-in-new-tab) |
| `VisionAgent` | Gemini Vision for page analysis when selectors fail |

## Config-Driven Approach

Each school has a YAML config with step-by-step instructions:

```yaml
# src/config/schools/norquest.yaml
school_name: NorQuest
portal_url: https://norquest.vasuniverse.com/auth/signin

login:
  steps:
    - action: find_and_fill
      selectors: ['input[id="username"]']
      hints: ['Username']
      value: '{username}'
    - action: find_and_fill
      selectors: ['input[type="password"]']
      value: '{password}'
    - action: find_and_click
      hints: ['Sign in']
    - action: wait_for_load

navigation:
  steps:
    - action: find_and_click
      hints: ['Applications']
      use_javascript: true  # For Angular Material
    - action: find_and_click
      hints: ['View applications']
    - action: find_and_click
      hints: ['{application_id}']
      opens_new_tab: true

download:
  steps:
    - action: find_and_click
      hints: ['Print Offer']
      triggers_download: true
```

## Supported Action Types

| Action | Description |
|--------|-------------|
| `find_and_fill` | Fill input fields (username, password) |
| `find_and_click` | Click buttons, links, menu items |
| `wait_for_load` | Wait for page to load |
| `wait` | Fixed delay (for dropdowns, modals) |

### Special Flags
- `use_javascript: true` - For Angular Material / complex SPAs
- `opens_new_tab: true` - Handles popup windows
- `triggers_download: true` - Captures file downloads
- `optional: true` - Continue if step fails

## Running the System

```bash
# Check application and download offer
python run.py check-application \
  --school norquest \
  --app-id 380631 \
  --username "user@email.com" \
  --password "password"

# Onboard new school (creates template config)
python run.py onboard \
  --school "NewSchool" \
  --url "https://portal.newschool.edu" \
  --username "user" \
  --password "pass"
```

## Currently Onboarded Schools

| School | Login Type | Navigation | Download |
|--------|------------|------------|----------|
| **NorQuest** | Single-step | Angular Material dropdown | Async download with modal |
| **OCAS** | Two-step + agency selection | Left menu | PDF opens in new tab |

## Onboarding a New School (4-6 hours)

1. **Create config file**: `src/config/schools/newschool.yaml`
2. **Define login steps**: Inspect login page, add selectors/hints
3. **Define navigation steps**: Path to application list → application details
4. **Define download steps**: How to trigger offer download
5. **Test and iterate**: Run, check logs/screenshots, adjust config

## Key Benefits

- ✅ **No code changes** to add new schools
- ✅ **Handles complex UIs** (Angular Material, SPAs, overlays)
- ✅ **Automatic fallbacks** (selectors → hints → JavaScript → Vision AI)
- ✅ **Robust downloads** (direct files, PDFs in new tabs, async with modals)
- ✅ **Full audit trail** (screenshots, logs, metadata)

## File Structure

```
src/
├── config/schools/          # School YAML configs
│   ├── norquest.yaml
│   └── ocas.yaml
├── agents/                  # V2 generic agents
│   ├── action_executor.py   # Core action interpreter
│   ├── login_agent.py
│   ├── navigation_agent.py
│   ├── download_agent.py
│   └── vision_agent.py
├── automation/
│   ├── workflows.py         # Main orchestrator
│   └── playwright_manager.py
outputs/
├── offers/{school}/         # Downloaded PDFs
└── logs/screenshots/        # Debug screenshots
```

## Tech Stack

- **Python 3.9+** with asyncio
- **Playwright** for browser automation
- **Gemini 2.0 Flash** for vision analysis
- **Pydantic** for config validation
- **YAML** for school configurations

