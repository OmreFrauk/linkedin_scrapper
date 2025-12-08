# LinkedIn Job Scraper

A robust Python-based scraper using Playwright to automate job searching and data extraction from LinkedIn.

## Key Features
- **Automated Login**: Handles authentication and saves session state (`storage_state.json`) to avoid repeated logins.
- **Smart Filtering**: Configurable via `config.yml` for:
  - Position (Keywords)
  - Location
  - Experience Level (e.g., Entry Level, Mid-Senior)
  - Date Posted (e.g., Past Week, Past 24 Hours)
- **Deep Data Extraction**:
  - Extracts full **Description**, **Applicant Count**, and **Posted Date** (parsing relative time like "12 hours ago").
  - Identifies **Easy Apply** vs. Standard Apply.
  - **Interactive Link Retrieval**: Automatically clicks "Apply" buttons to capture the real external application URL for standard jobs.
- **Robustness**:
  - Handles infinite scrolling.
  - Supports Turkish characters in output.
  - Saves data incrementally to `jobs_export.json`.

## Usage
1. Configure filters in `config.yml`.
2. Run `python main.py`.
