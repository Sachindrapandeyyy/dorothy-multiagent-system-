"""
Dorothy OS v2.0 — Public API Tools
Curated free API catalog for real-time data fetching (crypto, geo, facts, etc.).
"""

import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger("Dorothy.Tools.API")

# Curated public API catalog — endpoint name → (url, description)
PUBLIC_APIS_CATALOG: Dict[str, Dict[str, str]] = {
    "bitcoin": {
        "url": "https://api.coindesk.com/v1/bpi/currentprice.json",
        "description": "CoinDesk Bitcoin Price Index — real-time BTC/USD price.",
    },
    "crypto_global": {
        "url": "https://api.coingecko.com/api/v3/global",
        "description": "CoinGecko Global Cryptocurrency Market Data.",
    },
    "ip_geolocation": {
        "url": "http://ip-api.com/json/",
        "description": "IP-API Geolocation — current public IP location data.",
    },
    "cat_fact": {
        "url": "https://catfact.ninja/fact",
        "description": "Cat Facts — random cat fact for entertainment.",
    },
    "public_ip": {
        "url": "https://api.ipify.org?format=json",
        "description": "Ipify — returns your public IP address.",
    },
    "joke": {
        "url": "https://official-joke-api.appspot.com/random_joke",
        "description": "Official Joke API — random programming joke.",
    },
    "weather": {
        "url": "https://wttr.in/?format=j1",
        "description": "Wttr.in — current weather data in JSON format.",
    },
    "quote": {
        "url": "https://api.quotable.io/random",
        "description": "Quotable — random inspirational quote.",
    },
    "dog_image": {
        "url": "https://dog.ceo/api/breeds/image/random",
        "description": "Dog CEO — random dog image URL.",
    },
    "trivia": {
        "url": "https://opentdb.com/api.php?amount=1&type=multiple",
        "description": "Open Trivia DB — random trivia question.",
    },
}


async def fetch_public_api_data(api_key: str) -> Dict[str, Any]:
    """Fetch data from a public API endpoint by catalog key."""
    api_key_lower = api_key.lower().strip()

    if api_key_lower not in PUBLIC_APIS_CATALOG:
        available = ", ".join(sorted(PUBLIC_APIS_CATALOG.keys()))
        return {
            "success": False,
            "error": f"Unknown API key: '{api_key}'. Available: {available}",
        }

    entry = PUBLIC_APIS_CATALOG[api_key_lower]
    url = entry["url"]
    api_name = entry["description"]

    return await asyncio.to_thread(_fetch_api_sync, url, api_key_lower, api_name)


def _fetch_api_sync(url: str, api_key: str, api_name: str) -> Dict[str, Any]:
    """Synchronous API fetcher using httpx."""
    try:
        import httpx

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "api_key": api_key,
                    "api_name": api_name,
                    "data": data,
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "api_key": api_key,
                }
    except ImportError:
        return {"success": False, "error": "httpx is not installed."}
    except Exception as e:
        logger.error(f"API fetch failed for {api_key}: {e}")
        return {"success": False, "error": str(e), "api_key": api_key}


def get_public_api_list() -> List[Dict[str, str]]:
    """Return the complete list of available public API endpoints."""
    return [
        {"key": key, "description": info["description"], "url": info["url"]}
        for key, info in PUBLIC_APIS_CATALOG.items()
    ]


async def web_search(query: str) -> Dict[str, Any]:
    """Search DuckDuckGo HTML interface for query and return top results."""
    query_clean = query.strip()
    if not query_clean:
        return {"success": False, "error": "Search query cannot be empty."}

    url = f"https://html.duckduckgo.com/html/?q={query_clean.replace(' ', '+')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    try:
        import httpx
        import html as html_parser
        import re

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return {"success": False, "error": f"Search engine returned status {resp.status_code}"}

            html_text = resp.text
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html_text, re.S)
            titles = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', html_text, re.S)

            results = []
            for i in range(min(len(titles), len(snippets), 5)):
                title_clean = re.sub(r'<[^<]+?>', '', titles[i]).strip()
                snippet_clean = re.sub(r'<[^<]+?>', '', snippets[i]).strip()
                # Unescape HTML entities
                title_unescaped = html_parser.unescape(title_clean)
                snippet_unescaped = html_parser.unescape(snippet_clean)
                results.append({
                    "title": title_unescaped,
                    "snippet": snippet_unescaped
                })

            if not results:
                return {"success": True, "results": [], "message": f"No search results found for '{query_clean}'."}

            return {
                "success": True,
                "query": query_clean,
                "results": results,
                "message": f"Successfully retrieved {len(results)} search results."
            }

    except Exception as e:
        logger.error(f"Web search failed for query '{query}': {e}")
        return {"success": False, "error": str(e)}
