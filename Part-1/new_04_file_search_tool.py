"""
NUEVO 04: Herramienta de Búsqueda de Archivos / File Search (Demo interactiva)

Muestra cómo darle a un agente de Azure AI Foundry la capacidad de buscar dentro
de documentos indexados en un VECTOR STORE. El agente responde "grounded" en el
contenido de tus archivos.

NOTA: Debes crear un vector store y subir archivos ANTES (en el portal de Azure
AI Foundry) y poner su ID en .env01 como VECTOR_STORE_ID.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
El tutorial original usaba `HostedFileSearchTool(inputs=[HostedVectorStoreContent(...)])`
+ `AzureAIAgentClient`, todo eliminado en la API actual. El método vigente (según la
doc oficial de Microsoft Foundry) es:
  * AzureAIAgentClient(...)                      -> FoundryChatClient(...)
  * HostedFileSearchTool(inputs=[HostedVectorStoreContent(vector_store_id=...)], max_results=)
        -> client.get_file_search_tool(vector_store_ids=[...], max_num_results=)
  * ChatAgent(..., tools=[...])                  -> Agent(client, ..., tools=[...])
  * agent.run_stream(texto)                      -> agent.run(texto, stream=True)

Requisitos:
  1. `az login`.
  2. .env01 con AZURE_AI_PROJECT_ENDPOINT, AZURE_AI_MODEL_DEPLOYMENT_NAME y VECTOR_STORE_ID.
"""

import asyncio
import os
from dotenv import load_dotenv

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import AzureCliCredential

# Cargar variables de entorno
load_dotenv('.env01')

PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")

# IMPORTANTE: reemplaza con el ID real de tu vector store de Azure AI Foundry.
# Puedes crear un vector store en el portal y subir archivos (PDF, TXT, DOCX).
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID", "YOUR_VECTOR_STORE_ID_HERE")


async def main():
    """Demo interactiva: agente con herramienta de File Search."""

    print("\n" + "="*70)
    print("🔍 DEMO: Herramienta de Búsqueda de Archivos (File Search)")
    print("="*70)

    if VECTOR_STORE_ID in ("YOUR_VECTOR_STORE_ID_HERE", "", "xxxx", None):
        print("\n⚠️  ADVERTENCIA: Configura VECTOR_STORE_ID en el archivo .env01")
        print("   1. Entra al portal de Azure AI Foundry")
        print("   2. Crea un Vector Store")
        print("   3. Sube documentos (PDF, TXT, DOCX)")
        print("   4. Copia el ID del Vector Store")
        print("   5. Agrega VECTOR_STORE_ID=tu_id a .env01")
        print("\n   Sin un vector store válido, la búsqueda de archivos no funcionará.\n")

    async with AzureCliCredential() as credential:
        # Cliente de Foundry ligado al proyecto + modelo desplegado.
        # FoundryChatClient NO es context manager (no soporta 'async with').
        chat_client = FoundryChatClient(
            project_endpoint=PROJECT_ENDPOINT,
            model=MODEL_DEPLOYMENT,
            credential=credential,
        )

        # Método MODERNO para la herramienta de file search (reemplaza a
        # HostedFileSearchTool + HostedVectorStoreContent).
        file_search_tool = chat_client.get_file_search_tool(
            vector_store_ids=[VECTOR_STORE_ID],
            max_num_results=5,
        )

        # Agente con la herramienta adjunta.
        agent = Agent(
            chat_client,
            instructions=(
                "Eres un asistente de búsqueda de documentos. Usa la herramienta de "
                "file search para encontrar información en los documentos indexados."
            ),
            name="FileSearchBot",
            tools=[file_search_tool],
        )

        print("\n✅ Agente creado con la herramienta de File Search")
        print("💡 TIP: Pregunta cosas sobre los documentos de tu vector store")

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
