"""
NUEVO 02: Usar un agente EXISTENTE de Azure AI Foundry (Demo interactiva)

Esta demo se conecta a un agente que YA existe en Azure AI Foundry (p. ej. el
"DemoAssistant" que publicó la demo 01) y chatea con él, sin volver a crearlo.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
El tutorial original se conectaba por ID de agente (AZURE_AI_AGENT_ID) usando
AzureAIAgentClient. En la API actual, un PromptAgent de Foundry se identifica por
NOMBRE + VERSIÓN, y la conexión se hace con FoundryAgent. Equivalencias:
  * AzureAIAgentClient(agent_id=...)  -> FoundryAgent(agent_name=..., agent_version=...)
  * agent.run_stream(texto)           -> agent.run(texto, stream=True)

Si no fijas la versión en .env02, esta demo resuelve automáticamente la ÚLTIMA.

Requisitos:
  1. `az login`.
  2. Un agente ya publicado en el proyecto (corre primero new_01).
  3. .env02 con AZURE_AI_PROJECT_ENDPOINT y AZURE_AI_AGENT_NAME.
"""

import asyncio
import os
from dotenv import load_dotenv

from agent_framework.foundry import FoundryAgent
from azure.identity.aio import AzureCliCredential
from azure.ai.projects.aio import AIProjectClient

# Cargar variables de entorno
load_dotenv('.env02')

PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
AGENT_NAME = os.getenv("AZURE_AI_AGENT_NAME")
AGENT_VERSION = os.getenv("AZURE_AI_AGENT_VERSION")  # opcional

# Esta función resuelve la última versión publicada de un agente si no se especifica ninguna.
async def resolve_latest_version(project_client, agent_name: str) -> str | None:
    """Devuelve la última versión publicada del agente (o None si no existe)."""
    async for version in project_client.agents.list_versions(
        agent_name, order="desc", limit=1
    ):
        return version.version
    return None


async def main():
    """Demo interactiva: conectarse a un agente existente."""

    print("\n" + "="*70)
    print("🔗 DEMO: Conectar a un Agente EXISTENTE de Azure AI Foundry")
    print("="*70)

    print(f"\n📋 Agente objetivo: {AGENT_NAME}")

    # Resolver la versión del agente (fijada en .env02 o la última publicada)
    async with (
        AzureCliCredential() as credential,
        AIProjectClient(
            endpoint=PROJECT_ENDPOINT,
            credential=credential,
        ) as project_client,
    ):
        # Resolver la versión: la fijada en .env02 o, si no, la última publicada.
        version = AGENT_VERSION or await resolve_latest_version(project_client, AGENT_NAME)
        if not version:
            print(f"\n❌ No se encontró ninguna versión del agente '{AGENT_NAME}'.")
            print("   ¿Ya lo creaste? Corre primero: python new_01_create_agent.py")
            return

        print(f"🔢 Usando versión: {version}")

        # Conectarse al agente persistente (reutiliza el mismo project_client).
        async with FoundryAgent(
            project_client=project_client,
            agent_name=AGENT_NAME,
            agent_version=version,
        ) as agent:
            print("✅ ¡Conectado correctamente!")

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