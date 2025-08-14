# chatbot/web_search.py
import logging

# Próba importu nowej wersji ddgs, fallback do starej
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

logger = logging.getLogger(__name__)

def ddg_search(query: str, max_results: int = 5) -> str:
    """
    Performs a DuckDuckGo search and returns a formatted string of results.
    """
    if DDGS is None:
        logger.error("DuckDuckGo search library not available.")
        return "Search functionality is not available."
        
    logger.info(f"Performing DDG search for query: '{query}'")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                logger.info("No results found for the query.")
                return "No results found."

            formatted_results = []
            for i, result in enumerate(results):
                formatted_results.append(
                    f"Result {i+1}:\n"
                    f"Title: {result.get('title')}\n"
                    f"Snippet: {result.get('body')}\n"
                    f"URL: {result.get('href')}"
                )
            
            logger.info(f"Found {len(results)} results.")
            return "\n\n---\n\n".join(formatted_results)

    except Exception as e:
        logger.error(f"An error occurred during DuckDuckGo search: {e}", exc_info=True)
        return "An error occurred while searching the web."
