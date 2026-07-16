import urllib.request
import urllib.error
import re

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

from ..base import Tool

class SearchWebTool(Tool):
    name = "SearchWeb"
    description = "Search the web for information using DuckDuckGo."

    schema = {
        "type": "function",
        "function": {
            "name": "SearchWeb",
            "description": "Search the web for a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query."
                    }
                },
                "required": ["query"]
            }
        }
    }

    def __call__(self, *, query: str) -> dict:
        print(f"\033[90m[System] Searching web for: {query}\033[0m")
        
        if not HAS_DDGS:
            return {
                "stdout": "",
                "stderr": "Error: 'duckduckgo-search' library not found. Please install it via `pip install ddgs`.",
                "exit_code": 1,
                "changed_files": []
            }

        try:
            results = []
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=3))
                for r in search_results:
                    results.append(f"Title: {r.get('title')}\nLink: {r.get('href')}\nSnippet: {r.get('body')}\n")
            
            if not results:
                return {
                    "stdout": "No results found.",
                    "stderr": "",
                    "exit_code": 0,
                    "changed_files": []
                }
            
            return {
                "stdout": "\n---\n".join(results),
                "stderr": "",
                "exit_code": 0,
                "changed_files": []
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error searching web: {str(e)}",
                "exit_code": 1,
                "changed_files": []
            }

class FetchURLTool(Tool):
    name = "FetchURL"
    description = "Fetch the content of a URL."

    schema = {
        "type": "function",
        "function": {
            "name": "FetchURL",
            "description": "Fetch text content from a URL. Useful for reading web pages found in search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch."
                    }
                },
                "required": ["url"]
            }
        }
    }

    def __call__(self, *, url: str) -> dict:
        print(f"\033[90m[System] Fetching URL: {url}\033[0m")
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
                text = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.DOTALL)
                text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                
                snippet = text[:2000] + ("... (truncated)" if len(text) > 2000 else "")
                return {
                    "stdout": snippet,
                    "stderr": "",
                    "exit_code": 0,
                    "changed_files": []
                }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error fetching URL: {str(e)}",
                "exit_code": 1,
                "changed_files": []
            }
