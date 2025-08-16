"""
Agent implementations for Django Agent system.
"""

import logging
import re
from abc import ABC
from typing import Any

import httpx

from ..interfaces import AgentResponse, BaseAgentInterface, ErrorSeverity
from ..rag_processor import rag_processor
from ..weather_service import get_weather
from ..web_search import ddg_search
from .async_services import AsyncPantryService

logger = logging.getLogger(__name__)


class BaseAgent(BaseAgentInterface, ABC):
    """
    Enhanced base agent with error handling and metadata support.
    """

    def __init__(self, name: str = "BaseAgent", **kwargs):
        self.name = name
        self.config = kwargs.get("config", {})
        self.capabilities = kwargs.get("capabilities", [])

    def get_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "capabilities": self.capabilities,
            "config": self.config,
        }

    def is_healthy(self) -> bool:
        return True

    async def safe_process(self, input_data: dict[str, Any]) -> AgentResponse:
        try:
            return await self.process(input_data)
        except Exception as e:
            logger.error(f"Error in {self.name}.process: {str(e)}", exc_info=True)
            return AgentResponse(
                success=False, error=str(e), severity=ErrorSeverity.HIGH.value
            )


class OllamaAgent(BaseAgent):
    """
    Agent that connects to an Ollama server for generating responses.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "OllamaAgent")
        super().__init__(**kwargs)
        self.capabilities = ["llm_chat", "dynamic_response_generation"]
        self.ollama_url = self.config.get("ollama_url", "http://127.0.0.1:11434")
        self.model = self.config.get("model", "SpeakLeash/bielik-11b-v2.3-instruct:Q5_K_M")
        self.fallback_models = ["ollama", "simple_rules"]

    async def health_check_ollama(self) -> bool:
        """Check if Ollama server is available."""
        proxies = {
            "http://": None,
            "https://": None,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {
                    'User-Agent': 'curl/7.81.0',
                }
                base_url = self.ollama_url.strip('/')
                full_url = f"{base_url}/api/tags"
                response = await client.get(full_url, headers=headers)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}", exc_info=True)
            return False

    async def process(self, input_data: dict[str, Any]) -> AgentResponse:
        user_message = input_data.get("message", "")
        history = input_data.get("history", [])

        # Try fallback system
        for model in self.fallback_models:
            try:
                if model == "ollama":
                    # Check Ollama health first
                    if not await self.health_check_ollama():
                        logger.warning(
                            "Ollama server not available, trying next fallback"
                        )
                        continue

                    return await self.process_with_ollama(input_data)
                elif model == "simple_rules":
                    return await self.rule_based_fallback(input_data)
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}")
                continue

        return AgentResponse(
            success=False,
            error="All fallback models failed",
            severity=ErrorSeverity.CRITICAL.value,
        )

    async def process_with_ollama(self, input_data: dict[str, Any]) -> AgentResponse:
        user_message = input_data.get("message", "")
        history = input_data.get("history", [])

        formatted_messages = []
        current_datetime = input_data.get("current_datetime")
        if current_datetime:
            formatted_messages.append(
                {
                    "role": "system",
                    "content": f"Current date and time: {current_datetime}",
                }
            )

        formatted_messages.extend(
            [{"role": msg["role"], "content": msg["content"]} for msg in history]
        )
        formatted_messages.append({"role": "user", "content": user_message})

        payload = {"model": self.model, "messages": formatted_messages, "stream": False}

        proxies = {
            "http://": None,
            "https://": None,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                'User-Agent': 'curl/7.81.0',
                'Content-Type': 'application/json'
            }
            base_url = self.ollama_url.strip('/')
            full_url = f"{base_url}/api/chat"
            response = await client.post(full_url, json=payload, headers=headers)
            response.raise_for_status()
            ollama_response = response.json()
            response_text = ollama_response.get("message", {}).get("content", "")
            return AgentResponse(
                success=True,
                data={
                    "response": response_text,
                    "agent": self.name,
                    "response_type": "llm_chat",
                },
                metadata=ollama_response.get("metadata", {}),
            )

    async def rule_based_fallback(self, input_data: dict[str, Any]) -> AgentResponse:
        """Simple rule-based fallback when LLM is not available."""
        user_message = input_data.get("message", "").lower()

        # Simple greeting responses
        greetings = ["cześć", "hej", "witam", "dzień dobry", "hi", "hello"]
        if any(greeting in user_message for greeting in greetings):
            response = "Cześć! Niestety, główny system AI jest obecnie niedostępny, ale mogę Ci pomóc w podstawowych kwestiach."
        else:
            response = "Przepraszam, główny system AI jest obecnie niedostępny. Spróbuj ponownie za chwilę lub skontaktuj się z administratorem."

        return AgentResponse(
            success=True,
            data={
                "response": response,
                "agent": f"{self.name}_fallback",
                "response_type": "rule_based",
            },
            metadata={"fallback_used": True},
        )


class RouterAgent(OllamaAgent):
    """
    An autonomous agent that can decide which tool to use (RAG, Web Search, Weather)
    or just chat, based on the user's query and conversation history.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "RouterAgent")
        super().__init__(**kwargs)
        self.capabilities.extend(["router", "tool_user", "autonomous_reasoning"])

        # Few-shot examples for better routing
        self.router_examples = """
Przykłady:

Wiadomość: "Jaka jest pogoda w Krakowie?"
Narzędzie: weather_service

Wiadomość: "Wyszukaj informacje o nowym iPhone"
Narzędzie: web_search

Wiadomość: "Co mam w lodówce?"
Narzędzie: pantry_management

Wiadomość: "Opowiedz o dokumencie ABC.pdf"
Narzędzie: rag_search

Wiadomość: "Jak się masz?"
Narzędzie: general_conversation
"""

        # Rule-based patterns for immediate routing
        self.routing_patterns = {
            "weather_service": [
                r"\b(pogoda|temperatur[ae]|deszcz|słońce|chłodno|ciepło|wiatr|śnieg)\b",
                r"\b(jaka.*pogoda|jak.*pogoda|czy.*pada|czy.*świeci)\b",
            ],
            "web_search": [
                r"\b(wyszukaj|znajdź|poszukaj|sprawdź w internecie|googluj)\b",
                r"\b(najnowsze|aktualn[ey]|co nowego|informacj[ae])\b",
            ],
            "pantry_management": [
                r"\b(spiżarni[ae]|lodówc[ae]|produkty|jedzeni[ae]|co mam)\b",
                r"\b(ile mam|czy mam|lista produktów)\b",
            ],
            "rag_search": [
                r"\b(dokument|plik|pdf|tekst|treść|przeczytaj)\b",
                r"\b(co jest w|opowiedz o|znajdź w dokumencie)\b",
            ],
        }

    async def process(self, input_data: dict[str, Any]) -> AgentResponse:
        user_message = input_data.get("message", "")
        history = input_data.get("history", [])

        # Hardcoded rule for simple greetings
        greetings = ["cześć", "hej", "witam", "dzień dobry", "hi", "hello"]
        if user_message.strip().lower() in greetings:
            logger.info("Greeting detected, skipping router.")
            return await super().process(input_data)

        # 1. Try rule-based routing first (faster and more reliable)
        chosen_tool = self._rule_based_routing(user_message)

        if chosen_tool:
            logger.info(f"Rule-based routing selected: '{chosen_tool}'")
        else:
            # 2. Fallback to LLM-based routing with few-shot examples
            chosen_tool = await self._llm_based_routing(user_message)
            logger.info(f"LLM-based routing selected: '{chosen_tool}'")

        # 3. Execute the chosen tool's logic
        if chosen_tool == "web_search":
            return await self._execute_web_search(input_data)
        elif chosen_tool == "weather_service":
            return await self._execute_weather_service(input_data)
        elif chosen_tool == "rag_search":
            return await self._execute_rag_search(input_data)
        elif chosen_tool == "pantry_management":
            return await self._execute_pantry_management(input_data)
        else:  # general_conversation
            return await super().process(input_data)

    def _rule_based_routing(self, user_message: str) -> str | None:
        """Fast rule-based routing for common patterns."""
        message_lower = user_message.lower()

        # Check each tool pattern
        for tool, patterns in self.routing_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return tool

        # Check for simple greetings
        greetings = [
            "cześć",
            "hej",
            "witam",
            "dzień dobry",
            "hi",
            "hello",
            "jak się masz",
        ]
        if any(greeting in message_lower for greeting in greetings):
            return "general_conversation"

        return None

    async def _llm_based_routing(self, user_message: str) -> str:
        """LLM-based routing with few-shot examples."""
        tools = [
            "web_search: Służy do wyszukiwania aktualnych informacji w internecie, faktów, wiadomości lub odpowiadania na ogólne pytania.",
            "weather_service: Służy do sprawdzania aktualnej prognozy pogody dla konkretnej lokalizacji.",
            "rag_search: Służy do odpowiadania na pytania dotyczące treści dokumentów, które wcześniej przesłał użytkownik.",
            "pantry_management: Służy do sprawdzania zawartości spiżarni, dodawania lub usuwania produktów.",
            "general_conversation: Służy do prowadzenia zwykłej rozmowy, powitań, lub gdy żadne inne narzędzie nie jest odpowiednie.",
        ]

        routing_prompt = (
            f"{self.router_examples}\n\n"
            f"Narzędzia dostępne:\n{chr(10).join(tools)}\n\n"
            f"Na podstawie powyższych przykładów, wybierz najbardziej odpowiednie narzędzie dla następującej wiadomości. "
            f"Odpowiedz TYLKO nazwą narzędzia (np. weather_service).\n\n"
            f"Wiadomość użytkownika: {user_message}\n\nNarzędzie:"
        )

        routing_input = {"message": routing_prompt, "history": []}
        try:
            decision_response = await super().process(routing_input)
            if not decision_response.success:
                return "general_conversation"

            response_text = decision_response.data.get(
                "response", "general_conversation"
            ).strip()

            # Enhanced parsing with regex
            response_text = re.sub(r"[^a-z_]", "", response_text.lower())

            # Find exact match
            for tool_name in [
                "web_search",
                "weather_service",
                "rag_search",
                "pantry_management",
                "general_conversation",
            ]:
                if tool_name in response_text:
                    return tool_name

            return "general_conversation"
        except Exception as e:
            logger.error(f"LLM routing failed: {e}")
            return "general_conversation"

    async def _execute_rag_search(self, input_data):
        user_message = input_data.get("message", "")
        retrieved_context = rag_processor.retrieve_context(user_message, n_results=3)
        if not retrieved_context:
            return await super().process(input_data)
        context_str = "\n\n---\n\n".join(retrieved_context)
        augmented_prompt = f"Na podstawie kontekstu z dokumentów: '{context_str}', odpowiedz na pytanie: '{user_message}'"
        input_data["message"] = augmented_prompt
        return await super().process(input_data)

    async def _execute_web_search(self, input_data):
        user_message = input_data.get("message", "")
        search_results = ddg_search(user_message)
        augmented_prompt = f"Na podstawie wyników wyszukiwania: '{search_results}', odpowiedz na pytanie: '{user_message}'"
        input_data["message"] = augmented_prompt
        return await super().process(input_data)

    async def _execute_weather_service(self, input_data):
        user_message = input_data.get("message", "")
        city_prompt = f"Z pytania: '{user_message}' wyekstrahuj tylko nazwę miasta w mianowniku. Jeśli nie ma miasta, odpowiedz 'brak'."
        city_input = {"message": city_prompt, "history": []}
        city_response = await super().process(city_input)
        city = city_response.data.get("response", "").strip()
        if city and "brak" not in city.lower():
            weather_data = get_weather(city)
            augmented_prompt = (
                f"Oto dane pogodowe: {weather_data}. Odpowiedz na pytanie użytkownika."
            )
            input_data["message"] = augmented_prompt
            return await super().process(input_data)
        return await super().process(input_data)  # Fallback if no city

    async def _execute_pantry_management(self, input_data):
        user_message = input_data.get("message", "")

        # Determine if user is asking about a specific item or general pantry content
        # This requires another LLM call to classify the query type
        classification_prompt = f"""
        Użytkownik pyta o spiżarnię. Zdecyduj, czy pyta o konkretny produkt, czy o ogólną zawartość spiżarni.
        Odpowiedz tylko jednym słowem: 'specific' lub 'general'.
        Pytanie użytkownika: {user_message}
        """
        classification_input = {"message": classification_prompt, "history": []}
        classification_response = await super().process(classification_input)
        query_type = (
            classification_response.data.get("response", "general").strip().lower()
        )

        pantry_info = ""
        if query_type == "specific":
            # Extract product name for specific query
            product_name_prompt = f"Z pytania: '{user_message}' wyekstrahuj tylko nazwę produktu, o który pyta użytkownik. Odpowiedz tylko nazwą produktu."
            product_name_input = {"message": product_name_prompt, "history": []}
            product_name_response = await super().process(product_name_input)
            product_name = product_name_response.data.get("response", "").strip()

            if product_name:
                item = await AsyncPantryService.find_item_by_name(product_name)
                if item:
                    pantry_info = f"W spiżarni masz {item['quantity']} {item['unit']} {item['name']}."
                else:
                    pantry_info = f"Nie znalazłem {product_name} w spiżarni."
            else:
                pantry_info = "Nie rozumiem, o jaki konkretny produkt pytasz."
        else:  # general
            all_items = await AsyncPantryService.get_all_items()
            if all_items:
                pantry_info = "W spiżarni masz:\n"
                for item in all_items:
                    pantry_info += (
                        f"- {item['name']}: {item['quantity']} {item['unit']}\n"
                    )
            else:
                pantry_info = "Twoja spiżarnia jest pusta."

        augmented_prompt = f"Oto informacje o spiżarni: '{pantry_info}'. Odpowiedz na pytanie użytkownika: '{user_message}'"
        input_data["message"] = augmented_prompt
        return await super().process(input_data)
