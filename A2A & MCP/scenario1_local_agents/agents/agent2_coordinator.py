"""
Agente Coordinador - Agente 2 del Escenario 1
=============================================
Este agente orquesta el trabajo entre el Agente de Investigación y el Agente Ejecutor.

Capacidades:
- Recibe peticiones del usuario en lenguaje natural
- Delega la investigación al Agente de Investigación (vía A2A)
- Delega las operaciones de archivo al Agente Ejecutor (vía A2A)
- Agrega los resultados y responde al usuario

Rol: Orquestador de Flujos de Trabajo

Migrado a Microsoft Agent Framework (core 1.12.0):
- `openai.AzureOpenAI` en crudo  ->  `OpenAIChatClient` + `Agent` (agent_framework)
- Planificación por palabras clave (`_plan_workflow`)  ->  **la decide el LLM**
- Diccionario fijo de 6 ciudades (`_extract_weather_params`)  ->  **la extrae el LLM**
- `if/elif` que llamaba métodos Python  ->  **function tools** que delegan por A2A

-------------------------------------------------------------------------------
ORDEN DE EJECUCIÓN (los comentarios [n] del código siguen esta numeración)
-------------------------------------------------------------------------------
  [0]-[2]  Arranque del módulo: UTF-8, .env, logging
  [3]      __init__                   -> cliente + herramientas de delegación + Agent
  [4]      handle_message             -> ENTRADA A2A (desde otros agentes)
  [5]      process_user_request       -> ENTRADA DEL USUARIO (desde run_scenario1)
  [6]      agent.run(stream=True)     -> el LLM planifica y decide a quién delegar
  [7]      _delegar_por_a2a           -> envía el mensaje A2A y muestra su estructura
  [8]      tool: investigar_clima     -> delega en el Agente de Investigación
  [9]      tool: guardar_en_archivo   -> delega en el Agente Ejecutor
  [10]     _agregar_resultados        -> arma la respuesta final para el usuario

Convención de los comentarios:
  ⚙️ MFA   = instrucción propia del Microsoft Agent Framework (materia de estudio)
  📡 A2A   = relativo a la comunicación Agente-a-Agente
  🔧 Infra = Python/entorno, no es del framework
-------------------------------------------------------------------------------
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Any, Dict, List

# ⚙️ MFA: `tool` convierte una función Python normal en una herramienta que el
#    modelo puede invocar. Aquí las herramientas no calculan nada: **delegan en
#    otros agentes**, y por eso son el mecanismo de A2A de esta demo.
from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from dotenv import load_dotenv
from pydantic import Field

# [0] 🔧 Infra: forzar UTF-8 (la consola de Windows usa cp1252 y revienta con emojis).
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# [1] 🔧 Infra: cargar el .env del escenario con ruta absoluta (no depende del cwd).
DIRECTORIO_ESCENARIO = Path(__file__).resolve().parent.parent
load_dotenv(DIRECTORIO_ESCENARIO / ".env", override=True)

# [2] 🔧 Infra: silenciar el ruido de transporte para no tapar la interfaz didáctica.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
for _ruidoso in ("httpx", "httpcore", "mcp", "openai", "agent_framework"):
    logging.getLogger(_ruidoso).setLevel(logging.WARNING)

ANCHO_CAJA = 60


class CoordinatorAgent:
    """Agente responsable de orquestar flujos de trabajo entre otros agentes."""

    # =========================================================================
    # [3] CONSTRUCCIÓN — se ejecuta una vez, al crear el agente
    # =========================================================================
    def __init__(self, research_agent=None, executor_agent=None):
        """
        Inicializa el Agente Coordinador.

        Args:
            research_agent: instancia del Agente de Investigación (destino A2A)
            executor_agent: instancia del Agente Ejecutor (destino A2A)
        """
        self.agent_id = "coordinator-agent"
        self.name = "Agente Coordinador"
        self.role = "Orquestador de Flujos de Trabajo"

        # [3.1] 📡 A2A: referencias a los agentes destino. Son los "contactos" a los
        #       que este agente puede enviar mensajes A2A. Si faltan, las herramientas
        #       responden con error en vez de simular (ver [8] y [9]).
        self.research_agent = research_agent
        self.executor_agent = executor_agent

        # [3.2] 🔧 Infra: bitácora de los pasos que el LLM decida ejecutar. Se rellena
        #       dentro de las herramientas y se usa en [10] para el informe final.
        self._pasos: List[Dict[str, Any]] = []

        # [3.3] ⚙️ MFA: el ChatClient es el CANAL hacia el modelo; todavía no es agente.
        #       ⚠️ El endpoint debe ser SOLO la base (sin /openai/...).
        self.client = OpenAIChatClient(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "preview"),
        )

        # [3.4] ⚙️ MFA: las instrucciones son el system prompt. Aquí se le explica al
        #       modelo QUÉ agentes tiene disponibles y CÓMO encadenarlos. Antes esta
        #       lógica estaba escrita a mano en `_plan_workflow` con `if` de palabras.
        self.system_instructions = """
        Eres un Agente Coordinador que orquesta flujos de trabajo entre otros agentes.

        Tus responsabilidades:
        1. Analizar la petición del usuario y decidir qué agentes intervienen.
        2. Delegar cada subtarea al agente adecuado usando tus herramientas.
        3. Encadenar los resultados: lo que devuelve un agente puede ser la entrada
           del siguiente.
        4. Resumir al usuario lo que se hizo.

        Agentes disponibles (a través de tus herramientas):
        - Agente de Investigación -> herramienta `investigar_clima`.
          Úsala SIEMPRE que pidan clima, temperatura, pronóstico o alertas.
          Extrae tú la ciudad y el país de la petición del usuario, sea cual sea:
          funciona con CUALQUIER ciudad del mundo, no solo con las de Australia.
        - Agente Ejecutor -> herramienta `guardar_en_archivo`.
          Úsala solo si el usuario pide guardar, escribir, archivar o generar
          un informe o documento. Pásale el texto ya obtenido de la investigación.

        Reglas:
        - No inventes datos meteorológicos: siempre pásalos por `investigar_clima`.
        - Si el usuario pide clima Y guardar, llama primero a `investigar_clima`
          y después a `guardar_en_archivo` con el resultado.
        - Si la petición no requiere ningún agente, respóndela directamente.

        RESPONDE SIEMPRE EN ESPAÑOL, sin excepción.
        """

        # [3.5] ⚙️ MFA: el Agent une cliente + instrucciones + herramientas.
        #       `tools=[...]` recibe las dos funciones de delegación A2A ([8] y [9]).
        #       Es el framework quien enseña su esquema al modelo y ejecuta la que
        #       el modelo decida invocar, con los argumentos que el modelo extraiga.
        self.agent = Agent(
            self.client,
            self.system_instructions,
            name=self.agent_id,
            tools=[self._crear_tool_investigar(), self._crear_tool_guardar()],
        )

        print(f"✅ {self.name} inicializado (ID: {self.agent_id})")
        print(f"   Rol: {self.role}")

    # =========================================================================
    # [4] ENTRADA A2A — mensajes que llegan DESDE otros agentes
    # =========================================================================
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Manejador de los mensajes A2A entrantes. **Buzón del agente.**

        Ojo: este es el buzón para OTROS AGENTES. Las peticiones del usuario final
        entran por `process_user_request` ([5]).

        Args:
            message: mensaje A2A con `type`, `sender` y `data`.

        Returns:
            Diccionario de respuesta A2A.
        """
        # [4.1] Leer la cabecera del mensaje A2A.
        message_type = message.get("type", "desconocido")
        sender = message.get("sender", "desconocido")

        print(f"\n📨 Mensaje recibido de {sender}")
        print(f"   Tipo: {message_type}")

        # [4.2] CLASIFICACIÓN por tipo: es el enrutador del protocolo A2A.

        # [4.3] Rama 1 — ping: comprobación de salud, no gasta tokens.
        if message_type == "ping":
            print(f"   ✅ {self.name}: activo")
            return {
                "sender": self.agent_id,
                "recipient": sender,
                "type": "pong",
                "status": "active",
                "message": f"{self.name} está operativo",
            }

        # [4.4] Rama 2 — otro agente le delega un flujo completo: se trata igual
        #       que una petición de usuario y se resuelve con el LLM ([5]).
        elif message_type == "workflow_request":
            peticion = message.get("data", {}).get("request", "")
            print(f"   📋 Flujo de trabajo delegado por {sender}")
            resultado = await self.process_user_request(peticion)
            return {
                "sender": self.agent_id,
                "recipient": sender,
                "type": "workflow_response",
                "status": resultado["status"],
                "results": resultado,
            }

        # [4.5] Rama 3 — tipo desconocido: se responde con error en vez de reventar.
        else:
            return {
                "sender": self.agent_id,
                "recipient": sender,
                "type": "error",
                "error": f"Tipo de mensaje desconocido: {message_type}",
            }

    # =========================================================================
    # [5] ENTRADA DEL USUARIO — la llama run_scenario1.py
    # =========================================================================
    async def process_user_request(self, user_request: str) -> Dict[str, Any]:
        """
        Procesa una petición del usuario y orquesta el flujo entre agentes.

        Args:
            user_request: petición en lenguaje natural.

        Returns:
            Diccionario con el resultado agregado (contrato que consume run_scenario1).
        """
        print(f"\n👤 Petición del usuario: {user_request}")
        print(f"🤔 Analizando la petición y planificando el flujo de trabajo...")

        # [5.1] Vaciar la bitácora: cada petición es un flujo independiente.
        self._pasos = []

        try:
            print(f"\n   🤖 Respuesta del Coordinador:")
            print("   ", end="", flush=True)

            # [6] ⚙️ MFA: aquí ocurre TODA la orquestación en un único await.
            #     El modelo lee la petición, decide qué herramientas llamar y en
            #     qué orden, extrae los argumentos (ciudad, país, nombre de archivo)
            #     y encadena los resultados. El framework ejecuta cada herramienta
            #     y le devuelve la salida al modelo hasta que este redacta el cierre.
            #     ➜ Esto sustituye por completo a `_plan_workflow` + `_execute_workflow`.
            resumen = ""
            async for chunk in self.agent.run(user_request, stream=True):
                if chunk.text:
                    resumen += chunk.text
                    print(chunk.text, end="", flush=True)
            print()

        except Exception as e:
            print(f"\n❌ Error orquestando el flujo: {e}")
            resumen = f"El flujo falló: {e}"

        # [10] Agregar lo ocurrido en un informe con el formato que espera el escenario.
        return self._agregar_resultados(resumen)

    # =========================================================================
    # [7] CANAL A2A — envío del mensaje y visualización de su estructura
    # =========================================================================
    async def _delegar_por_a2a(
        self, agente_destino: Any, agent_id: str, tipo: str, datos: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Envía un mensaje A2A a otro agente y devuelve su respuesta.

        Este método concentra el "protocolo": construir el sobre, mostrarlo y
        entregarlo al buzón (`handle_message`) del agente destino.
        """
        # [7.1] 📡 A2A: construir el SOBRE del mensaje. Estos cuatro campos son el
        #       contrato que comparten los tres agentes del escenario.
        mensaje = {
            "sender": self.agent_id,
            "recipient": agent_id,
            "type": tipo,
            "data": datos,
            "timestamp": asyncio.get_event_loop().time(),
        }

        # [7.2] Mostrar la estructura del mensaje: es el objetivo didáctico del bloque.
        print(f"\n   📤 Enviando mensaje A2A a {agent_id}...")
        print(f"\n   📨 ESTRUCTURA DEL MENSAJE A2A:")
        print(f"   ┌{'─' * ANCHO_CAJA}┐")
        print(f"   │ Emisor:     {mensaje['sender']:<{ANCHO_CAJA - 13}}│")
        print(f"   │ Destino:    {mensaje['recipient']:<{ANCHO_CAJA - 13}}│")
        print(f"   │ Tipo:       {mensaje['type']:<{ANCHO_CAJA - 13}}│")
        print(f"   │ Datos:      {str(mensaje['data'])[:ANCHO_CAJA - 15]:<{ANCHO_CAJA - 13}}│")
        print(f"   └{'─' * ANCHO_CAJA}┘")

        # [7.3] 📡 A2A: entregar el mensaje en el buzón del agente destino.
        #       Los tres agentes del escenario exponen el mismo `handle_message`
        #       asíncrono: ese contrato común es lo que hace intercambiables a los
        #       destinos y permite que este método no sepa nada de quién recibe.
        respuesta = await agente_destino.handle_message(mensaje)

        # [7.4] Mostrar el acuse de recibo.
        print(f"\n   📨 RESPUESTA A2A RECIBIDA:")
        print(f"   ┌{'─' * ANCHO_CAJA}┐")
        print(f"   │ De:         {str(respuesta.get('agent_id', agent_id)):<{ANCHO_CAJA - 13}}│")
        print(f"   │ Estado:     {str(respuesta.get('status', 'desconocido')):<{ANCHO_CAJA - 13}}│")
        print(f"   └{'─' * ANCHO_CAJA}┘")

        return respuesta

    # =========================================================================
    # [8] HERRAMIENTA 1 — delegar en el Agente de Investigación
    # =========================================================================
    def _crear_tool_investigar(self):
        """Crea la herramienta que el modelo usará para delegar la investigación."""

        # ⚙️ MFA: `@tool` publica esta función al modelo. La descripción y los
        #    `Annotated[..., Field(description=...)]` son lo que el modelo LEE para
        #    decidir cuándo llamarla y con qué argumentos: por eso son tan explícitos.
        @tool(
            name="investigar_clima",
            description=(
                "Delega en el Agente de Investigación la consulta del clima de "
                "cualquier ciudad del mundo. Devuelve el informe meteorológico."
            ),
        )
        async def investigar_clima(
            ciudad: Annotated[str, Field(description="Nombre de la ciudad, p. ej. 'Tokio'")],
            pais: Annotated[str, Field(description="País de la ciudad, p. ej. 'Japón'")] = "",
        ) -> str:
            # [8.1] Sin contacto no hay delegación posible: se informa del error en
            #       vez de simular una respuesta (el código antiguo sí la simulaba).
            if not self.research_agent:
                return "ERROR: el Agente de Investigación no está conectado."

            # [8.2] 📡 A2A: delegar con el tipo de mensaje que ese agente entiende.
            respuesta = await self._delegar_por_a2a(
                self.research_agent,
                "research-agent",
                "research_request",
                {"task": "weather_lookup", "parameters": {"city": ciudad, "country": pais}},
            )

            # [8.3] Registrar el paso para el informe final ([10]).
            self._pasos.append(respuesta)

            # [8.4] Devolver al modelo SOLO el texto útil: es lo que él encadenará
            #       hacia la siguiente herramienta.
            if respuesta.get("status") == "success":
                return respuesta.get("results", {}).get("weather_data", "")
            return f"ERROR: {respuesta.get('error', 'fallo desconocido')}"

        return investigar_clima

    # =========================================================================
    # [9] HERRAMIENTA 2 — delegar en el Agente Ejecutor
    # =========================================================================
    def _crear_tool_guardar(self):
        """Crea la herramienta que el modelo usará para delegar el guardado."""

        @tool(
            name="guardar_en_archivo",
            description=(
                "Delega en el Agente Ejecutor el guardado de un texto en un archivo "
                "del espacio de trabajo. Úsala cuando el usuario pida guardar o "
                "generar un informe."
            ),
        )
        async def guardar_en_archivo(
            contenido: Annotated[str, Field(description="Texto completo a guardar")],
            nombre_archivo: Annotated[
                str, Field(description="Nombre del archivo, p. ej. 'informe_clima.txt'")
            ] = "informe_clima.txt",
        ) -> str:
            if not self.executor_agent:
                return "ERROR: el Agente Ejecutor no está conectado."

            # [9.1] 📡 A2A: el Ejecutor espera `operation`, `parameters` y `content`.
            respuesta = await self._delegar_por_a2a(
                self.executor_agent,
                "executor-agent",
                "execution_request",
                {
                    "operation": "write_file",
                    "parameters": {"filename": nombre_archivo},
                    "content": contenido,
                },
            )

            self._pasos.append(respuesta)

            if respuesta.get("status") == "success":
                return respuesta.get("results", {}).get(
                    "message", f"Guardado en {nombre_archivo}"
                )
            return f"ERROR: {respuesta.get('error', 'fallo desconocido')}"

        return guardar_en_archivo

    # =========================================================================
    # [10] AGREGACIÓN — construir el informe final para el usuario
    # =========================================================================
    def _agregar_resultados(self, resumen_modelo: str) -> Dict[str, Any]:
        """
        Agrega los pasos ejecutados en la respuesta final.

        El formato de salida es un CONTRATO que consume run_scenario1.py:
        lee `status`, `total_steps`, `successful_steps`, `results` y `summary`.
        """
        total = len(self._pasos)
        exitosos = sum(1 for p in self._pasos if p.get("status") == "success")

        print(f"\n📊 Agregando resultados de {total} paso(s) delegado(s)...")

        return {
            "coordinator_id": self.agent_id,
            # Sin pasos delegados el flujo igual se considera completado: el modelo
            # pudo haber respondido directamente (p. ej. un saludo).
            "status": "completed" if exitosos == total else "partial_success",
            "total_steps": total,
            "successful_steps": exitosos,
            "results": self._pasos,
            "summary": resumen_modelo.strip() or "Flujo completado.",
        }


async def main():
    """Ejecuta el Agente Coordinador de forma aislada, con sus agentes reales."""
    print("\n" + "=" * 60)
    print("🤖 Agente Coordinador (Agente 2) - Iniciando...")
    print("=" * 60)

    # [A] 🔧 Infra: importar los agentes destino desde este mismo directorio.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from agent1_research import ResearchAgent
    from agent3_executor import ExecutorAgent

    # [B] Crear los agentes destino y conectarlos al Coordinador. Antes, el `main()`
    #     construía el Coordinador SIN referencias y todo salía simulado.
    #     Cada uno abre su propia sesión MCP al entrar y la cierra al salir.
    async with ResearchAgent() as investigador, ExecutorAgent() as ejecutor:
        coordinador = CoordinatorAgent(
            research_agent=investigador,
            executor_agent=ejecutor,
        )

        # [C] Petición con DOS subtareas encadenadas y una ciudad que NO es australiana:
        #     antes el extractor fijo la habría convertido en Melbourne sin avisar.
        peticion = "¿Qué clima hace en Tokio, Japón? Guárdalo en informe_tokio.txt"

        respuesta = await coordinador.process_user_request(peticion)

        print(f"\n✅ ¡Flujo completado!")
        print(f"   Estado: {respuesta['status']}")
        print(f"   Pasos: {respuesta['successful_steps']}/{respuesta['total_steps']}")

    print(f"\n✨ Demo del Agente Coordinador finalizada correctamente.")


if __name__ == "__main__":
    asyncio.run(main())
