"""
NUEVO 03: Chat DIRECTO con Azure OpenAI (Demo interactiva)

Usa Azure OpenAI DIRECTAMENTE (no el Agent Service de Foundry). El agente es
efímero: existe solo durante esta sesión, no se guarda en la nube.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
El tutorial original usaba AzureOpenAIChatClient (API beta). En la versión actual,
`OpenAIChatClient` es NATIVO para Azure: basta con pasarle `azure_endpoint`,
`api_version`, `api_key` y `model` (nombre del deployment). Equivalencias:
  * AzureOpenAIChatClient(endpoint=, deployment_name=, ...)
        -> OpenAIChatClient(azure_endpoint=, model=, api_key=, api_version=)
  * client.create_agent(...)   -> Agent(client, instructions=, name=)
  * agent.run_stream(texto)    -> agent.run(texto, stream=True)

Nota sobre la versión de API:
  El default moderno es "preview" (alias rolling = última preview de Azure), en
  lugar de fijar una fecha como "2025-01-01-preview". `OpenAIChatClient` usa la
  Responses API de Azure OpenAI.

Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.

Utilidad:
    - Demostración de chat directo con Azure OpenAI (sin Agent Service).
    - Ejemplo de agente efímero (no se guarda en la nube).

"""

import asyncio
import os
from dotenv import load_dotenv

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

# Cargar variables de entorno.
# override=True: el archivo .env03 MANDA sobre cualquier variable $env: ya definida
# en la sesión de PowerShell (evita que valores viejos de la terminal pisen al archivo).
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "preview")


async def main():
    """Demo interactiva: chat directo con Azure OpenAI."""

    print("\n" + "="*70)
    print("🤖 DEMO: Chat Directo con Azure OpenAI (sin Agent Service)")
    print("="*70)

    # Cliente Azure OpenAI nativo: 'model' es el nombre del deployment en Azure.
    chat_client = OpenAIChatClient(
        model=DEPLOYMENT,
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    # Agente efímero (vive solo en esta sesión).
    agent = Agent(
        chat_client,
        instructions="Eres un asistente útil. Sé conciso y claro.",
        name="DirectChatBot",
    )

    print("\n✅ Agente creado (temporal, no se guarda en la nube)")

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
