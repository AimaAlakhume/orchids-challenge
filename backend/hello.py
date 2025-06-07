from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import uvicorn
import httpx
import json
import os
import traceback
import base64
from dotenv import load_dotenv
import anthropic

load_dotenv()

try:
    anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=anthropic_api_key)
except KeyError:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")


# Create FastAPI instance
app = FastAPI(
    title="Orchids Challenge API",
    description="A starter FastAPI template for the Orchids Challenge backend",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/public/screenshots", StaticFiles(directory="public/screenshots"), name="screenshots")


# Pydantic models
class Item(BaseModel):
    id: int
    name: str
    description: str = None


class ItemCreate(BaseModel):
    name: str
    description: str = None


class UrlRequest(BaseModel):
    url: str


class ScrapedData(BaseModel):
    id: str
    url: str
    html_content: str | None
    screenshot_path: str | None
    assets: Dict[str, List[str]] | None
    title: str | None = None


class CloneRequest(BaseModel):
    url_id: str


class CloneResponse(BaseModel):
    success: bool
    cloned_html: Optional[str] = None
    message: Optional[str] = None


SCRAPED_DATA_FILE = "scraped_data.json"
SCREENSHOTS_DIR = "public/screenshots"

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def load_scraped_data():
    if os.path.exists(SCRAPED_DATA_FILE):
        with open(SCRAPED_DATA_FILE, 'r') as data_file:
            try:
                return json.load(data_file)
            except json.JSONDecodeError:
                return {}
            
    return {}

def save_scraped_data(data):
    with open(SCRAPED_DATA_FILE, 'w') as data_file:
        json.dump(data, data_file, indent=4)


# Web scrape endpoint!
@app.post("/webscrape")
async def scrape_website(request: UrlRequest):
    url_id = request.url.replace("https://", "").replace("http://", "").replace("www.", "").replace("/", "_").replace(".", "_").replace(":", "_").replace("?", "_").replace("=", "_").replace("&", "_")
    if len(url_id) > 100:
        url_id = url_id[:100] + "_hash"

    scraped_data = load_scraped_data()

    try:
        #SCRAPE HTML
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(request.url)
            res.raise_for_status()

        html_content = res.text
        soup = BeautifulSoup(html_content, 'html.parser')

        if soup.title: #get page title
            title = soup.title.string
        else:
            title = "Title not found"


        #SCRAPE ASSETS
        assets = {
            "images": [],
            "stylesheets": [],
            "scripts": []
        }

        base_url_parsed = httpx.URL(request.url)

        for img in soup.find_all('img', src=True):
            src = img['src']
            if not src.startswith(('data:', '#')):
                try:
                    resolved_url = str(base_url_parsed.join(src))
                    assets["images"].append(resolved_url)
                except Exception as e:
                    print(f"Error resolving image URL {src}: {e}")
        for link in soup.find_all('link', rel='stylesheet', href=True):
            href = link['href']
            if not href.startswith(('data:', '#')):
                try:
                    resolved_url = str(base_url_parsed.join(href))
                    assets["stylesheets"].append(resolved_url)
                except Exception as e:
                    print(f"Error resolving stylesheet URL {href}: {e}")
        for script in soup.find_all('script', src=True):
            src = script['src']
            if not src.startswith(('data:', '#')):
                try:
                    resolved_url = str(base_url_parsed.join(src))
                    assets["scripts"].append(resolved_url)
                except Exception as e:
                    print(f"Error resolving script URL {src}: {e}")

        #TAKE SCREENSHOTS
        screenshot_filename = f"{url_id}.png"
        screenshot_path = os.path.join(SCREENSHOTS_DIR, screenshot_filename)
        relative_screenshot_path = f"/public/screenshots/{screenshot_filename}"

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            try:
                await page.goto(request.url, wait_until='networkidle', timeout=90000) #1min 30s timeout
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"Screenshot saved to {screenshot_path}")
            except Exception as e:
                traceback.print_exc()
                screenshot_path = None
                relative_screenshot_path = None
                print(f"Could not take screenshot for {request.url}: {e}")
            finally:
                await browser.close()
            
        new_scraped_entry = ScrapedData(
            id=url_id,
            url=request.url,
            title=title,
            html_content=html_content,
            screenshot_path=relative_screenshot_path,
            assets=assets
        )
        
        scraped_data[url_id] = new_scraped_entry.dict()
        save_scraped_data(scraped_data)
        print("Scraped data saved.")

        return {
            "success": True,
            "url": request.url,
            "title": title,
            "id": url_id,
            "html_content_length": len(html_content),
            "screenshot_url": relative_screenshot_path,
            "assets_count": {
                "images": len(assets["images"]),
                "stylesheets": len(assets["stylesheets"]),
                "scripts": len(assets["scripts"]),
                "links": 0
            }
        }
    except httpx.RequestError as exc: #network error handler
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while requesting {request.url}: {exc}"
        )
    except httpx.HTTPStatusError as exc: #http error handler
        traceback.print_exc()
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"HTTP error {exc.response.status_code} occurred while fetching {request.url}: {exc.response.text}"
        )
    except Exception as e: #handle other errors
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# Scraped data endpoint
@app.get("/scraped-data", response_model=Dict[str, ScrapedData])
async def get_scraped_data():
    return load_scraped_data()

