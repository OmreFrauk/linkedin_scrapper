import os
import time
import json
import tempfile
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

def login(username=None, password=None):
    if not username or not password:
        load_dotenv()
        username = username or os.environ.get("LINKEDIN_USERNAME")
        password = password or os.environ.get("LINKEDIN_PASSWORD")

    if not username or not password:
        print("Error: LINKEDIN_USERNAME and LINKEDIN_PASSWORD must be provided or set in environment variables.")
        return None

    with sync_playwright() as p:
        # Launch browser with robust flags for headless
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        ) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        # Add webdriver property removal script
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("Navigating to LinkedIn login page...")
        page.goto("https://www.linkedin.com/login")

        print("Filling credentials...")
        page.fill("#username", username)
        page.fill("#password", password)

        print("Clicking sign in...")
        page.click("button[type='submit']")

        # Wait for navigation and check for success
        # We look for the global nav search bar or something distinctive of the feed
        try:
            print("Waiting for successful login...")
            page.wait_for_selector(".global-nav__content", timeout=15000)
            print("Login successful!")
            
            # Save storage state to a temporary file correctly to read it back into memory
            # or use context.storage_state() which usually returns the dict directly or writes to path?
            # context.storage_state(path=...) writes to file.
            # But context.storage_state() without path argument returns the state as a DICT!
            
            state = context.storage_state()
            
            # Check if local run requested to save file
            # For API usage we might not want to save to disk essentially, but for 'run()' it expected a file.
            # But here we are just returning the state.
            
            return state
            
        except Exception as e:
            print(f"Login failed or required manual intervention (CAPTCHA/2FA). Error: {e}")
            print("Saving debug info...")
            page.screenshot(path="debug_login.png")
            with open("debug_login.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"Debug saved to debug_login.png and debug_login.html")
            return None

        finally:
            browser.close()

if __name__ == "__main__":
    state = login()
    if state:
        with open("storage_state.json", "w") as f:
            json.dump(state, f)
        print("Session saved to storage_state.json")
