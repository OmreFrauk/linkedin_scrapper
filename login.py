import os
import time
from playwright.sync_api import sync_playwright

def login():
    username = os.environ.get("LINKEDIN_USERNAME")
    password = os.environ.get("LINKEDIN_PASSWORD")

    if not username or not password:
        print("Error: LINKEDIN_USERNAME and LINKEDIN_PASSWORD environment variables must be set.")
        return 

    with sync_playwright() as p:
        # Launch browser (headless=False so we can see what's happening if needed, 
        # but user might want it headless later. For login, usually better to show it 
        # or at least helpful for debugging).
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()

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
            
            # Save storage state
            context.storage_state(path="storage_state.json")
            print("Session saved to storage_state.json")
            
        except Exception as e:
            print(f"Login failed or required manual intervention (CAPTCHA/2FA). Error: {e}")
            # If we timed out, it might be a captcha. 
            # We could keep the browser open for a bit to see what happened?
            # But for now, just exit.

        browser.close()

if __name__ == "__main__":
    login()
