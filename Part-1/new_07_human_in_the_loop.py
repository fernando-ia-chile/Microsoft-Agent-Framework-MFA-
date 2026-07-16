"""
NUEVO 07: Human-in-the-Loop / Aprobación humana (Demo interactiva)

Dos funciones:
  1. create_file()  - NO requiere aprobación (operación segura)
  2. delete_file()  - REQUIERE aprobación (operación peligrosa)

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
El tutorial original implementaba un wrapper CASERO (`ApprovalRequiredTool`) con
lógica de desanidado de argumentos y prints [DEBUG], porque la API beta NO tenía
aprobación nativa. Eso YA NO es necesario: MFA trae aprobación humana nativa.

  * Wrapper ApprovalRequiredTool(...)          -> @tool(approval_mode="always_require")
  * intercepción manual + callback de input()  -> result.user_input_requests
  * ejecutar/rechazar a mano                   -> req.to_function_approval_response(True/False)
  * AzureOpenAIChatClient(...)                 -> OpenAIChatClient (nativo-Azure)

Cómo funciona el mecanismo nativo:
  - Una tool marcada con approval_mode="always_require" NO se ejecuta sola.
  - En su lugar, agent.run() devuelve `result.user_input_requests` (solicitudes de
    aprobación). Cada una trae `.function_call` (nombre + argumentos).
  - Se responde con `req.to_function_approval_response(aprobado)` y se vuelve a
    llamar a run() con el contexto para que el agente continúe.

Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated
from pydantic import Field
from dotenv import load_dotenv

from agent_framework import Agent, tool, Message
from agent_framework.openai import OpenAIChatClient

# Cargar variables de entorno (el archivo manda sobre $env: viejos de la sesión).
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
DEPLOYMENT = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME')
API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', 'preview')

# Directorio donde se crean/borran los archivos de la demo.
DEMO_DIR = Path(__file__).parent / "demo_files"
DEMO_DIR.mkdir(exist_ok=True)


# ============================================================================
# Herramientas
# ============================================================================

@tool  # Operación segura: se ejecuta directamente, sin aprobación.
def create_file(
    filename: Annotated[str, Field(description="Nombre del archivo a crear")],
    content: Annotated[str, Field(description="Contenido a escribir en el archivo")],
) -> str:
    """Crea un archivo nuevo con contenido."""
    try:
        (DEMO_DIR / filename).write_text(content, encoding='utf-8')
        return f"✅ Archivo '{filename}' creado con {len(content)} caracteres"
    except Exception as e:
        return f"❌ Error creando el archivo: {e}"


@tool(approval_mode="always_require")  # Operación peligrosa: EXIGE aprobación humana.
def delete_file(
    filename: Annotated[str, Field(description="Nombre del archivo a borrar")],
) -> str:
    """Borra un archivo del directorio de la demo."""
    try:
        path = DEMO_DIR / filename
        if path.exists():
            path.unlink()
            return f"🗑️ Archivo '{filename}' borrado correctamente"
        return f"⚠️ Archivo '{filename}' no encontrado en {DEMO_DIR}"
    except Exception as e:
        return f"❌ Error borrando el archivo: {e}"


# ============================================================================
# Aprobación humana (usa el mecanismo NATIVO de MFA)
# ============================================================================

def _formatear_args(function_call) -> str:
    """Muestra los argumentos de la llamada, vengan como dict o como JSON string."""
    args = function_call.arguments
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except Exception:
            return args
    if isinstance(args, dict):
        return ", ".join(f"{k}={v!r}" for k, v in args.items())
    return str(args)


def pedir_aprobacion(function_call) -> bool:
    """Pregunta al usuario si aprueba la ejecución de la función."""
    print("\n" + "=" * 70)
    print("🚨 SE REQUIERE APROBACIÓN")
    print("=" * 70)
    print(f"📝 Función: {function_call.name}")
    print(f"📊 Argumentos: {_formatear_args(function_call)}")
    print("-" * 70)
    while True:
        r = input("⚠️ ¿Apruebas esta acción? (sí/no): ").strip().lower()
        if r in ("si", "sí", "s", "yes", "y"):
            return True
        if r in ("no", "n"):
            return False
        print("   Responde 'sí' o 'no'.")


async def ejecutar_con_aprobaciones(agent, consulta: str) -> str:
    """
    Ejecuta el agente resolviendo en bucle las solicitudes de aprobación.
    Se usa run() sin streaming porque necesitamos inspeccionar
    result.user_input_requests (la lista de aprobaciones pendientes).
    """
    entrada = consulta
    while True:
        result = await agent.run(entrada)

        # Sin solicitudes pendientes -> ya hay respuesta final.
        if not result.user_input_requests:
            return result.text

        # Reconstruir el contexto: la consulta original + por cada solicitud, el
        # mensaje del asistente (la petición) y el del usuario (la respuesta).
        entrada = [consulta]
        for req in result.user_input_requests:
            if req.function_call is None:
                continue
            aprobado = pedir_aprobacion(req.function_call)
            print("✅ APROBADO" if aprobado else "❌ RECHAZADO")
            entrada.append(Message(role="assistant", contents=[req]))
            entrada.append(Message(role="user", contents=[req.to_function_approval_response(aprobado)]))


# ============================================================================
# Demo principal
# ============================================================================

async def main():
    """Ejecuta la demo de human-in-the-loop."""
    print("\n" + "=" * 70)
    print("🔒 DEMO: Human-in-the-Loop - Crear vs Borrar")
    print("=" * 70)
    print("\n📋 Esta demo tiene 2 funciones:")
    print("   ✅ create_file() - Se ejecuta de inmediato (sin aprobación)")
    print("   🔒 delete_file() - Pide tu aprobación primero")

    chat_client = OpenAIChatClient(
        model=DEPLOYMENT,
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    # El agente recibe ambas tools; MFA aplica la aprobación según approval_mode.
    agent = Agent(
        chat_client,
        instructions=(
            "Eres un asistente de gestión de archivos. Cuando el usuario pida crear "
            "un archivo, llama a create_file(); cuando pida borrar, llama a delete_file(). "
            "No pidas confirmación en el chat: el sistema gestiona las aprobaciones."
        ),
        name="FileBot",
        tools=[create_file, delete_file],
    )

    print(f"\n✅ Agente creado. Los archivos se guardan en: {DEMO_DIR.absolute()}/")
    print("\n💡 Prueba:")
    print("   • Crea un archivo llamado test.txt con algún contenido")
    print("   • Borra test.txt")

    print("\n" + "=" * 70)
    print("💬 Chat interactivo (escribe 'quit' para salir)")
    print("=" * 70)

    while True:
        user_input = input("\nTú: ").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 ¡Hasta luego!")
            break

        if not user_input:
            continue

        respuesta = await ejecutar_con_aprobaciones(agent, user_input)
        print(f"Agente: {respuesta}")


if __name__ == "__main__":
    asyncio.run(main())
