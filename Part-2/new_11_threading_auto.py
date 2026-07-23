"""
NUEVO 11: Sesiones con auto-serialización (Demo interactiva)

Objetivo pedagógico (sin cambios respecto del original):
    Demostrar que el estado de una conversación se puede GUARDAR en disco y
    RESTAURAR, y que el agente sigue recordando todo. Tras CADA mensaje se hace
    el ciclo completo: serializar -> guardar a JSON -> leer del JSON ->
    deserializar -> seguir conversando con la sesión restaurada.
    Además, al arrancar se reanuda la conversación de la ejecución anterior.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
El tutorial original usaba la API beta de "threads". En la versión actual el
concepto se llama SESIÓN y la serialización dejó de ser asíncrona:

  * AzureOpenAIChatClient(endpoint=, deployment_name=, ...)
        -> OpenAIChatClient(azure_endpoint=, model=, api_key=, api_version=)
  * client.create_agent(...)          -> Agent(client, instructions=, name=)
  * agent.get_new_thread()            -> agent.create_session()
  * agent.run_stream(x, thread=t)     -> agent.run(x, stream=True, session=s)
  * await thread.serialize()          -> session.to_dict()          (SÍNCRONO)
  * await agent.deserialize_thread(d) -> AgentSession.from_dict(d)  (SÍNCRONO)
  * ChatMessage (privado, agent_framework._types) -> Message (público)

Simplificación importante:
    El código viejo tenía que convertir a mano cada ChatMessage con to_dict() /
    from_dict() porque `thread.serialize()` devolvía objetos Pydantic que
    `json.dump` no sabía escribir. Ya NO hace falta: `session.to_dict()`
    devuelve un dict de tipos primitivos, JSON-serializable tal cual.

¿Dónde vive el historial?
    En `session.state["messages"]`, gestionado por un `InMemoryHistoryProvider`.
    El framework lo inyecta solo si no declaras uno; aquí lo declaramos EXPLÍCITO
    para que el mecanismo quede a la vista (es justamente el tema de la demo).

Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.

Utilidad:
    - Persistir conversaciones entre ejecuciones del programa.
    - Base para guardar sesiones en Redis, Cosmos DB o cualquier almacén durable.
"""

import asyncio
import json
import os
from datetime import datetime

from dotenv import load_dotenv

from agent_framework import Agent, AgentSession, InMemoryHistoryProvider, Message
from agent_framework.openai import OpenAIChatClient

# override=True: el archivo .env03 MANDA sobre variables $env: viejas de la
# sesión de PowerShell (evita que valores obsoletos de la terminal lo pisen).
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "preview")

# Archivo donde se persiste la sesión entre ejecuciones
SESSION_FILE = "session_history.json"


def guardar_sesion(session: AgentSession, numero_mensaje: int) -> int:
    """Serializa la sesión y la escribe en disco. Devuelve el tamaño en bytes.

    `session.to_dict()` ya entrega tipos primitivos, así que json.dump funciona
    directo: no hay que convertir los Message uno por uno como en la API vieja.
    """
    datos = {
        'timestamp': datetime.now().isoformat(),
        'message_number': numero_mensaje,
        'session_data': session.to_dict(),   # <-- síncrono y JSON-serializable
    }
    contenido = json.dumps(datos, indent=2, ensure_ascii=False)
    with open(SESSION_FILE, 'w', encoding='utf-8') as f:
        f.write(contenido)
    return len(contenido)

#-----------------------------
# Funciones que se encargan de la serialización y deserialización de la sesión
# -----------------------------
def cargar_sesion() -> tuple[AgentSession | None, int]:
    """Lee el JSON del disco y reconstruye la sesión.

    Devuelve (sesión, nº de mensajes) o (None, 0) si no hay archivo o está roto.
    """
    if not os.path.exists(SESSION_FILE):
        return None, 0
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        # from_dict es un método estático y SÍNCRONO (antes: await agent.deserialize_thread)
        session = AgentSession.from_dict(datos['session_data'])
        return session, datos.get('message_number', 0)
    except Exception as e:
        print(f"   ⚠️  No se pudo cargar la sesión previa: {e}")
        return None, 0

# -----------------------------
# Función auxiliar para leer el historial de mensajes guardados en la sesión.
async def leer_historial(
    historial: InMemoryHistoryProvider, session: AgentSession
) -> list[Message]:
    """Devuelve los mensajes guardados en la sesión.

    OJO con el `state`: cada provider guarda lo suyo en un sub-diccionario de
    `session.state`, bajo su propio `source_id` (para el InMemoryHistoryProvider
    ese id es "in_memory"). Es decir, el historial real vive en:

        session.state["in_memory"]["messages"]

    Por eso a `get_messages` hay que pasarle esa porción del estado y no el
    `session.state` completo: si le pasas el dict entero, devuelve 0 mensajes.
    """
    return await historial.get_messages(
        session.session_id,
        state=session.state.get(historial.source_id),
    )

