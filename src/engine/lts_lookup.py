# -*- coding: utf-8 -*-
import requests
import logging
from src.engine.config import HTTP_TIMEOUT_SECONDS, END_OF_LIFE_API_URL

logger = logging.getLogger("devops-agent")

class LTSLookup:
    """
    Dynamically fetches LTS versions for runtimes using the endoflife.date API.
    """
    
    @staticmethod
    def get_lts_version(runtime: str) -> str:
        """
        Fetches the latest LTS version for a given runtime (e.g., 'node', 'python').
        """
        runtime = runtime.lower()
        if runtime == "javascript/node": runtime = "nodejs"
        
        try:
            url = f"{END_OF_LIFE_API_URL}/{runtime}.json"
            response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
            if response.status_code == 200:
                data = response.json()
                # Find the first one with lts: true or the latest stable
                for release in data:
                    if release.get("lts"):
                        return release.get("cycle")
                # Fallback to the latest cycle
                return data[0].get("cycle")
        except Exception as e:
            logger.warning(f"LTS lookup failed for {runtime}: {e}")
            
        # Hardcoded fallbacks
        fallbacks = {
            "nodejs": "20",
            "python": "3.11",
            "go": "1.21"
        }
        return fallbacks.get(runtime, "latest")
