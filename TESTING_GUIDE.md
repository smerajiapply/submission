# Testing Guide with Real School Credentials

## Prerequisites

Before testing with real credentials, ensure:

1. **Setup is complete**:
```bash
bash setup.sh
```

2. **Environment configured**:
Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-4-vision-preview
HEADLESS=false
BROWSER_TIMEOUT=30000
LOG_LEVEL=INFO
```

3. **Test the setup**:
```bash
python run.py test-setup
```

## Step 1: Onboard Your School

First, we'll onboard the school portal. This creates a configuration file and tests login.

```bash
python run.py onboard \
  --school-name "Your School Name" \
  --url "https://portal.yourschool.edu" \
  --username "your_username" \
  --password "your_password"
```

**What this does:**
- Creates a config file in `src/config/schools/your_school_name.yaml`
- Opens a browser (visible, not headless)
- Tests login with your credentials
- Analyzes the dashboard
- Saves screenshots of each step

**Expected output:**
- "✓ Onboarding successful!"
- Config file path
- Dashboard analysis showing page type and elements found

**If it fails:**
- Check the screenshots in `outputs/logs/screenshots/`
- Review the logs in `outputs/logs/automation.log`
- The config file will still be created - you can edit it manually

## Step 2: Review and Refine Config

After onboarding, review the generated config file:

```bash
python run.py show-config --school your_school_name
```

Edit the config file if needed:

```bash
# Open in your editor
code src/config/schools/your_school_name.yaml
```

### What to check:

1. **Portal URL**: Is it correct?
2. **Hints**: Add any specific text you see on the login/dashboard pages
3. **Selectors**: If the agent struggled, add specific CSS selectors

Example refined config:

```yaml
school_name: "ABC University"
portal_url: "https://portal.abc.edu/applicant"
timeout: 30

hints:
  login_page_indicators:
    - "Applicant Login"
    - "Enter your credentials"
  dashboard_indicators:
    - "Welcome"
    - "My Applications"
    - "Application Dashboard"
  application_status_indicators:
    - "Application Status"
    - "Decision"
    - "Status:"
  offer_indicators:
    - "Offer Letter"
    - "Download Decision"
    - "View Offer"

selectors:
  username_field: "#username"
  password_field: "#password"
  login_button: "button[type='submit']"

notes: |
  - Dashboard shows applications in a table
  - Need to click "View All" to see applications
  - Offer letters appear as "Download" links
```

## Step 3: Test Application Check

Now test checking an actual application:

```bash
python run.py check-application \
  --school your_school_name \
  --username "your_username" \
  --password "your_password" \
  --app-id "12345" \
  --student-name "John Doe" \
  --student-email "john@example.com"
```

**Note:** Provide at least one of `--app-id`, `--student-name`, or `--student-email`

**What this does:**
1. Logs into the portal
2. Navigates to applications section
3. Searches for the specific application
4. Extracts the status
5. Downloads offer letter if available
6. Saves all artifacts

**Expected output:**
- Success: Yes/No
- Status: Pending/Accepted/Rejected/etc.
- Offer Downloaded: Yes/No
- Offer Path: (if downloaded)

## Step 4: Review Results

### Check Screenshots
```bash
ls -lh outputs/logs/screenshots/
```

Screenshots are named in sequence showing each step:
- `before_task_001.png`
- `after_navigate_002.png`
- `after_click_003.png`
- etc.

Review these to see what the agent saw at each step.

### Check Logs
```bash
tail -f outputs/logs/automation.log
```

Or view the full log:
```bash
cat outputs/logs/automation.log
```

Look for:
- Where did the agent succeed?
- Where did it struggle?
- What decisions did it make?

### Check Offer Letters (if downloaded)
```bash
ls -lh outputs/offers/your_school_name/
```

## Step 5: Troubleshooting & Refinement

### Common Issues and Solutions

#### 1. Login Fails

**Symptoms:**
- Agent can't find username/password fields
- Login button not clicked
- Error message appears

**Solutions:**
- Add specific selectors to config:
```yaml
selectors:
  username_field: "#username"  # Inspect element to get this
  password_field: "#password"
  login_button: "button.login-btn"