async def main():
    """Demo interactiva: serialización y restauración de la sesión en cada turno."""

    print("\n" + "=" * 70)
    print("🧵 DEMO AUTO-SERIALIZACIÓN: guardar y restaurar la sesión en cada mensaje")
    print("=" * 70)

    # Cliente Azure OpenAI nativo: 'model' es el nombre del deployment en Azure.
    chat_client = OpenAIChatClient(
        model=DEPLOYMENT,
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    # Declaramos el history provider EXPLÍCITAMENTE. Si no lo hiciéramos, el
    # framework inyectaría uno igual automáticamente al pasar `session=` a run(),
    # pero aquí queremos que se vea de dónde sale el historial (y necesitamos la
    # referencia para poder leerlo y mostrar cuántos mensajes hay guardados).
    historial = InMemoryHistoryProvider()

    agent = Agent(
        chat_client,
        instructions=(
            "Eres un asistente útil. Recuerda todo lo que el usuario te cuente "
            "y haz referencia a ello cuando venga al caso."
        ),
        name="MemoryBot",
        context_providers=[historial],
    )

    print("\n✅ Agente creado")

    # --- Reanudar la conversación anterior, si existe ---
    print("📋 Buscando una sesión previa...")
    session, contador = cargar_sesion()

    if session is not None:
        mensajes_previos = await leer_historial(historial, session)
        print(f"   📂 Encontrado {SESSION_FILE}")
        print(f"   ✅ Sesión restaurada: {len(mensajes_previos)} entradas en el historial")
        print(f"   🆔 session_id: {session.session_id}")
        print("   💡 Continuamos donde lo dejaste...\n")
    else:
        session = agent.create_session()   # antes: agent.get_new_thread()
        contador = 0
        print("   📋 No había sesión previa: se creó una nueva")
        print(f"   🆔 session_id: {session.session_id}\n")

    print("=" * 70)
    print("💬 Chat interactivo con auto-serialización")
    print("=" * 70)
    print("💡 Después de cada mensaje:")
    print("   1. El agente responde")
    print("   2. La sesión se serializa y se guarda en JSON")
    print("   3. La sesión se vuelve a leer y deserializar desde el archivo")
    print("   4. El siguiente mensaje usa la sesión restaurada")
    print("\n💡 Escribe 'quit' para salir")
    print("=" * 70 + "\n")

    while True:
        user_input = input("Tú: ").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 ¡Demo terminada!")
            print(f"\n📊 Mensajes en esta ejecución: {contador}")
            print(f"📊 Ciclos de serialización: {contador}")
            break

        if not user_input:
            continue

        contador += 1
        print(f"\n[Mensaje #{contador}]")

        # 1) El agente responde en streaming usando la sesión actual.
        #    `session=` reemplaza al viejo `thread=`.
        print("Agente: ", end="", flush=True)
        async for chunk in agent.run(user_input, stream=True, session=session):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print()

        # 2) Serializar y guardar en disco
        print(f"\n💾 [Serializando y guardando en {SESSION_FILE}...]")
        bytes_escritos = guardar_sesion(session, contador)
        guardados = await leer_historial(historial, session)
        print(f"   ✅ Guardado: {bytes_escritos} bytes, "
              f"{len(guardados)} mensajes en el historial")

        # 3) Volver a leer del disco y deserializar. Reasignamos `session` con el
        #    objeto restaurado: el siguiente turno usa lo que salió del archivo,
        #    que es justamente lo que la demo quiere probar.
        print(f"📥 [Leyendo y deserializando {SESSION_FILE}...]")
        session_restaurada, _ = cargar_sesion()
        if session_restaurada is not None:
            session = session_restaurada
            restaurados = await leer_historial(historial, session)
            print(f"   ✅ Sesión restaurada desde el archivo "
                  f"({len(restaurados)} mensajes)")
            print("   💡 El próximo mensaje usará esta sesión restaurada\n")
        else:
            print("   ⚠️  No se pudo restaurar; se sigue con la sesión en memoria\n")

        print("-" * 70 + "\n")

    print("\n" + "=" * 70)
    print("✅ DEMO COMPLETA")
    print("=" * 70)
    print("💡 Lo que acabas de ver:")
    print("   • La sesión se guardó en JSON después de cada mensaje")
    print("   • La sesión se restauró desde el JSON antes del siguiente turno")
    print("   • El agente mantuvo todo el historial de la conversación")
    print("   • Al volver a ejecutar el script, la conversación continúa")
    print(f"\n📁 Revisa el archivo: {SESSION_FILE}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
