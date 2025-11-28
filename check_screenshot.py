"""Quick test to see the current page structure after login"""

import asyncio
from pathlib import Path
from PIL import Image

# Just look at the most recent screenshot
screenshot_path = Path("/Users/sina.meraji/Code/submission/outputs/logs/screenshots/after_click_004_20251126_223747_097936.png")

if screenshot_path.exists():
    img = Image.open(screenshot_path)
    print(f"Screenshot size: {img.size}")
    print(f"Screenshot exists: {screenshot_path}")
    print("\nThis screenshot shows what the page looked like after clicking Sign in")
    print("The agent needs to figure out where to navigate from here to find applications.")
else:
    print("Screenshot not found")


