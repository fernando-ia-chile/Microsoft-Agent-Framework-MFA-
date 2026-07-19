"""
NUEVO 12: Memoria de largo plazo con extracción por IA (Demo interactiva)

Objetivo pedagógico (sin cambios respecto del original):
    Mostrar que un agente puede tener DOS capas de memoria:
      * Corto plazo -> el historial de la sesión (se pierde al abrir una nueva).
      * Largo plazo -> un PERFIL del usuario que persiste en disco y sobrevive
        a sesiones nuevas e incluso a reinicios del programa.
    Y que ese perfil no se llena con reglas hardcodeadas: es la propia IA la que
    decide qué vale la pena recordar de cada mensaje.

    Prueba clave: escribe 'new' para abrir una sesión limpia. El agente olvida
    la conversación pero SIGUE sabiendo quién eres.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---
El `ContextProvider` cambió por completo: ya no se devuelve un objeto `Context`,
ahora se MUTA el `SessionContext` que llega por parámetro.

  * AzureOpenAIChatClient(...)         -> OpenAIChatClient(azure_endpoint=, model=, ...)
  * client.create_agent(...)           -> Agent(client, instructions=, name=)
  * agent.get_new_thread()             -> agent.create_session()
  * agent.run_stream(x, thread=t)      -> agent.run(x, stream=True, session=s)
  * ContextProvider.invoking(messages) -> before_run(*, agent, session, context, state)
  * ContextProvider.invoked(req, resp)  -> after_run(*, agent, session, context, state)
  * return Context(instructions=...)   -> context.extend_instructions(source_id, ...)
  * ContextProvider()                  -> super().__init__(source_id="...")  (obligatorio)

Dos mejoras que trae la migración:
  1. Se eliminó el cliente `AsyncAzureOpenAI` crudo del SDK de OpenAI. La
     extracción del perfil ahora usa `OpenAIChatClient.get_response(...)` del
     propio framework: todo queda dentro de MFA.
  2. Se eliminó el parseo frágil de JSON a mano (buscar '{' y '}' en el texto).
     Ahora se usa SALIDA ESTRUCTURADA con un modelo Pydantic
     (`options={"response_format": PerfilExtraido}`) y se lee `response.value`,
     que ya viene validado.

Nota sobre la documentación:
    La referencia de API en learn.microsoft.com/python/api/agent-framework-core
    todavía documenta `invoking()`/`Context` (API vieja). La documentación
    conceptual (agent-framework/agents/conversations/context-providers) y el
    paquete instalado son los que mandan.

Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT (¡solo la base!), AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.

Utilidad:
    - Personalización que sobrevive entre conversaciones.
    - Base para perfiles de usuario en asistentes reales.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from agent_framework import (
    Agent,
    AgentSession,
    ContextProvider,
    InMemoryHistoryProvider,
    Message,
    SessionContext,
    SupportsAgentRun,
)
from agent_framework.openai import OpenAIChatClient

# override=True: el .env03 manda sobre variables $env: viejas de la terminal.
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "preview")

# Archivo donde vive la memoria de largo plazo
MEMORY_FILE = "ai_memory_profile.json"


# ============================================================================
# MODELO DE SALIDA ESTRUCTURADA
# ============================================================================
# En vez de pedirle al modelo "devuelve JSON" y luego rebuscar las llaves en el
# texto, declaramos la forma exacta que queremos. El framework se encarga de
# validarla y nos entrega objetos Pydantic ya listos en `response.value`.

class DatoPerfil(BaseModel):
    """Un dato suelto del usuario, del estilo clave = valor."""
    clave: str = Field(description="Atributo en snake_case: nombre, profesion, color_favorito...")
    valor: str = Field(description="El valor del atributo, breve")


class PerfilExtraido(BaseModel):
    """Lo que la IA logró extraer de UN mensaje. Puede venir vacío."""
    datos: list[DatoPerfil] = Field(
        default_factory=list,
        description="Datos personales duraderos. Vacío si el mensaje no aporta nada.",
    )


# ============================================================================
# CONTEXT PROVIDER: memoria de largo plazo impulsada por IA
# ============================================================================

class MemoriaConIA(ContextProvider):
    """Inyecta el perfil del usuario antes de cada run y lo actualiza después.

    Ciclo de vida en la API 1.11.0:
      * before_run(...) -> se ejecuta ANTES de llamar al modelo. Aquí inyectamos
        el perfil como instrucciones extra, mutando el SessionContext.
      * after_run(...)  -> se ejecuta DESPUÉS. Aquí le pedimos a la IA que
        analice lo que dijo el usuario y guardamos lo que valga la pena.

    Ojo: en la API vieja `invoking()` DEVOLVÍA un objeto `Context`. Ahora no se
    devuelve nada: se modifica el `context` que llega por parámetro.
    """

    def __init__(self, cliente_extractor: OpenAIChatClient, memory_file: str = MEMORY_FILE):
        # source_id es OBLIGATORIO en 1.11.0: identifica a este provider para que
        # el framework sepa qué instrucciones/mensajes vienen de él.
        super().__init__(source_id="memoria_largo_plazo")
        self.cliente_extractor = cliente_extractor
        self.memory_file = memory_file
        self.perfil: dict[str, str] = {}
        self._cargar_perfil()

    # ---------------------------------------------------------------- disco --

    def _cargar_perfil(self) -> None:
        """Lee el perfil del archivo JSON al arrancar."""
        if not os.path.exists(self.memory_file):
            print(f"\n📋 [MEMORIA NUEVA] No existe {self.memory_file} todavía")
            return
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                self.perfil = json.load(f).get('perfil', {})
            print(f"\n📂 [MEMORIA CARGADA] desde {self.memory_file}")
            if self.perfil:
                print(f"   🧠 Perfil restaurado: {self._resumen()}")
            else:
                print("   📋 El archivo existe pero el perfil está vacío")
        except Exception as e:
            print(f"\n⚠️  [ERROR AL CARGAR] {self.memory_file}: {e}")
            self.perfil = {}

    def _guardar_perfil(self) -> None:
        """Escribe el perfil en el archivo JSON."""
        try:
            datos = {'timestamp': datetime.now().isoformat(), 'perfil': self.perfil}
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=2, ensure_ascii=False)
            print(f"   💾 [GUARDADO EN DISCO] {self.memory_file}")
        except Exception as e:
            print(f"   ⚠️  [ERROR AL GUARDAR] {self.memory_file}: {e}")

    def _resumen(self) -> str:
        return ", ".join(f"{k}={v}" for k, v in self.perfil.items())

    # ------------------------------------------------- ganchos del framework --

    async def before_run(
        self,
        *,
        agent: SupportsAgentRun,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """ANTES del modelo: inyecta el perfil como instrucciones adicionales."""
        if not self.perfil:
            return

        print("\n   💭 [INYECTANDO MEMORIA DE LARGO PLAZO]")
        print(f"   📋 Perfil: {self._resumen()}\n")

        lineas = "\n".join(f"- {k}: {v}" for k, v in self.perfil.items())
        # extend_instructions reemplaza al viejo `return Context(instructions=...)`.
        # El primer argumento es el source_id, para que el framework sepa quién
        # aportó estas instrucciones.
        context.extend_instructions(
            self.source_id,
            f"""[PERFIL DEL USUARIO - MEMORIA DE LARGO PLAZO]:
{lineas}

