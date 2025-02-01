import os
import requests
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from upsonic import UpsonicClient, Task, AgentConfiguration, ObjectResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the Upsonic client
client = UpsonicClient("localserver")
client.set_config("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID"))
client.set_config("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY"))
client.set_config("AWS_REGION", os.getenv("AWS_REGION"))

client.set_config("AZURE_OPENAI_ENDPOINT", os.getenv("AZURE_OPENAI_ENDPOINT"))
client.set_config("AZURE_OPENAI_API_VERSION", os.getenv("AZURE_OPENAI_API_VERSION"))
client.set_config("AZURE_OPENAI_API_KEY", os.getenv("AZURE_OPENAI_API_KEY"))

client.default_llm_model = "azure/gpt-4o"

# Define FastAPI app
app = FastAPI()

# Input Model: Brand or Person Name
class BrandInput(BaseModel):
    brand_name: str

# Response Format
class Influencer(ObjectResponse):
    name: str
    platform: str
    profile_link: str
    engagement_score: float

class BrandAnalysisResponse(ObjectResponse):
    top_articles: list[dict]
    influencers: list[Influencer]

# ✅ SerpAPI Tool for Brand Monitoring
@client.tool()
class SerpAPITool:
    def search(query: str) -> list:
        """Uses SerpAPI to find latest articles and influencer data."""
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="SerpAPI API Key not found!")

        url = "https://google.serper.dev/search"
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        payload = json.dumps({"q": query})

        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            data = response.json()
            search_results = data.get("organic", [])

            return [
                {
                    "title": result.get("title", "Unknown Article"),
                    "url": result.get("link", "#"),
                    "snippet": result.get("snippet", "No Description")
                }
                for result in search_results[:10]
            ]
        else:
            raise HTTPException(status_code=500, detail=f"SerpAPI Request Failed: {response.text}")

# ✅ Define Brand Monitoring Agent
brand_monitor_agent = AgentConfiguration(
    job_title="Brand & Influencer Analyst",
    company_url="https://upsonic.ai",
    company_objective="Monitor brand presence and identify top influencers.",
    reflection=True
)

@app.post("/monitor-brand/")
async def monitor_brand(input_data: BrandInput):
    """Finds latest articles and relevant influencers for a brand or person."""
    search_query = f"Latest news and top influencers talking about {input_data.brand_name}"

    # Task: Find Brand Mentions & Influencers
    brand_monitor_task = Task(
        description=f"Find latest articles and identify top influencers talking about {input_data.brand_name}.",
        tools=[SerpAPITool],
        response_format=BrandAnalysisResponse
    )
    client.agent(brand_monitor_agent, brand_monitor_task)
    brand_data = brand_monitor_task.response

    if not brand_data:
        raise HTTPException(status_code=500, detail="Failed to fetch brand data.")

    return {
        "brand_name": input_data.brand_name,
        "top_articles": brand_data.top_articles,
        "influencers": brand_data.influencers
    }

# ✅ UI for Brand Monitoring
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Brand & Influencer Monitoring</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin: 50px; }
            input { padding: 10px; margin: 10px; width: 300px; }
            button { padding: 10px; background: blue; color: white; border: none; cursor: pointer; }
            #results { margin-top: 20px; text-align: left; }
            footer { margin-top: 30px; font-size: 0.9em; color: #555; }
            footer a { color: #007BFF; text-decoration: none; }
            footer a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>Brand & Influencer Monitoring</h1>
        <input type="text" id="brand" placeholder="Enter brand or person name">
        <button onclick="fetchBrandAnalysis()">Analyze</button>
        <div id="results"></div>
        <footer>
            Powered by <a href="https://upsonic.ai" target="_blank">UpsonicAI</a>
        </footer>
        <script>
            async function fetchBrandAnalysis() {
                const brand = document.getElementById('brand').value;
                const response = await fetch('/monitor-brand/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ brand_name: brand })
                });
                const data = await response.json();
                
                let resultsHTML = "<h2>Results:</h2>";
                resultsHTML += `<h3>Latest Articles:</h3>`;
                data.top_articles.forEach(article => {
                    resultsHTML += `<p><strong>${article.title}</strong><br>`;
                    resultsHTML += `<a href="${article.url}" target="_blank">Read Article</a></p>`;
                });
                
                resultsHTML += `<h3>Top Influencers:</h3>`;
                data.influencers.forEach(influencer => {
                    resultsHTML += `<p><strong>${influencer.name}</strong><br>`;
                    resultsHTML += `Platform: ${influencer.platform}<br>`;
                    resultsHTML += `Engagement Score: ${influencer.engagement_score}<br>`;
                    resultsHTML += `<a href="${influencer.profile_link}" target="_blank">View Profile</a></p>`;
                });

                document.getElementById('results').innerHTML = resultsHTML;
            }
        </script>
    </body>
    </html>
    """
