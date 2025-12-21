import json
import time
import random
import os
import yaml
import re
import tempfile
from playwright.sync_api import sync_playwright
import login

def run(keywords="DevOps", location="Germany", date_posted="past_week", experience_level=None, storage_state_path=None, headless=True, pages_to_scrape=2):
    """
    Scrapes LinkedIn jobs based on provided parameters.
    
    Args:
        keywords (str): Job search keywords
        location (str): Job location
        date_posted (str): 'past_24h', 'past_week', 'past_month'
        experience_level (list): List of experience levels
        storage_state_path (str): Path to the storage state file.
        headless (bool): Run browser in headless mode.
        
    Returns:
        list: List of scraped job dictionaries
    """
    
    # Helper mappings for filters
    date_mapping = {
        "past_24h": "r86400",
        "past_week": "r604800",
        "past_month": "r2592000"
    }
    
    exp_mapping = {
        "internship": "1",
        "entry_level": "2",
        "associate": "3",
        "mid_senior": "4",
        "director": "5",
        "executive": "6"
    }
    
    date_param = date_mapping.get(date_posted, "r604800")
    
    # Handle experience level
    if experience_level is None:
        experience_level = []
    elif isinstance(experience_level, str):
        experience_level = [experience_level] 

    mapped_exps = [exp_mapping.get(e, "") for e in experience_level if e in exp_mapping]
    exp_param = ",".join(filter(None, mapped_exps))
    
    # We expect storage_state_path to be a valid file path if provided
    # If not provided, we might try to login locally, but for API usage it should be provided
    
    # If logic for local run without args is needed, we can keep it, but for API we assume args are passed.
    
    print(f"Starting scrape: {keywords} in {location}, Date: {date_param}, Exp: {exp_param}")

    with sync_playwright() as p:
        # Launch browser with saved state and robust flags
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = None
        try:
            if storage_state_path and os.path.exists(storage_state_path):
                 context = browser.new_context(
                    storage_state=storage_state_path,
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 800}
                )
            else:
                 print("No valid storage state provided. Running without login (might fail/redirect).")
                 context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 800}
                )

        except Exception as e:
            print(f"Error loading storage state: {e}")
            # return "RETRY_LOGIN" # Should probably handle this better in API
            return []

        page = context.new_page()

        # Add webdriver property removal script
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("Navigating to LinkedIn Jobs...")
        
        # Check login status if supposed to be logged in?
        # For now, just go to search
        
        jobs_data = []
        print("Starting pagination loop...")

        # PAGINATION LOOP: 5 Pages, approx 25 jobs per page (Limit for API response time?)
        # Reduced to 2 pages for faster API response during testing, or keep user default?
        # Let's keep it robust but maybe limit implicitly or add a 'max_pages' arg later.
        max_pages = pages_to_scrape 
        
        for page_num in range(max_pages):
            start_offset = page_num * 25
            print(f"\n--- Processing Page {page_num + 1}/{max_pages} (Start Offset: {start_offset}) ---")

            search_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&f_TPR={date_param}&start={start_offset}"
            if exp_param:
                search_url += f"&f_E={exp_param}"
            
            page.goto(search_url)
            
            # Wait for list to load
            try:
                page.wait_for_selector(".job-card-container", timeout=10000)
            except:
                print(f"No job cards found on page {page_num + 1}. Ending scrape.")
                break
            
            print(f"Page {page_num + 1} loaded. Starting scroll...")
            
            time.sleep(random.uniform(2, 4))
            
            # Scroll logic
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while True:
                card_locators = page.locator(".job-card-container").all()
                count = len(card_locators)
                
                if count >= 25 or scroll_attempts >= max_scroll_attempts:
                    print(f"Scrolling finished. Found {count} job cards (Attempts: {scroll_attempts}).")
                    break
                    
                # Scroll the list container using JS
                try:
                     page.evaluate("""
                        var selectors = [
                            '.PfaZBQjnUYgmiwbArDngwzNxUcNgfhpoTM',
                            '.vNNioWCWAlCflKqeMSIByDWvDXhAUVPeqE',
                            'ul.scaffold-layout__list-container',
                            'ul.jobs-search__results-list',
                            '.ygleTEnWHLfoUkWsvDaalKdfNRUTyfmJHwk',
                            '.scaffold-layout__list',
                            '.jobs-search-results-list'
                        ];
                        for (var i = 0; i < selectors.length; i++) {
                            var list = document.querySelector(selectors[i]);
                            if (list) {
                                list.scrollBy(0, 300);
                                break;
                            }
                        }
                    """)
                except:
                    pass
                    
                page.mouse.wheel(0, 300)
                time.sleep(0.5)
                scroll_attempts += 1

            # Extract data loop (Simplified for brevity/speed in API context, but keeping logic)
            # NOTE: Deep extraction (clicking each card) is slow.
            # Ideally for an API, we want speed. But the user asked for "return a json file that includes jobs"
            # The original code clicked every job. That takes ~3-5s per job. 25 jobs = ~2 mins per page.
            # I will keep the logic but maybe we should advise on speed later. 
            
            for i, card in enumerate(card_locators):
                # Only process limited amount if needed
                global_index = len(jobs_data) + 1
                print(f"Processing job {i+1}/{len(card_locators)} (Total Scraped: {len(jobs_data)})...")
                
                try:
                    # Scroll to card
                    card.scroll_into_view_if_needed()
                    try:
                        card.click()
                        print("  Clicked job card.")
                    except:
                        card.click(force=True)
                        print("  Clicked job card (Force).")
                    
                    time.sleep(random.uniform(0.5, 1.5)) # Reduced sleep slightly for API speed
                    
                    # Wait for details
                    try:
                        page.wait_for_selector(".job-details-jobs-unified-top-card__job-title, .top-card-layout__title", timeout=3000)
                    except:
                        print("  Timeout waiting for job details to load.")
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
                        
                    try:
                        description_node = soup.select_one("#job-details, .jobs-description__content")
                        description = description_node.get_text(strip=True) if description_node else "No description found"
                    except:
                        description = "Error extracting description"
                        
                    try:
                         # Current URL often changes to the job ID view
                        job_url = page.url 
                    except:
                        job_url = "Unknown"

                    job_data = {
                        "title": title,
                        "company": company,
                        "location": location, 
                        "description_snippet": description[:200] + "...", 
                        "description": description,
                        "job_url": job_url,
                        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    jobs_data.append(job_data)
                    print(f"  Successfully scraped: {title} at {company}")
                    # print(f"Scraped: {title} at {company}")
                        
                except Exception as e:
                    print(f"Error processing job {global_index}: {e}")
                    continue

        browser.close()
        return jobs_data

if __name__ == "__main__":
    # Local test wrapper
    # Try to read config if available
    try:
        with open("config.yml", "r") as f:
            config = yaml.safe_load(f)
            k = config.get("keywords", "DevOps")
            l = config.get("location", "Germany")
            dp = config.get("date_posted", "past_week")
            ex = config.get("experience_level", [])
            h = config.get("headless", True)
            p = config.get("pages_to_scrape", 2)
    except:
        k, l, dp, ex, h, p = "DevOps", "Germany", "past_week", [], True, 2
        
    # Local storage state defaults to "storage_state.json"
    s_path = "storage_state.json"
    
    results = run(k, l, dp, ex, s_path, h, p)
    
    # Save to file for local run compatibility
    with open("jobs_export.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"Done. Saved {len(results)} jobs to jobs_export.json")