IMPORTANTE: esta información sobre el usuario persiste entre conversaciones.
Menciónala con naturalidad cuando venga al caso y saluda con entusiasmo si lo reconoces.""",
        )

    async def after_run(
        self,
        *,
        agent: SupportsAgentRun,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """DESPUÉS del modelo: la IA decide qué merece recordarse."""
        # context.input_messages trae los mensajes que envió el usuario en este run.
        mensaje_usuario = ""
        for msg in reversed(context.input_messages):
            if msg.role == "user" and msg.text:
                mensaje_usuario = msg.text
                break

        if len(mensaje_usuario.strip()) < 3:
            return

        print(f"\n   🤖 [IA ANALIZANDO]: '{mensaje_usuario}'")

        prompt = f"""Extrae datos personales duraderos del mensaje del usuario.

Mensaje: "{mensaje_usuario}"
Perfil actual: {self.perfil or "vacío"}

Reglas:
- Solo datos factuales del usuario: nombre, edad, profesión, gustos, aficiones...
- Solo lo NUEVO o lo que haya CAMBIADO respecto del perfil actual.
- Si el mensaje no aporta nada personal (ej. "¿cómo estás?"), devuelve la lista vacía.
- Valores breves, claves en snake_case."""

        try:
            # Llamada de un solo turno con salida estructurada, usando el cliente
            # del propio framework (antes: AsyncAzureOpenAI crudo + json.loads).
            respuesta = await self.cliente_extractor.get_response(
                [Message("user", [prompt])],
                options={"response_format": PerfilExtraido},
            )
            extraido: PerfilExtraido = respuesta.value

            if not extraido.datos:
                return

            for dato in extraido.datos:
                self.perfil[dato.clave] = dato.valor
                print(f"   💾 [IA APRENDIÓ] {dato.clave} = {dato.valor}")
            self._guardar_perfil()

        except Exception as e:
            print(f"   ⚠️  [ERROR DE EXTRACCIÓN] {e}")


# ============================================================================
# DEMO INTERACTIVA
# ============================================================================

async def main():
    print("\n" + "=" * 70)
    print("🤖 MEMORIA DE LARGO PLAZO CON IA + PERSISTENCIA EN ARCHIVO")
    print("=" * 70)
    print("\nConcepto: la IA decide sola qué información vale la pena guardar.")
    print(f"Archivo de memoria: {MEMORY_FILE}")
    print("=" * 70)

    # Un único cliente sirve para las dos cosas: conversar y extraer el perfil.
    chat_client = OpenAIChatClient(
        model=DEPLOYMENT,
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    print("\n🔧 Creando agente con memoria impulsada por IA...")
    memoria = MemoriaConIA(chat_client)
    print("   ✅ Analizador de memoria inicializado")

    # Dos capas de memoria, explícitas:
    #   - InMemoryHistoryProvider -> corto plazo (historial de ESTA sesión)
    #   - MemoriaConIA            -> largo plazo (perfil en disco, entre sesiones)
    agent = Agent(
        chat_client,
        instructions=(
            "Eres un asistente amable y cercano con memoria de largo plazo.\n"
            "Cuando reconozcas datos del perfil del usuario, menciónalos con "
            "naturalidad, salúdalo con entusiasmo y personaliza tus respuestas.\n"
            "Sé conversacional y cálido."
        ),
        name="MemoryBot",
        context_providers=[InMemoryHistoryProvider(), memoria],
    )
    print("✅ Agente creado con memoria de largo plazo\n")

    print("=" * 70)
    print("💡 COMANDOS:")
    print("=" * 70)
    print("  • Conversa normalmente — la IA extrae y guarda datos en el archivo")
    print("  • 'new'     - Abre una sesión nueva (prueba la memoria entre sesiones)")
    print("  • 'profile' - Muestra lo que la IA aprendió de ti")
    print("  • 'quit'    - Salir")
    print("=" * 70)

    numero_sesion = 0
    session: AgentSession | None = None

    while True:
        # Crear sesión nueva cuando haga falta (al arrancar o tras 'new')
        if session is None:
            numero_sesion += 1
            session = agent.create_session()   # antes: agent.get_new_thread()
            print(f"\n🆕 SESIÓN #{numero_sesion} creada\n")

        user_input = input("Tú: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 ¡Demo terminada!")
            if memoria.perfil:
                print("\n📊 Perfil final aprendido por la IA:")
                for clave, valor in memoria.perfil.items():
                    print(f"   • {clave}: {valor}")
            else:
                print("   (No se aprendió ningún dato)")
            break

        if user_input.lower() == 'new':
            # Solo se descarta la sesión: el perfil de largo plazo sobrevive.
            session = None
            print("\n🔄 Sesión descartada. El perfil de largo plazo se mantiene.")
            continue

        if user_input.lower() == 'profile':
            print("\n📋 PERFIL APRENDIDO POR LA IA:")
            if memoria.perfil:
                for clave, valor in memoria.perfil.items():
                    print(f"   • {clave}: {valor}")
            else:
                print("   (La IA todavía no ha aprendido nada de ti)")
            print()
            continue

        # El provider se dispara solo: inyecta el perfil antes y aprende después.
        print(f"Agente (Sesión #{numero_sesion}): ", end="", flush=True)
        async for chunk in agent.run(user_input, stream=True, session=session):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
