import json
import time
import random
import os
import yaml
import re
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

    # Load Config
    try:
        with open("config.yml", "r") as f:
            config = yaml.safe_load(f)
            keywords = config.get("keywords", "DevOps")
            location = config.get("location", "Germany")
            print(f"Loaded config: {keywords} in {location}")
            
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
            
            
            date_param = date_mapping.get(config.get("date_posted", "past_week"), "r604800")
            
            # Handle experience level (can be string or list)
            raw_exp = config.get("experience_level", "")
            if isinstance(raw_exp, str):
                raw_exp = [raw_exp] # Convert single string to list
            elif not raw_exp:
                raw_exp = []
                
            # Map each level and join with commas
            mapped_exps = [exp_mapping.get(e, "") for e in raw_exp if e in exp_mapping]
            exp_param = ",".join(filter(None, mapped_exps))
            
    except FileNotFoundError:
        print("config.yml not found. Using defaults.")
        keywords = "DevOps"
        location = "Germany"
        date_param = "r604800"
        exp_param = ""

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
        print(f"Applying filters: {keywords} in {location}, Date: {date_param}, Exp: {exp_param}")
        
        jobs_data = []

        # PAGINATION LOOP: 5 Pages, approx 25 jobs per page
        for page_num in range(5):
            start_offset = page_num * 25
            print(f"\n--- Processing Page {page_num + 1}/5 (Start Offset: {start_offset}) ---")

            # Construct search URL with filters and pagination start
            # f_TPR = Date Posted (r604800 = past week)
            # f_E = Experience Level
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

            time.sleep(random.uniform(2, 4))

            # Helper to get all card locators
            # Sometimes we need to scroll a bit to ensure all 25 are loaded in the DOM
            # But the 'start=' parameter usually loads them.
            
            # Scroll down to ensure all jobs on this page are rendered
            # We need to scroll the SPECIFIC container for the list, not just the window
            # Scroll down to ensure all jobs on this page are rendered
            # We need to scroll the SPECIFIC container for the list, not just the window
            scroll_attempts = 0
            max_scroll_attempts = 15 # Increased attempts
            
            while True:
                card_locators = page.locator(".job-card-container").all()
                count = len(card_locators)
                print(f"   -> Currently loaded jobs: {count}")
                
                if count >= 25 or scroll_attempts >= max_scroll_attempts:
                    break
                    
                print("   -> Scrolling list container to load more jobs...")
                print("   -> Scrolling list container to load more jobs...")
                # Scroll the list container using JS - Smooth incremental scroll to bottom
                try:
                    # User-provided class and common alternatives
                    # scrollBy small amount to mimic user and trigger lazy load
                     page.evaluate("""
                        var selectors = [
                            '.ygleTEnWHLfoUkWsvDaalKdfNRUTyfmJHwk', 
                            '.scaffold-layout__list', 
                            '.jobs-search-results-list'
                        ];
                        for (var i = 0; i < selectors.length; i++) {
                            var list = document.querySelector(selectors[i]);
                            if (list) {
                                // Scroll by a small chunk
                                list.scrollBy(0, 300);
                                break;
                            }
                        }
                    """)
                except:
                    pass
                    
                # Also fallback to window scroll just in case
                page.mouse.wheel(0, 300)
                
                time.sleep(0.5) # Short sleep for smooth effect
                scroll_attempts += 1

            print(f"Found {len(card_locators)} jobs on this page.")
            
            if not card_locators:
                print("No cards found after waiting. Moving to next page or finishing.")
                break

            for i, card in enumerate(card_locators):
                 # We only want to process up to 25 per page roughly, but usually the page has exactly 25.
                global_index = len(jobs_data) + 1
                
                try:
                    print(f"[{global_index}] Clicking job card {i+1} on page {page_num + 1}...")
                    
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
                        print(f"Warning: Detail pane didn't load for job {global_index}. Skipping extraction.")
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

                    # Extract Description
                    try:
                        # Usually in a div with id="job-details" or class "jobs-description__content"
                        description_node = soup.select_one("#job-details, .jobs-description__content")
                        description = description_node.get_text(strip=True) if description_node else "No description found"
                    except:
                        description = "Error extracting description"

                    # Extract Job Post Time and Applicants (often in the same subline)
                    try:
                        # The structure usually is: Location · Time · Applicants
                        # Selector for the primary description/subline line
                        primary_desc = soup.select_one(".job-details-jobs-unified-top-card__primary-description-container, .job-details-jobs-unified-top-card__primary-description")
                        
                        if primary_desc:
                            full_text = primary_desc.get_text(" ", strip=True) 
                            # Replace non-breaking spaces and common separators
                            clean_text = full_text.replace("\u00a0", " ").replace("·", "|")
                            parts = [p.strip() for p in clean_text.split("|")]
                            
                            # Initialize defaults
                            posted_time = "Unknown"
                            applicant_count = "Unknown"
                            
                            for part in parts:
                                # Check for time indicators (English + Turkish)
                                if any(x in part.lower() for x in ["ago", "minute", "hour", "day", "week", "month", "saniye", "dakika", "saat", "gün", "hafta", "ay", "önce"]):
                                    posted_time = part
                                # Check for applicant count (English + Turkish)
                                elif any(x in part.lower() for x in ["applicant", "kişi", "başvuru"]):
                                    applicant_count = part
                                    
                            # If still unknown, try specific fallbacks
                        else:
                            posted_time = "Unknown"
                            applicant_count = "Unknown"
                            
                    except:
                        posted_time = "Error"
                        applicant_count = "Error"

                    # Extract Easy Apply and Apply Link
                    easy_apply = False
                    apply_link = "N/A" 
                    
                    try:
                        # Use Playwright locators for interaction
                        # Locate the apply button in the details panel
                        # We need to find the specific button within the current page context
                        # The details panel is usually updated, so we query the page
                        
                        # Common selectors for the apply button in the details pane
                        apply_btn_locator = page.locator(".jobs-apply-button--top-card button, .jobs-apply-button--top-card a").first
                        
                        if apply_btn_locator.count() > 0:
                            btn_text = apply_btn_locator.text_content().strip()
                            
                            if "Easy Apply" in btn_text or "Kolay Başvuru" in btn_text:
                                easy_apply = True
                                apply_link = "Easy Apply (In-app)"
                            else:
                                easy_apply = False
                                # Interactive Click to get the URL
                                print(f"   -> Clicking 'Apply' to fetch external link...")
                                try:
                                    with context.expect_page(timeout=5000) as new_page_info:
                                        apply_btn_locator.click()
                                    
                                    new_page = new_page_info.value
                                    new_page.wait_for_load_state("domcontentloaded", timeout=10000)
                                    apply_link = new_page.url
                                    print(f"   -> Found external link: {apply_link}")
                                    new_page.close()
                                except Exception as e:
                                    print(f"   -> Failed to capture external link (might be same tab or blocked): {e}")
                                    apply_link = "External (Failed to resolve)"
                        else:
                            # Fallback checks if button is missing but text exists (rare)
                            if soup.find(string=re.compile(r"Easy Apply|Kolay Başvuru", re.IGNORECASE)):
                                easy_apply = True
                                apply_link = "Easy Apply (In-app)"
                    except Exception as e:
                            print(f"Error extracting apply info: {e}")
                            pass

                    # Extract Job URL (often in the card or details)
                    try:
                        # Current URL often changes to the job ID view
                        job_url = page.url 
                    except:
                        job_url = "Unknown"

                    job_data = {
                        "title": title,
                        "company": company,
                        "location": location, 
                        "date_posted_text": posted_time,
                        "applicants": applicant_count,
                        "easy_apply": easy_apply,
                        "apply_link": apply_link,
                        "description_snippet": description[:200] + "...", 
                        "description": description,
                        "job_url": job_url,
                        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    jobs_data.append(job_data)
                    print(f"Scraped: {title} at {company} | Posted: {posted_time} | Applicants: {applicant_count} | Easy Apply: {easy_apply}")
                    
                    # Incremental Save
                    with open("jobs_export.json", "w", encoding="utf-8") as f:
                        json.dump(jobs_data, f, indent=4, ensure_ascii=False)
                        
                except Exception as e:
                    print(f"Error processing job {global_index}: {e}")
                    continue

            # Random sleep between pages
            print(f"Finished page {page_num + 1}. Waiting before next page...")
            time.sleep(random.uniform(5, 8))

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