```

- Check if portal has CAPTCHA (not supported yet)
- Verify credentials are correct

#### 2. Application Not Found

**Symptoms:**
- Agent navigates successfully but can't locate application
- Gets stuck on applications page

**Solutions:**
- Manually inspect the portal and note the exact flow
- Add navigation hints:
```yaml
hints:
  dashboard_indicators:
    - "Click here to view applications"
    - "Application List"
```

- The agent might need multiple attempts - check if pagination exists

#### 3. Status Extraction Fails

**Symptoms:**
- Status returned as "unknown"
- Finds application but can't read status

**Solutions:**
- Add status-specific hints:
```yaml
hints:
  application_status_indicators:
    - "Current Status:"
    - "Decision:"
    - "Application Decision"
```

- Check screenshots - is status visible?
- May need to click into application details

#### 4. Download Fails

**Symptoms:**
- Offer detected but download fails
- No file in outputs/offers

**Solutions:**
- Check if download requires extra clicks
- Verify offer is actually downloadable (not just viewable)
- May need to add specific selector:
```yaml
selectors:
  offer_download: "a.download-offer"
```

### Advanced Debugging

#### Run with Verbose Mode

The agent already runs in verbose mode, showing all reasoning steps.

#### Watch in Real-Time

Set headless to false in `.env`:
```
HEADLESS=false
```

This lets you watch the browser automation happen in real-time.

#### Adjust Timeouts

If the portal is slow, increase timeout:
```yaml
timeout: 60  # 60 seconds
```

#### Test Incrementally

Test just the login:
- Run onboard command
- Watch it login
- If successful, proceed to full check

Test just navigation:
- Login manually
- Note the exact steps
- Add those as hints

## Step 6: Iterate and Optimize

After your first successful run:

1. **Document quirks** in the config `notes` field
2. **Add discovered selectors** to make future runs faster
3. **Test with different applications** to ensure consistency
4. **Refine hints** based on what worked

### Measuring Success

Target metrics:
- **Login success rate**: >95%
- **Application found**: >90%
- **Status extracted**: >85%
- **Offer download**: >80% (when available)

### Time to Onboard

Track your time:
- Config creation: ~30 min
- First test run: 1-2 hours
- Refinement: 1-2 hours
- Final testing: 1 hour

**Total: 4-6 hours** for a production-ready config

## Step 7: Production Use

Once you're confident:

1. **Set headless mode**:
```
HEADLESS=true
```

2. **Batch process multiple applications**:
Create a CSV with applications and loop through them

3. **Schedule automated checks**:
Use cron or similar to check daily

4. **Add monitoring**:
Track success rates and alert on failures

## Example: Complete First Test

Here's a complete example for your first test:

```bash
# 1. Setup
bash setup.sh

# 2. Configure .env
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

# 3. Verify setup
python run.py test-setup

# 4. Onboard (replace with real values)
python run.py onboard \
  --school-name "Test University" \
  --url "https://apply.test.edu/portal" \
  --username "test@example.com" \
  --password "your_password"

# 5. Review config
python run.py show-config --school test_university

# 6. Check application
python run.py check-application \
  --school test_university \
  --username "test@example.com" \
  --password "your_password" \
  --app-id "APP-12345"

# 7. Review results
ls outputs/logs/screenshots/
cat outputs/logs/automation.log | tail -50
ls outputs/offers/test_university/
```

## Getting Help

If you get stuck:

1. **Check screenshots** - they show exactly what the agent saw
2. **Read logs** - detailed reasoning is logged
3. **Try manually** - can you do it yourself? If so, note the steps
4. **Refine config** - add more hints and selectors
5. **Adjust prompts** - edit `src/agents/browser_agent.py` if needed

## Next Steps

After successful testing:

1. Onboard additional schools (reuse learnings)
2. Build batch processing for multiple applications
3. Add monitoring and alerting
4. Consider adding MFA support if needed
5. Create a web dashboard for easier management

Good luck with your testing! 🚀


