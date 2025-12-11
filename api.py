from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import main
import login
import json
import tempfile
import os

app = FastAPI()

class ScrapeRequest(BaseModel):
    keywords: str = "DevOps"
    location: str = "Germany"
    date_posted: str = "past_week"
    experience_level: Optional[List[str]] = None
    storage_state: dict # The actual JSON content of storage_state

@app.post("/scrape")
def scrape_jobs(request: ScrapeRequest):
    """
    Endpoint to scrape LinkedIn jobs.
    """
    
    # Create a temporary file for the storage state
    # main.py expects a file path
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as tmp_state:
            json.dump(request.storage_state, tmp_state)
            tmp_state_path = tmp_state.name
            
        print(f"Created temp storage state at {tmp_state_path}")
        
        # Call the scraper
        jobs = main.run(
            keywords=request.keywords,
            location=request.location,
            date_posted=request.date_posted,
            experience_level=request.experience_level,
            storage_state_path=tmp_state_path,
            headless=True 
        )
        
        # Cleanup
        try:
            os.remove(tmp_state_path)
            print(f"Removed temp storage state at {tmp_state_path}")
        except Exception as e:
            print(f"Warning: Failed to delete temp file {tmp_state_path}: {e}")
            
        return {"count": len(jobs), "jobs": jobs}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login_endpoint(request: LoginRequest):
    """
    Endpoint to login to LinkedIn and retrieve storage state.
    """
    try:
        # Call the login function
        state = login.login(username=request.username, password=request.password)
        
        if not state:
            raise HTTPException(status_code=401, detail="Login failed. Check credentials or CAPTCHA.")
            
        return state
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
