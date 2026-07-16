"""
NUEVO 06: Múltiples Function Tools (Demo interactiva)

Muestra un agente con MÚLTIPLES herramientas:
  - Herramienta de clima
  - Herramienta de calculadora
  - Herramienta de zona horaria

El agente elige automáticamente la herramienta correcta según tu pregunta.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
Mismo patrón que las demos 03 y 05 (Azure OpenAI directo). Equivalencias:
  * AzureOpenAIChatClient(...)              -> OpenAIChatClient(azure_endpoint=, model=, api_key=, api_version=)
  * client.create_agent(..., tools=[...])   -> Agent(client, ..., tools=[...])
  * agent.run_stream(texto)                 -> agent.run(texto, stream=True)

Las herramientas son funciones Python normales; pasar varias en tools=[...] no
cambió respecto de la API antigua.

Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.
"""

import asyncio
import os
from typing import Annotated
from pydantic import Field
from dotenv import load_dotenv
import requests

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

# Cargar variables de entorno.
# override=True: el archivo .env03 MANDA sobre variables $env: viejas de la sesión.
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "preview")


# Herramienta 1: Clima
def get_weather(
    location: Annotated[str, Field(description="Nombre de la ciudad")]
) -> str:
    """Obtiene el clima actual de una ubicación."""
    weather_data = {
        "london": "🌧️ 15°C, Lluvioso",
        "paris": "☀️ 22°C, Soleado",
        "tokyo": "⛅ 18°C, Parcialmente nublado",
        "new york": "🌤️ 20°C, Despejado"
    }
    return weather_data.get(location.lower(), f"No hay datos de clima para {location}")


# Herramienta 2: Calculadora
def calculate(
    expression: Annotated[str, Field(description="Expresión matemática")]
) -> str:
    """Calcula una expresión matemática."""
    try:
        result = eval(expression, {"__builtins__": {}}, {
            "abs": abs, "round": round, "min": min, "max": max, "pow": pow
        })
        return f"Resultado: {result}"
    except Exception:
        return f"No se pudo calcular '{expression}'"


# Herramienta 3: Zona Horaria
def get_time(
    timezone: Annotated[str, Field(description="Zona horaria como 'America/New_York' o 'Europe/London'")]
) -> str:
    """Obtiene la hora actual en una zona horaria."""
    try:
        response = requests.get(f"http://worldtimeapi.org/api/timezone/{timezone}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            time = data.get('datetime', '').split('T')[1].split('.')[0]
            return f"⏰ Hora actual en {timezone}: {time}"
        else:
            return f"No se pudo obtener la hora para {timezone}"
    except Exception:
        return f"Error obteniendo la hora para {timezone}"


async def main():
    """Demo interactiva: agente con múltiples herramientas."""

    print("\n" + "="*70)
    print("🛠️ DEMO: Múltiples Function Tools")
    print("="*70)

    # Cliente Azure OpenAI nativo ('model' = nombre del deployment).
    chat_client = OpenAIChatClient(
        model=DEPLOYMENT,
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    # Agente con las 3 herramientas adjuntas; el modelo elige cuál usar.
    agent = Agent(
        chat_client,
        instructions="Eres un asistente útil con herramientas de clima, calculadora y hora. Elige la herramienta correcta automáticamente.",
        name="MultiToolBot",
        tools=[get_weather, calculate, get_time],
    )

    print("\n✅ Agente creado con 3 herramientas:")
    print("   🌤️  Herramienta de clima")
    print("   🧮 Herramienta de calculadora")
    print("   ⏰ Herramienta de zona horaria")

    print("\n" + "="*70)
    print("💬 Chat interactivo (escribe 'quit' para salir)")
    print("="*70 + "\n")

    while True:
        user_input = input("Tú: ")

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 ¡Hasta luego!")
            break

        if not user_input.strip():
            continue

        # Respuesta en streaming (token a token)
        print("Agente: ", end="", flush=True)
        async for chunk in agent.run(user_input, stream=True):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
