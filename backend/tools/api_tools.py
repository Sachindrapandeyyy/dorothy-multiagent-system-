import logging
import httpx
from typing import Dict, Any, List

logger = logging.getLogger("JARVIS.APITools")

# A curated catalog of popular, high-value public APIs matching the public-apis/public-apis schema
PUBLIC_APIS_CATALOG = {
    "bitcoin": {
        "name": "CoinDesk Bitcoin Price Index",
        "description": "Fetch real-time Bitcoin (BTC) price index in USD, GBP, and EUR.",
        "url": "https://api.coindesk.com/v1/bpi/currentprice.json",
        "category": "Finance",
        "auth": "No"
    },
    "ip_geolocation": {
        "name": "IP-API Geolocation",
        "description": "Retrieve geolocation data (country, city, ISP, lat/lon) for your current public IP.",
        "url": "http://ip-api.com/json/",
        "category": "Geocoding",
        "auth": "No"
    },
    "joke": {
        "name": "Official Joke API",
        "description": "Retrieve a random programmer or general setup-and-punchline joke.",
        "url": "https://official-joke-api.appspot.com/random_joke",
        "category": "Entertainment",
        "auth": "No"
    },
    "cat_fact": {
        "name": "Cat Facts API",
        "description": "Fetch a random interesting trivia fact about cats.",
        "url": "https://catfact.ninja/fact",
        "category": "Animals",
        "auth": "No"
    },
    "public_ip": {
        "name": "IPify Public IP",
        "description": "Query your current external/public IP address.",
        "url": "https://api.ipify.org?format=json",
        "category": "Utility",
        "auth": "No"
    }
}

async def get_public_api_list() -> Dict[str, Any]:
    """Retrieve the catalog of supported public APIs integrated into JARVIS."""
    return {
        "success": True,
        "apis": [
            {
                "key": key,
                "name": val["name"],
                "description": val["description"],
                "category": val["category"],
                "auth": val["auth"]
            }
            for key, val in PUBLIC_APIS_CATALOG.items()
        ]
    }

async def fetch_public_api_data(api_key: str) -> Dict[str, Any]:
    """Fetch live real-time JSON data from one of the pre-configured public APIs."""
    api_key_lower = api_key.lower().strip()
    if api_key_lower not in PUBLIC_APIS_CATALOG:
        return {
            "success": False, 
            "error": f"API key '{api_key}' is not pre-configured. Supported keys: {list(PUBLIC_APIS_CATALOG.keys())}"
        }
        
    api_info = PUBLIC_APIS_CATALOG[api_key_lower]
    url = api_info["url"]
    
    try:
        logger.info(f"Fetching data from public API: '{api_info['name']}' at {url}")
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                return {
                    "success": True,
                    "api_name": api_info["name"],
                    "data": data,
                    "message": f"Successfully retrieved live data from {api_info['name']}."
                }
            else:
                return {
                    "success": False,
                    "error": f"API server returned status code {res.status_code}"
                }
    except Exception as e:
        logger.error(f"Error fetching from public API {api_key}: {e}")
        return {"success": False, "error": str(e)}
