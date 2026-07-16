"""
NUEVO 05: Function Tools - Calculadora (Demo interactiva)

Muestra una herramienta (function tool) de calculadora. El agente puede realizar
cálculos matemáticos llamando a una función de Python normal.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
Mismo patrón que la demo 03 (Azure OpenAI directo). Equivalencias:
  * AzureOpenAIChatClient(endpoint=, deployment_name=, ...)
        -> OpenAIChatClient(azure_endpoint=, model=, api_key=, api_version=)
  * client.create_agent(..., tools=[...])   -> Agent(client, ..., tools=[...])
  * agent.run_stream(texto)                 -> agent.run(texto, stream=True)

Las herramientas NO cambiaron: siguen siendo funciones Python con parámetros
tipados con typing.Annotated[..., Field(description=...)] para que el modelo vea
el esquema. Se pasan en tools=[...].

Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.
"""

import asyncio
import os
from typing import Annotated
from pydantic import Field
from dotenv import load_dotenv

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

# Cargar variables de entorno.
# override=True: el archivo .env03 MANDA sobre variables $env: viejas de la sesión.
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "preview")


# Definir la función de calculadora (herramienta)
def calculate(
    expression: Annotated[str, Field(description="Expresión matemática a evaluar, p. ej. '2 + 2' o '10 * 5'")]
) -> str:
    """Evalúa una expresión matemática."""
    try:
        # Evaluación segura con un namespace limitado
        result = eval(
            expression,
            {"__builtins__": {}},
            {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
            }
        )
        return f"Resultado: {result}"
    except Exception:
        return f"Error: No se pudo calcular '{expression}'"


async def main():
    """Demo interactiva: agente con herramienta de calculadora."""

    print("\n" + "="*70)
    print("🧮 DEMO: Function Tools - Calculadora")
    print("="*70)

    # Cliente Azure OpenAI nativo ('model' = nombre del deployment).
    chat_client = OpenAIChatClient(
        model=DEPLOYMENT,
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    # Agente con la herramienta de calculadora adjunta.
    agent = Agent(
        chat_client,
        instructions="Eres un asistente de matemáticas. Usa la herramienta 'calculate' para los problemas matemáticos.",
        name="CalculatorBot",
        tools=[calculate],
    )

    print("\n✅ Agente creado con la herramienta de calculadora")
    print("💡 TIP: Haz preguntas o cálculos matemáticos")

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
