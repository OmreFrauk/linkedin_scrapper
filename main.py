import json
import time
import random
import os
from playwright.sync_api import sync_playwright
import login

STORAGE_STATE = "storage_state.json"

def run():
    # Ensure we are logged in
    if not os.path.exists(STORAGE_STATE):
        print(f"{STORAGE_STATE} not found. Attempting to log in...")
        login.login()
        if not os.path.exists(STORAGE_STATE):
            print("Login failed to produce storage state. Exiting.")
            return False

    with sync_playwright() as p:
        # Launch browser with saved state
        browser = p.chromium.launch(headless=False)
        
        try:
            context = browser.new_context(storage_state=STORAGE_STATE)
        except Exception as e:
            print(f"Error loading storage state: {e}")
            return "RETRY_LOGIN"

        page = context.new_page()

        print("Navigating to LinkedIn Jobs...")
        page.goto("https://www.linkedin.com/jobs/search")
        
        # Verify we are logged in (look for nav bar)
        try:
            page.wait_for_selector(".global-nav__content", timeout=10000)
            print("Successfully accessed Jobs page.")
        except:
            print("Session might be invalid/expired. Deleting state and retrying login...")
            browser.close()
            return "RETRY_LOGIN"

        # Apply Filters
        # "Past Week" filter: f_TPR=r604800
        keywords = "DevOps"
        location = "Germany"
        print(f"Applying filters: {keywords} in {location}, Date Posted: Past Week")
        
        # Construct search URL with "Past Week" filter
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&f_TPR=r604800"
        page.goto(search_url)
        time.sleep(random.uniform(2, 4))

        # Scraping Loop with Robust Infinite Scroll
        jobs_data = []
        job_cards_selector = ".job-card-container" 
        
        processed_count = 0
        consecutive_no_new_jobs = 0
        MAX_RETRIES = 3 # Number of times to try scrolling/button clicking if no new jobs appear

        while True:
            # Re-query the DOM for job cards
            card_locators = page.locator(job_cards_selector).all()
            total_cards = len(card_locators)
            print(f"Status: Found {total_cards} job cards so far. Processed: {processed_count}.")

            if total_cards > processed_count:
                # We have new cards to process
                consecutive_no_new_jobs = 0 # Reset retry counter
                new_cards = card_locators[processed_count:]
                
                for i, card in enumerate(new_cards):
                    global_index = processed_count + i
                    try:
                        print(f"[{global_index + 1}/{total_cards}] Clicking job card...")
                        
                        # Scroll to the card to ensure it's "real" and interactable
                        card.scroll_into_view_if_needed()
                        # Use force=True if normal click fails due to overlays, but try normal first
                        try:
                            card.click()
                        except:
                            # Sometimes headers overlay; force click or scroll slightly
                            card.click(force=True)
                        
                        time.sleep(random.uniform(1.5, 3.5)) # Mimic human reading delay
                        
                        # Wait for details
                        try:
                            page.wait_for_selector(".job-details-jobs-unified-top-card__job-title, .top-card-layout__title", timeout=5000)
                        except:
                            print(f"Warning: Detail pane didn't load for job {global_index + 1}. Skipping extraction.")
                            continue

                        # Extract Data
                        details_html = page.content() 
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(details_html, 'html.parser')
                        
                        try:
                            title = soup.select_one(".job-details-jobs-unified-top-card__job-title, .top-card-layout__title").get_text(strip=True)
                        except:
                            title = "Unknown Title"
                            
                        try:
                            company = soup.select_one(".job-details-jobs-unified-top-card__company-name, .top-card-layout__first-subline .topcard__org-name-link").get_text(strip=True)
                        except:
                            company = "Unknown Company"

                        # Extract Job URL (often in the card or details)
                        try:
                            # Current URL often changes to the job ID view
                            job_url = page.url 
                            # Or try to find link in card: card.locator("a.job-card-list__title").get_attribute("href")
                        except:
                            job_url = "Unknown"

                        job_data = {
                            "title": title,
                            "company": company,
                            "job_url": job_url,
                            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        jobs_data.append(job_data)
                        print(f"Scraped: {title} at {company}")
                        
                        # Incremental Save
                        with open("jobs_export.json", "w", encoding="utf-8") as f:
                            json.dump(jobs_data, f, indent=4)
                            
                    except Exception as e:
                        print(f"Error processing job {global_index + 1}: {e}")
                        continue
                
                # Update processed count
                processed_count = total_cards
            
            else:
                # No new cards found yet. Try to load more.
                print("No new jobs immediately visible. Attempting to load more...")
                consecutive_no_new_jobs += 1
                
                if consecutive_no_new_jobs >= MAX_RETRIES:
                    print(f"No new jobs appeared after {MAX_RETRIES} attempts. Assuming end of list.")
                    break
                
                # Scroll to bottom of the list container (or window)
                # Ideally, find the list container. Usually 'div.jobs-search-results-list'
                try:
                    # Scroll global window
                    page.mouse.wheel(0, 3000)
                    time.sleep(2)
                    
                    # Also try to specifically scroll the list container if found
                    # This is often needed in the SPA layout
                    # Selector guess: .jobs-search-results-list
                    page.evaluate("var list = document.querySelector('.jobs-search-results-list'); if(list) { list.scrollTop = list.scrollHeight; }")
                except:
                    pass
                
                time.sleep(3)
                
                # Check for "See more jobs" button
                try:
                    see_more = page.locator("button[aria-label='See more jobs']")
                    if see_more.is_visible():
                        print("Found 'See more jobs' button. Clicking...")
                        see_more.click()
                        time.sleep(3)
                        consecutive_no_new_jobs = 0 # Reset if we successfully clicked
                except:
                    pass
                    
        print(f"Scraping complete. Total jobs: {len(jobs_data)}")
        
        browser.close()
        return True

if __name__ == "__main__":
    result = run()
    if result == "RETRY_LOGIN":
        if os.path.exists(STORAGE_STATE):
            os.remove(STORAGE_STATE)
        print("Retrying with fresh login...")
        run()