# Cloning endpoint
@app.post("/clone-website", response_model=CloneResponse)
async def clone_website_with_llm(request: CloneRequest):
    scraped_data = load_scraped_data()
    url_id = request.url_id

    if url_id not in scraped_data:
        raise HTTPException(status_code=404, detail="Scraped data not found for this URL ID.")

    data = scraped_data[url_id]
    html_content = data.get("html_content")
    screenshot_path_for_file = data.get("screenshot_path")

    actual_screenshot_file_path = None
    if screenshot_path_for_file:
        actual_screenshot_file_path = os.path.join(os.getcwd(), screenshot_path_for_file.lstrip('/'))

    if not html_content and not actual_screenshot_file_path:
        raise HTTPException(status_code=400, detail="No HTML content or screenshot available for cloning.")

    messages = []
    system_prompt = """
    You are an expert web developer specializing in creating accurate HTML clones of websites.
    Your primary objective is to replicate the visual appearance of the provided website screenshot as precisely as possible. Every detail matters: layout, colors, font styles, spacing, element sizes, and component design.
    The final output must be a single, complete, and valid HTML file. All CSS must be embedded within a `<style>` tag in the `<head>`, and any necessary JavaScript within a `<script>` tag just before `</body>`.
    Do not include any external stylesheets, scripts, or frameworks unless their use is explicitly verifiable from the provided raw HTML content.
    For images shown in the screenshot, use `<img>` tags and reference their original URLs if possible. If not, create a visually appropriate placeholder.
    Thank you!"""
    
    user_message_content = []

    # Add raw HTML content if available
    if html_content:
        user_message_content.append({
            "type": "text",
            "text": f"Here is the raw HTML content of the original website, provided as additional context. Analyze its structure but prioritize the visual outcome from the screenshot:\n\n```html\n{html_content}\n```"
        })
    else:
        user_message_content.append({
            "type": "text",
            "text": "No raw HTML content available. Please rely solely on the visual screenshot."
        })

    # Add screenshot if available
    if actual_screenshot_file_path and os.path.exists(actual_screenshot_file_path):
        try:
            with open(actual_screenshot_file_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
            user_message_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": encoded_image,
                },
            })
            user_message_content.append({"type": "text", "text": "Here is the visual screenshot of the website that you must replicate:"})
            print(f"Image {actual_screenshot_file_path} successfully encoded and added to prompt.")
        except Exception as e:
            print(f"Error reading or encoding screenshot {actual_screenshot_file_path}: {e}")
            user_message_content.append({"type": "text", "text": "Error loading screenshot."})
    else:
        user_message_content.append({"type": "text", "text": "No screenshot available or file not found."})
        print(f"Screenshot path not found or invalid: {actual_screenshot_file_path}")

    user_message_content.append({"type": "text", "text": "Please provide the complete HTML code for the cloned website, starting directly with `<!DOCTYPE html>`."})


    messages.append({
        "role": "user",
        "content": user_message_content
    })

    try:
        response = client.messages.create(
            model="claude-4-sonnet-20250514",
            max_tokens=4000,
            system=system_prompt,
            messages=messages,
            temperature=0.2
        )
        cloned_html = response.content[0].text
        
        if cloned_html.startswith("```html") and cloned_html.endswith("```"):
            cloned_html = cloned_html[7:-3].strip()
        elif cloned_html.startswith("```") and cloned_html.endswith("```"):
            cloned_html = cloned_html[3:-3].strip()

        if not cloned_html.strip().startswith("<!DOCTYPE html>"):
            print("Warning: LLM output did not start with <!DOCTYPE html>. Attempting to prepend.")
            cloned_html = "<!DOCTYPE html>\n" + cloned_html

        return CloneResponse(success=True, cloned_html=cloned_html)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"LLM cloning failed: {str(e)}")

def main():
    """Run the application"""
    uvicorn.run(
        "hello:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    main()