import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Lokalny backend/.env jest przydatny w trybie developerskim, ale produkcyjne
# zmienne z systemd EnvironmentFile muszą mieć pierwszeństwo.
load_dotenv()

# Inicjalizacja asynchronicznego klienta OpenAI ze wskazaniem na OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY") or "missing-openrouter-api-key",
)

AVAILABLE_MODELS = [
    {
        "id": "google/gemini-3-flash-preview",
        "label": "Gemini 3 Flash Preview",
        "description": "Szybki i tani",
        "input_price": 0.5,
        "output_price": 3.0,
    },
    {
        "id": "anthropic/claude-sonnet-4.6",
        "label": "Claude Sonnet 4.6",
        "description": "Najwyższa jakość",
        "input_price": 3.0,
        "output_price": 15.0,
    },
]
AVAILABLE_MODEL_IDS = {model["id"] for model in AVAILABLE_MODELS}
FALLBACK_MODEL = "google/gemini-3-flash-preview"
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:5173")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "Rajko Chess Analyser")


def has_openrouter_api_key() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def get_default_model() -> str:
    configured_model = os.getenv("LLM_MODEL", FALLBACK_MODEL)
    return configured_model if configured_model in AVAILABLE_MODEL_IDS else FALLBACK_MODEL


async def generate_chess_analysis(
        fen: str,
        lichess_data: dict,
        stockfish_data: dict,
        user_prompt: str = None,
        model: str = None
) -> str:
    """
    Wysyła zebrane dane do LLM przez OpenRouter i zwraca analizę szachową.
    """

    # "Dusza" naszego agenta - tutaj definiujemy, jak ma się zachowywać
    system_prompt = """
    Jesteś arcymistrzem szachowym i wybitnym analitykiem. 
    Otrzymujesz od systemu aktualną pozycję (FEN), statystyki z bazy Lichess (ruchy ludzi) oraz bezbłędną analizę silnika Stockfish.

    Twoje zadanie:
    1. Porównaj to, co grają ludzie, z tym, co uważa za najlepsze Stockfish.
    2. Szukaj "pułapek" - sytuacji, w których najpopularniejszy ludzki ruch jest obiektywnie słaby (Stockfish ocenia go nisko).
    3. Krótko i przystępnie wyjaśnij, DLACZEGO dany ruch jest dobry lub zły. Wspomnij o planach strategicznych.
    4. Używaj języka naturalnego, bądź zwięzły i stosuj formatowanie Markdown (np. pogrubienia dla notacji ruchów).
    """

    # Budujemy kontekst - pakujemy nasze słowniki Pythona do ładnych stringów JSON
    context = f"""
    Aktualna pozycja (FEN): {fen}

    Nazwa otwarcia w danych Lichess może mieć opening_is_fallback=true.
    Oznacza to ostatnie znane otwarcie z wcześniejszej pozycji w tej partii,
    a nie klasyfikację dokładnie bieżącej pozycji.

    Dane z Lichess Explorer (częstość ruchów i winrate):
    {json.dumps(lichess_data, indent=2, ensure_ascii=False)}

    Analiza Stockfish (najlepsze linie i ocena):
    {json.dumps(stockfish_data, indent=2, ensure_ascii=False)}
    """

    # Opcjonalny prompt od użytkownika (jeśli wpisze coś w czacie)
    final_user_prompt = user_prompt if user_prompt else "Przeanalizuj tę pozycję. Wskaż dysonans między ruchami ludzi a oceną silnika i wyjaśnij główne plany."

    try:
        if not has_openrouter_api_key():
            return "Brak OPENROUTER_API_KEY w konfiguracji backendu. Uzupełnij klucz, żeby używać panelu LLM."

        selected_model = model or get_default_model()

        response = await client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{context}\n\nPolecenie użytkownika: {final_user_prompt}"}
            ],
            extra_headers={
                "HTTP-Referer": OPENROUTER_HTTP_REFERER,
                "X-Title": OPENROUTER_APP_TITLE,
            }
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Wystąpił błąd komunikacji z OpenRouter: {str(e)}"


async def generate_game_analysis(
        pgn: str,
        engine_analysis: dict,
        metadata: dict,
        user_prompt: str = None,
        model: str = None,
) -> str:
    system_prompt = """
    Jesteś wymagającym, ale przystępnym trenerem szachowym. Analizujesz zakończoną
    partię na podstawie PGN oraz pomiarów Stockfisha. Oceny silnika są podane
    z perspektywy białych. Nie wymyślaj wariantów, których nie ma w danych.

    Przygotuj analizę po polsku:
    1. Krótkie podsumowanie przebiegu partii.
    2. Najważniejsze momenty zwrotne, ze szczególnym uwzględnieniem ruchów gracza.
    3. Wyjaśnienie przyczyn błędów i lepszych planów, nie tylko samych wariantów.
    4. Trzy konkretne zalecenia treningowe.
    Stosuj zwięzły Markdown i szachową notację SAN.
    """
    llm_engine_context = {
        "headers": engine_analysis.get("headers"),
        "move_count": engine_analysis.get("move_count"),
        "critical_moments": engine_analysis.get("critical_moments"),
    }
    context = f"""
    Metadane importu:
    {json.dumps(metadata, indent=2, ensure_ascii=False)}

    PGN partii:
    {pgn}

    Krytyczne momenty według Stockfisha:
    {json.dumps(llm_engine_context, indent=2, ensure_ascii=False)}
    """
    final_user_prompt = user_prompt or "Przeanalizuj całą partię i wskaż, nad czym powinienem pracować."
    selected_model = model or get_default_model()

    try:
        if not has_openrouter_api_key():
            return "Brak OPENROUTER_API_KEY w konfiguracji backendu. Uzupełnij klucz, żeby analizować partie przez LLM."

        response = await client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{context}\n\nPolecenie użytkownika: {final_user_prompt}"},
            ],
            extra_headers={
                "HTTP-Referer": OPENROUTER_HTTP_REFERER,
                "X-Title": OPENROUTER_APP_TITLE,
            },
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Wystąpił błąd komunikacji z OpenRouter: {str(e)}"
