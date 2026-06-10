import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Wymuszamy wczytanie pliku .env dokładnie w tym momencie,
# żeby mieć pewność, że klucz będzie dostępny.
load_dotenv()

# Inicjalizacja asynchronicznego klienta OpenAI ze wskazaniem na OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


async def generate_chess_analysis(fen: str, lichess_data: dict, stockfish_data: dict, user_prompt: str = None) -> str:
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

    Dane z Lichess Explorer (częstość ruchów i winrate):
    {json.dumps(lichess_data, indent=2, ensure_ascii=False)}

    Analiza Stockfish (najlepsze linie i ocena):
    {json.dumps(stockfish_data, indent=2, ensure_ascii=False)}
    """

    # Opcjonalny prompt od użytkownika (jeśli wpisze coś w czacie)
    final_user_prompt = user_prompt if user_prompt else "Przeanalizuj tę pozycję. Wskaż dysonans między ruchami ludzi a oceną silnika i wyjaśnij główne plany."

    try:
        # Pobieramy nazwę modelu z .env, a jeśli jej nie ma, używamy Claude'a jako zabezpieczenia
        selected_model = os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")

        response = await client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{context}\n\nPolecenie użytkownika: {final_user_prompt}"}
            ],
            headers={
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "Rajko Chess Analyser",
            }
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Wystąpił błąd komunikacji z OpenRouter: {str(e)}"