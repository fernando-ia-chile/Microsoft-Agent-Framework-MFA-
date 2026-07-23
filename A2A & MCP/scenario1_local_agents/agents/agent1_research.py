"""
Agente de Investigación - Agente 1 del Escenario 1
==================================================
Este agente investiga y recopila información meteorológica usando el servidor MCP de clima.

Capacidades:
- Se conecta al servidor MCP de clima **hablando protocolo MCP de verdad** (stdio)
- Recibe peticiones del Agente Coordinador vía A2A
- Devuelve los resultados de la investigación vía A2A

Rol: Recopilador de Información

Migrado a Microsoft Agent Framework (core 1.12.0):
- `openai.AzureOpenAI` en crudo  ->  `OpenAIChatClient` + `Agent` (agent_framework)
- import directo de las funciones del servidor  ->  `MCPStdioTool` (protocolo MCP real)
- El LLM ahora SÍ se invoca y es él quien decide qué herramienta MCP llamar.

-------------------------------------------------------------------------------
ORDEN DE EJECUCIÓN (los comentarios [n] del código siguen esta numeración)
-------------------------------------------------------------------------------
  [0]-[3]  Arranque del módulo: UTF-8, .env, logging, ruta del servidor MCP
  [4]      __init__                  -> construye cliente + herramienta MCP + Agent
  [5]      handle_message            -> ENTRADA A2A: primera llamada del Coordinador
  [6]      process_research_request  -> valida la petición y arma la respuesta A2A
  [7]      _asegurar_conexion        -> connect() al servidor MCP (una sola vez)
  [8]      _consultar_clima_por_mcp  -> construye la consulta para el modelo
  [9]      agent.run(stream=True)    -> el LLM razona y llama a la tool MCP
  [10]     respuesta A2A al Coordinador
  [11]     send_to_coordinator
  [12]     cerrar()                  -> close() del MCP y fin del subproceso

Convención de los comentarios:
  ⚙️ MFA   = instrucción propia del Microsoft Agent Framework (materia de estudio)
  🔌 MCP   = relativo al Model Context Protocol
  🔧 Infra = Python/entorno, no es del framework
-------------------------------------------------------------------------------
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

# ⚙️ MFA: los tres pilares que usa esta demo.
#    - Agent         -> el agente en sí (modelo + instrucciones + herramientas)
#    - MCPStdioTool  -> herramienta que habla MCP con un servidor lanzado por stdio
#    - OpenAIChatClient -> cliente de chat nativo-Azure (sustituye a AzureOpenAIChatClient)
from agent_framework import Agent, MCPStdioTool
from agent_framework.openai import OpenAIChatClient
from dotenv import load_dotenv

# [0] 🔧 Infra: forzar UTF-8 en la salida. La consola de Windows usa cp1252 por
#     defecto y revienta con los emojis de la interfaz (UnicodeEncodeError).
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# [1] 🔧 Infra: cargar el .env del escenario con ruta absoluta, para no depender del
#     directorio de trabajo. override=True hace que el .env mande sobre variables
#     $env: viejas que hayan quedado en la sesión de PowerShell.
DIRECTORIO_ESCENARIO = Path(__file__).resolve().parent.parent
load_dotenv(DIRECTORIO_ESCENARIO / ".env", override=True)

# [2] 🔧 Infra: silenciar el ruido de transporte (peticiones HTTP y trazas del
#     cliente MCP), que taparía la interfaz didáctica. LOG_LEVEL controla el resto.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
for _ruidoso in ("httpx", "httpcore", "mcp", "openai", "agent_framework"):
    logging.getLogger(_ruidoso).setLevel(logging.WARNING)

# [3] 🔌 MCP: ruta al servidor de clima. MCPStdioTool lo lanzará como subproceso y
#     hablará JSON-RPC con él por stdin/stdout: aquí ya NO se importan sus funciones.
RUTA_SERVIDOR_CLIMA = DIRECTORIO_ESCENARIO / "mcp_servers" / "weather_server.py"


class ResearchAgent:
    """Agente especializado en investigación meteorológica mediante herramientas MCP."""

    # =========================================================================
    # [4] CONSTRUCCIÓN — se ejecuta una vez, al crear el agente
    # =========================================================================
    def __init__(self):
        """Inicializa el Agente de Investigación (todavía SIN conectar al servidor MCP)."""
        self.agent_id = "research-agent"
        self.name = "Agente de Investigación"
        self.role = "Recopilador de Información - Investigación Meteorológica"

        # [4.1] ⚙️ MFA: el ChatClient es el CANAL hacia el modelo; todavía no es un
        #       agente. Es nativo-Azure: basta con azure_endpoint + api_key.
        #       ⚠️ El endpoint debe ser SOLO la base (sin /openai/...): el framework
        #       le agrega /openai/v1/ por su cuenta. Si la incluyes, sale 404.
        self.client = OpenAIChatClient(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "preview"),
        )

        # [4.2] 🔌 MCP + ⚙️ MFA: MCPStdioTool es la herramienta que representa a TODO
        #       un servidor MCP (no a una función suelta). Al conectarse descubre por
        #       protocolo las tools que el servidor publica.
        #       - command=sys.executable -> el MISMO intérprete del venv, no "python"
        #         suelto del PATH (que podría no tener las dependencias instaladas).
        #       - load_prompts=False     -> este servidor solo expone tools, no prompts.
        self.herramienta_clima = MCPStdioTool(
            name="servidor_clima",
            command=sys.executable,
            args=[str(RUTA_SERVIDOR_CLIMA)],
            load_prompts=False,
        )

        # [4.3] ⚙️ MFA: las `instructions` son el system prompt del agente. Aquí se le
        #       prohíbe inventar datos y se le obliga a usar las tools MCP.
        #       ⚠️ Hay que pedir el español EXPLÍCITAMENTE o el modelo responde en inglés.
        self.system_instructions = """
        Eres un Agente de Investigación especializado en información meteorológica.

        Tus responsabilidades:
        1. Investigar el clima cuando el Agente Coordinador te lo solicite.
        2. Usar SIEMPRE las herramientas MCP disponibles para obtener datos reales.
           Nunca inventes temperaturas ni condiciones.
        3. Entregar resúmenes completos pero concisos.
        4. Citar la fuente de los datos (API de Open-Meteo).

        Herramientas MCP disponibles:
        - get_weather(city, country): clima actual de una ciudad.
        - get_forecast(city, country, days): pronóstico detallado.
        - get_alerts(city, country): avisos meteorológicos.

        RESPONDE SIEMPRE EN ESPAÑOL, sin excepción.
        """

        # [4.4] ⚙️ MFA: el Agent es la unión de cliente + instrucciones + herramientas.
        #       `tools=[...]` acepta funciones Python normales O herramientas MCP.
        #       Es el framework quien, en cada turno, le enseña al modelo el esquema
        #       de esas tools y ejecuta las que el modelo decida invocar.
        self.agent = Agent(
            self.client,
            self.system_instructions,
            name=self.agent_id,
            tools=[self.herramienta_clima],
        )

        # 🔧 Infra: bandera para conectar el MCP una sola vez (ver [7]).
        self._conectado = False

        print(f"✅ {self.name} inicializado (ID: {self.agent_id})")
        print(f"   Rol: {self.role}")

    # =========================================================================
    # [5] ENTRADA A2A — es la PRIMERA llamada que recibe el agente desde fuera
    # =========================================================================
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Manejador principal de los mensajes A2A entrantes. **Punto de entrada del agente.**

        Todo lo que otro agente quiera pedirle a este agente pasa por aquí: es el
        "buzón" que clasifica el mensaje por su campo `type` y lo deriva al método
        correspondiente. El Coordinador nunca llama a los métodos internos.

        Args:
            message: mensaje A2A entrante, con la forma
                - type:   tipo de petición ("research_request", "ping", ...)
                - sender: quién la envía
                - data:   carga útil de la petición

        Returns:
            Diccionario de respuesta A2A que se devuelve al emisor.
        """
        # [5.1] Leer la cabecera del mensaje A2A (tipo y emisor).
        message_type = message.get("type", "desconocido")
        sender = message.get("sender", "desconocido")

        print(f"\n📨 Mensaje recibido de {sender}")
        print(f"   Tipo: {message_type}")

        # [5.2] CLASIFICACIÓN por tipo de mensaje: es el "enrutador" del protocolo A2A.
        #       Cada rama es una capacidad que este agente publica hacia los demás.

        # [5.3] Rama 1 — petición de investigación: el trabajo real (continúa en [6]).
        if message_type == "research_request":
            return await self.process_research_request(message.get("data", {}))

        # [5.4] Rama 2 — ping: comprobación de salud. No gasta tokens ni toca el MCP;
        #       sirve para que el orquestador verifique que el agente está vivo.
        elif message_type == "ping":
            print(f"   ✅ {self.name}: activo")
            return {
                "agent_id": self.agent_id,
                "status": "active",
                "type": "pong",
            }

        # [5.5] Rama 3 — tipo desconocido: se responde con error en vez de reventar,
        #       para que el emisor pueda manejarlo (buena práctica en A2A).
        else:
            return {
                "agent_id": self.agent_id,
                "status": "error",
                "error": f"Tipo de mensaje desconocido: {message_type}",
            }

    # =========================================================================
    # [6] LÓGICA DE NEGOCIO — validar la petición y construir la respuesta A2A
    # =========================================================================
    async def process_research_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa una petición de investigación del Agente Coordinador.

        Args:
            request: diccionario con la petición
                - task: tipo de investigación (p. ej. "weather_lookup")
                - parameters: parámetros (ciudad, país)

        Returns:
            Diccionario con los resultados de la investigación.
        """
        # [6.1] Desempaquetar la carga útil que venía en `data` (ver [5.3]).
        task = request.get("task", "desconocida")
        parameters = request.get("parameters", {})

        print(f"\n📊 {self.name} recibió una petición de investigación:")
        print(f"   Tarea: {task}")
        print(f"   Parámetros: {parameters}")

        try:
            # [6.2] Delegar en el LLM + MCP (continúa en [8]).
            resultado = await self._consultar_clima_por_mcp(parameters)

            # [6.3] Envolver el resultado en el sobre de respuesta A2A. Esta forma
            #       es un CONTRATO: el Coordinador lee `status` y `results`.
            return {
                "agent_id": self.agent_id,
                "status": "success",
                "task": task,
                "results": resultado,
                "metadata": {
                    "source": "Servidor MCP de clima (protocolo MCP real)",
                    "confidence": "high",
                },
            }

        except Exception as e:
            # [6.4] Un fallo se devuelve como respuesta A2A de error, no como
            #       excepción: el Coordinador debe poder seguir con los demás pasos.
            print(f"❌ Error procesando la petición de investigación: {e}")
            return {
                "agent_id": self.agent_id,
                "status": "error",
                "task": task,
                "error": str(e),
            }

    # =========================================================================
    # [7] CICLO DE VIDA MCP — conexión perezosa (solo la primera vez)
    # =========================================================================
    async def _asegurar_conexion(self) -> None:
        """Conecta con el servidor MCP antes del primer uso, una sola vez."""
        if not self._conectado:
            print(f"   🔌 Conectando por MCP (stdio) con {RUTA_SERVIDOR_CLIMA.name}...")

            # [7.1] ⚙️ MFA + 🔌 MCP: connect() lanza el subproceso del servidor, hace
            #       el handshake `initialize` del protocolo y pide la lista de tools.
            await self.herramienta_clima.connect()
            self._conectado = True

            # [7.2] 🔌 MCP: `.functions` son las tools DESCUBIERTAS por protocolo.
            #       No están escritas a mano en ningún sitio: si mañana el servidor
            #       publica una tool nueva, aparece aquí sola. Eso es MCP.
            nombres = [f.name for f in self.herramienta_clima.functions]
            print(f"   ✅ MCP conectado. Herramientas descubiertas: {', '.join(nombres)}")

    # =========================================================================
    # [8] CONSULTA — se le pide al agente; el agente decide qué tool MCP usar
    # =========================================================================
    async def _consultar_clima_por_mcp(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pide el clima al agente, que a su vez llamará por MCP al servidor.

        Args:
            parameters: parámetros de la consulta (city, country)

        Returns:
            Datos del clima obtenidos de Open-Meteo a través del servidor MCP.
        """
        city = parameters.get("city", "Melbourne")
        country = parameters.get("country", "Australia")

        print(f"   🌐 Obteniendo datos EN VIVO para {city}, {country}...")

        try:
            # [8.1] Garantizar la sesión MCP antes de invocar al modelo (ver [7]).
            await self._asegurar_conexion()

            # [8.2] La consulta va en lenguaje natural. Fíjate en que NO se nombra
            #       la función a llamar: es el modelo quien elige entre get_weather,
            #       get_forecast y get_alerts. Antes de migrar, esto era un if/elif.
            consulta = (
                f"Consulta el clima actual de {city}, {country} "
                f"y resume las condiciones para un informe."
            )

            print(f"\n   🤖 Respuesta del agente:")
            print("   ", end="", flush=True)

            # [9] ⚙️ MFA: `agent.run(..., stream=True)` devuelve un flujo asíncrono de
            #     fragmentos. Por debajo, en este único await ocurre todo el ciclo:
            #       modelo -> decide llamar a get_weather -> el framework ejecuta la
            #       tool por MCP -> el servidor consulta Open-Meteo -> el resultado
            #       vuelve al modelo -> el modelo redacta la respuesta final.
            #     (La variante sin streaming sería `await self.agent.run(consulta)`.)
            texto_clima = ""
            async for chunk in self.agent.run(consulta, stream=True):
                if chunk.text:
                    texto_clima += chunk.text
                    print(chunk.text, end="", flush=True)
            print()

            # [10] Devolver la misma estructura que espera el Coordinador (contrato A2A).
            resultado = {
                "city": city,
                "country": country,
                "weather_data": texto_clima,
                "source": "API Open-Meteo (en vivo, vía MCP)",
                "timestamp": asyncio.get_event_loop().time(),
            }

            print(f"   ✅ Datos REALES recuperados para {city}, {country}")
            return resultado

        except Exception as e:
            print(f"   ⚠️ Error llamando al servidor MCP: {e}")
            return {
                "city": city,
                "country": country,
                "error": str(e),
                "note": "No se pudieron obtener datos en vivo - revisa el servidor MCP",
            }

    # =========================================================================
    # [11] SALIDA A2A — devolver el resultado al Coordinador
    # =========================================================================
    async def send_to_coordinator(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Devuelve los resultados al Agente Coordinador vía A2A.

        ⚠️ PENDIENTE DE MIGRAR: por ahora la entrega sigue siendo SIMULADA (devuelve
        un acuse fijo sin enviar nada). Se reemplazará por A2A real con
        `agent_framework.a2a` (A2AAgent) al migrar el Agente Coordinador.
        """
        print(f"\n📤 Enviando resultados al Agente Coordinador...")
        print(f"   Estado: {message.get('status', 'desconocido')}")

        return {
            "status": "entregado",
            "recipient": "coordinator-agent",
        }

    # =========================================================================
    # [12] CIERRE — liberar la sesión MCP y el subproceso
    # =========================================================================
    async def cerrar(self) -> None:
        """Cierra la sesión MCP y termina el subproceso del servidor."""
        if self._conectado:
            # ⚙️ MFA: sin close() el subproceso del servidor quedaría huérfano.
            await self.herramienta_clima.close()
            self._conectado = False

    async def __aenter__(self) -> "ResearchAgent":
        """Permite usar el agente como context manager (`async with ResearchAgent() as a:`),
        que conecta el MCP al entrar y lo cierra al salir, incluso si hay excepción."""
        await self._asegurar_conexion()
        return self

    async def __aexit__(self, *_) -> None:
        await self.cerrar()


async def main():
    """Función principal para ejecutar el Agente de Investigación de forma aislada."""
    print("\n" + "=" * 60)
    print("🤖 Agente de Investigación (Agente 1) - Iniciando...")
    print("=" * 60)

    # [A] El context manager abre la sesión MCP ([7]) y la cierra al terminar ([12]).
    async with ResearchAgent() as agente:

        print("\n--- Ejemplo de petición de investigación ---")

        # [B] Se simula el mensaje A2A que enviaría el Coordinador. Esta es
        #     exactamente la forma que espera handle_message ([5]).
        peticion = {
            "type": "research_request",
            "sender": "coordinator-agent",
            "data": {
                "task": "weather_lookup",
                "parameters": {
                    "city": "Santiago",
                    "country": "Chile",
                },
            },
        }

        # [C] Entrada por el buzón A2A ([5]).
        #     🐞 Antes de migrar faltaba el `await` y esto reventaba en json.dumps
        #        al recibir una corrutina en vez de un diccionario.
        respuesta = await agente.handle_message(peticion)

        print(f"\n✅ ¡Investigación completada!")
        print(f"   Estado: {respuesta['status']}")

        # [D] Devolución al Coordinador ([11]).
        await agente.send_to_coordinator(respuesta)

    print(f"\n✨ Demo del Agente de Investigación finalizada correctamente.")


if __name__ == "__main__":
    asyncio.run(main())
