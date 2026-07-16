"""
NUEVO 01: Crear un agente en Azure AI Foundry (Demo interactiva)

Demo interactiva para crear un nuevo agente en Azure AI Foundry y chatear con él
en tiempo real. El agente es PERSISTENTE: queda publicado como PromptAgent en el
servicio de Azure AI Foundry.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
El tutorial original usaba una API beta que ya no existe. Equivalencias:
  * ChatAgent                      -> Agent
  * AzureAIAgentClient             -> FoundryChatClient (definir) + FoundryAgent (chatear)
  * project_client.create_agent()  -> to_prompt_agent() + AIProjectClient.agents.create_version()
  * agent.run_stream(texto)        -> agent.run(texto, stream=True)

Requisitos para ejecutar:
  1. `az login` (usa AzureCliCredential).
  2. Un proyecto de Azure AI Foundry con un modelo desplegado.
  3. .env01 con AZURE_AI_PROJECT_ENDPOINT y AZURE_AI_MODEL_DEPLOYMENT_NAME.
"""

import asyncio
import os
from dotenv import load_dotenv

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient, FoundryAgent, to_prompt_agent
from azure.identity.aio import AzureCliCredential
from azure.ai.projects.aio import AIProjectClient

# Cargar variables de entorno
load_dotenv('.env01')

PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
AGENT_NAME = "DemoAssistant"


async def main():
    """Demo interactiva: crear agente persistente y chatear."""

    print("\n" + "="*70)
    print("🤖 DEMO: Crear Agente en Azure AI Foundry (Interactivo)")
    print("="*70)

    async with AzureCliCredential() as credential:
        # 1) Definir el agente localmente sobre un FoundryChatClient.
        #    FoundryChatClient no se usa como context manager (no lo soporta).
        chat_client = FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        )
        local_agent = Agent(
            chat_client,
            instructions="Soy un asistente de IA, seré conciso y amable.",
            name=AGENT_NAME,
        )

        # 2) Convertir la definición local a un PromptAgentDefinition y publicarlo.
        #    to_prompt_agent es experimental; emite un ExperimentalWarning (normal).
        definition = to_prompt_agent(local_agent)

        print("\n📋 Publicando el agente en Azure AI Foundry...")

        async with AIProjectClient(
            endpoint=PROJECT_ENDPOINT,
            credential=credential,
        ) as project_client:

            # create_version crea el agente si no existe (versión inicial) o
            # agrega una versión nueva si ya existía.
            created = await project_client.agents.create_version(
                agent_name=AGENT_NAME,
                definition=definition,
            )

            print(f"✅ Agente publicado correctamente!")
            print(f"   Nombre:  {created.name}")
            print(f"   Versión: {created.version}")

            # 3) Conectarse al agente persistente y chatear con streaming.
            async with FoundryAgent(
                project_endpoint=PROJECT_ENDPOINT,
                agent_name=created.name,
                agent_version=created.version,
                credential=credential,
            ) as agent:

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
