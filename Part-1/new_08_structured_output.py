"""
NUEVO 08: Salida Estructurada con Pydantic (Demo interactiva)

Muestra cómo extraer datos estructurados desde texto usando un modelo Pydantic.
El agente devuelve un objeto Python tipado en vez de texto plano.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
Mismo cliente que las demos 03/05/06 (Azure OpenAI directo). Cambio clave respecto
del tutorial original: `response_format` YA NO es un argumento directo de run();
ahora va dentro de `options`. Equivalencias:
  * AzureOpenAIChatClient(...)                          -> OpenAIChatClient (nativo-Azure)
  * agent.run(texto, response_format=Modelo)            -> agent.run(texto, options={"response_format": Modelo})
  * response.value  (objeto Pydantic parseado)          -> igual: response.value

  ejemplo de uso: Hola soy Fernando, tengo 49 años, soy ingeniero y vivo en Santiago de Chile, me gusta el futbol
Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.
"""

import asyncio
import os
from pydantic import BaseModel
from dotenv import load_dotenv

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

# Cargar variables de entorno (el archivo manda sobre $env: viejos de la sesión).
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "preview")


# Modelo de salida estructurada: define el esquema que el modelo debe rellenar.
class PersonInfo(BaseModel):
    """Información de una persona extraída del texto."""
    name: str | None = None
    age: int | None = None
    occupation: str | None = None
    city: str | None = None


async def main():
    """Demo interactiva: extracción de datos estructurados."""

    print("\n" + "="*70)
    print("📊 DEMO: Salida Estructurada con Pydantic")
    print("="*70)

    # Cliente Azure OpenAI nativo ('model' = nombre del deployment).
    chat_client = OpenAIChatClient(
        model=DEPLOYMENT,
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    agent = Agent(
        chat_client,
        instructions="Extrae la información de la persona a partir del texto del usuario.",
        name="ExtractorBot",
    )

    print("\n✅ Agente creado con el esquema PersonInfo")
    print("📋 Esquema: name, age, occupation, city")

    print("\n" + "="*70)
    print("💬 Chat interactivo (escribe 'quit' para salir)")
    print("="*70)
    print("\n💡 TIP: Describe a una persona y observa la extracción estructurada\n")

    while True:
        user_input = input("Tú: ")

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 ¡Hasta luego!")
            break

        if not user_input.strip():
            continue

        # Respuesta estructurada: se pasa el modelo Pydantic en options["response_format"].
        # NO se usa streaming aquí; se lee el objeto tipado desde response.value.
        print("\n🔄 Extrayendo datos estructurados...")
        response = await agent.run(user_input, options={"response_format": PersonInfo})

        person = response.value
        if person:
            print("\n📊 Información extraída:")
            print(f"   Nombre:     {person.name}")
            print(f"   Edad:       {person.age}")
            print(f"   Ocupación:  {person.occupation}")
            print(f"   Ciudad:     {person.city}")
        else:
            print("❌ No se pudo extraer información")

        print()
       

if __name__ == "__main__":
    asyncio.run(main())
