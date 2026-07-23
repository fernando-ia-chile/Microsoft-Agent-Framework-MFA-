"""
Agente Ejecutor - Agente 3 del Escenario 1
==========================================
Este agente ejecuta operaciones de archivo usando el servidor MCP de archivos.

Capacidades:
- Se conecta al servidor MCP de archivos **hablando protocolo MCP de verdad** (stdio)
- Recibe peticiones de ejecución del Agente Coordinador vía A2A
- Realiza operaciones de archivo (leer, escribir, listar, borrar, informar)
- Devuelve los resultados de la ejecución vía A2A

Rol: Ejecutor de Tareas

Migrado a Microsoft Agent Framework (core 1.12.0):
- `openai.AzureOpenAI` en crudo  ->  `OpenAIChatClient` + `Agent` (agent_framework)
- import directo de las funciones del servidor  ->  `MCPStdioTool` (protocolo MCP real)
- `if/elif` de 5 ramas por operación  ->  **el LLM elige la herramienta MCP**
- `handle_message` síncrono  ->  asíncrono, como el resto de los agentes

-------------------------------------------------------------------------------
ORDEN DE EJECUCIÓN (los comentarios [n] del código siguen esta numeración)
-------------------------------------------------------------------------------
  [0]-[3]  Arranque del módulo: UTF-8, .env, logging, ruta del servidor MCP
  [4]      __init__                    -> cliente + herramienta MCP + Agent
  [5]      handle_message              -> ENTRADA A2A: llamada del Coordinador
  [6]      process_execution_request   -> valida la petición y arma la respuesta A2A
  [7]      _asegurar_conexion          -> connect() al servidor MCP (una sola vez)
  [8]      _ejecutar_operacion         -> traduce la operación a instrucción para el LLM
  [9]      agent.run(stream=True)      -> el LLM razona y llama a la tool MCP
  [10]     respuesta A2A al Coordinador
  [11]     send_to_coordinator
  [12]     cerrar()                    -> close() del MCP y fin del subproceso

Convención de los comentarios:
  ⚙️ MFA   = instrucción propia del Microsoft Agent Framework (materia de estudio)
  🔌 MCP   = relativo al Model Context Protocol
  📡 A2A   = relativo a la comunicación Agente-a-Agente
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
#    - Agent            -> el agente (modelo + instrucciones + herramientas)
#    - MCPStdioTool     -> herramienta que habla MCP con un servidor lanzado por stdio
#    - OpenAIChatClient -> cliente de chat nativo-Azure
from agent_framework import Agent, MCPStdioTool
from agent_framework.openai import OpenAIChatClient
from dotenv import load_dotenv

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

# [3] 🔌 MCP: ruta al servidor de archivos. MCPStdioTool lo lanzará como subproceso
#     y hablará JSON-RPC con él: aquí ya NO se importan sus funciones.
RUTA_SERVIDOR_ARCHIVOS = DIRECTORIO_ESCENARIO / "mcp_servers" / "file_operations_server.py"


class ExecutorAgent:
    """Agente especializado en ejecutar operaciones de archivo mediante herramientas MCP."""

    # =========================================================================
    # [4] CONSTRUCCIÓN — se ejecuta una vez, al crear el agente
    # =========================================================================
    def __init__(self):
        """Inicializa el Agente Ejecutor (todavía SIN conectar al servidor MCP)."""
        self.agent_id = "executor-agent"
        self.name = "Agente Ejecutor"
        self.role = "Ejecutor de Tareas - Operaciones de Archivo"

        # [4.1] ⚙️ MFA: el ChatClient es el CANAL hacia el modelo; todavía no es agente.
        #       ⚠️ El endpoint debe ser SOLO la base (sin /openai/...): el framework
        #       le agrega /openai/v1/ por su cuenta. Si la incluyes, sale 404.
        self.client = OpenAIChatClient(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "preview"),
        )

        # [4.2] 🔌 MCP + ⚙️ MFA: MCPStdioTool representa a TODO el servidor de archivos,
        #       no a una función suelta. Al conectarse descubre por protocolo las cinco
        #       tools que publica (read_file, write_file, list_files, delete_file,
        #       file_info).
        #       - command=sys.executable -> el MISMO intérprete del venv.
        #       - load_prompts=False     -> este servidor solo expone tools.
        self.herramienta_archivos = MCPStdioTool(
            name="servidor_archivos",
            command=sys.executable,
            args=[str(RUTA_SERVIDOR_ARCHIVOS)],
            load_prompts=False,
        )

        # [4.3] ⚙️ MFA: las `instructions` son el system prompt del agente.
        #       ⚠️ Hay que pedir el español EXPLÍCITAMENTE o el modelo responde en inglés.
        self.system_instructions = """
        Eres un Agente Ejecutor especializado en operaciones de archivo.

        Tus responsabilidades:
        1. Ejecutar las tareas que te delegue el Agente Coordinador.
        2. Usar SIEMPRE las herramientas MCP para tocar archivos.
           Nunca simules ni inventes el resultado de una operación.
        3. Confirmar de forma breve y precisa qué se hizo.
        4. Si una operación falla, decir exactamente por qué.

        Herramientas MCP disponibles:
        - write_file(filename, content, append): escribe contenido en un archivo.
        - read_file(filename): lee el contenido de un archivo.
        - list_files(directory, pattern): lista archivos.
        - delete_file(filename): borra un archivo.
        - file_info(filename): datos de un archivo.

        Todas las rutas son relativas al espacio de trabajo del agente.
        Sé preciso y fiable: verifica que la operación se completó.

        RESPONDE SIEMPRE EN ESPAÑOL, sin excepción.
        """

        # [4.4] ⚙️ MFA: el Agent une cliente + instrucciones + herramientas MCP.
        #       Es el framework quien enseña el esquema de las tools al modelo y
        #       ejecuta la que el modelo decida invocar.
        self.agent = Agent(
            self.client,
            self.system_instructions,
            name=self.agent_id,
            tools=[self.herramienta_archivos],
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

        Es el "buzón" que clasifica el mensaje por su campo `type` y lo deriva al
        método correspondiente. El Coordinador nunca llama a los métodos internos.

        ⚠️ Este método ERA SÍNCRONO antes de la migración. Ahora es asíncrono, como
           el de los demás agentes, porque las llamadas al modelo y a MCP lo son.

        Args:
            message: mensaje A2A con `type`, `sender` y `data`.

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

        # [5.3] Rama 1 — petición de ejecución: el trabajo real (continúa en [6]).
        if message_type == "execution_request":
            return await self.process_execution_request(message.get("data", {}))

        # [5.4] Rama 2 — ping: comprobación de salud. No gasta tokens ni toca el MCP.
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
    async def process_execution_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa una petición de ejecución del Agente Coordinador.

        Args:
            request: diccionario con la petición
                - operation: operación a realizar (p. ej. "write_file")
                - parameters: parámetros de la operación (filename, directory...)
                - content: contenido a escribir, si aplica

        Returns:
            Diccionario con los resultados de la ejecución.
        """
        # [6.1] Desempaquetar la carga útil que venía en `data` (ver [5.3]).
        operation = request.get("operation", "desconocida")
        parameters = request.get("parameters", {})
        content = request.get("content", "")

        print(f"\n⚙️  {self.name} recibió una petición de ejecución:")
        print(f"   Operación: {operation}")
        print(f"   Parámetros: {parameters}")

        try:
            # [6.2] Delegar en el LLM + MCP (continúa en [8]).
            resultado = await self._ejecutar_operacion(operation, parameters, content)

            # [6.3] Envolver el resultado en el sobre de respuesta A2A. Esta forma
            #       es un CONTRATO: el Coordinador lee `status` y `results.message`.
            return {
                "agent_id": self.agent_id,
                "status": "success",
                "operation": operation,
                "results": resultado,
                "metadata": {
                    "tool": "Servidor MCP de archivos (protocolo MCP real)",
                },
            }

        except Exception as e:
            # [6.4] Un fallo se devuelve como respuesta A2A de error, no como
            #       excepción: el Coordinador debe poder seguir con los demás pasos.
            print(f"❌ Error ejecutando la operación: {e}")
            return {
                "agent_id": self.agent_id,
                "status": "error",
                "operation": operation,
                "error": str(e),
            }

    # =========================================================================
    # [7] CICLO DE VIDA MCP — conexión perezosa (solo la primera vez)
    # =========================================================================
    async def _asegurar_conexion(self) -> None:
        """Conecta con el servidor MCP antes del primer uso, una sola vez."""
        if not self._conectado:
            print(f"   🔌 Conectando por MCP (stdio) con {RUTA_SERVIDOR_ARCHIVOS.name}...")

            # [7.1] ⚙️ MFA + 🔌 MCP: connect() lanza el subproceso del servidor, hace
            #       el handshake `initialize` del protocolo y pide la lista de tools.
            await self.herramienta_archivos.connect()
            self._conectado = True

            # [7.2] 🔌 MCP: `.functions` son las tools DESCUBIERTAS por protocolo.
            #       No están escritas a mano: si el servidor publica una tool nueva,
            #       aparece aquí sola. Eso es MCP.
            nombres = [f.name for f in self.herramienta_archivos.functions]
            print(f"   ✅ MCP conectado. Herramientas descubiertas: {', '.join(nombres)}")

    # =========================================================================
    # [8] EJECUCIÓN — se le pide al agente; el agente elige la tool MCP
    # =========================================================================
    async def _ejecutar_operacion(
        self, operation: str, parameters: Dict[str, Any], content: str = ""
    ) -> Dict[str, Any]:
        """
        Traduce la operación pedida a una instrucción para el agente, que llamará
        por MCP al servidor de archivos.

        Args:
            operation: operación solicitada por el Coordinador
            parameters: parámetros de la operación
            content: contenido para las operaciones de escritura

        Returns:
            Resultado de la operación, con el texto devuelto por el agente.
        """
        # [8.1] Garantizar la sesión MCP antes de invocar al modelo (ver [7]).
        await self._asegurar_conexion()

        filename = parameters.get("filename", "informe.txt")

        # [8.2] Traducir la operación A2A a una instrucción en lenguaje natural.
        #       Fíjate en que NO se nombra la función MCP a llamar: es el modelo quien
        #       elige entre las cinco tools. Antes de migrar, esto era un if/elif de
        #       cinco ramas que invocaba la función Python directamente.
        if operation == "write_file":
            texto = content or parameters.get("content", "")
            instruccion = (
                f"Escribe el siguiente contenido en el archivo '{filename}'. "
                f"Confirma el resultado.\n\nContenido:\n{texto}"
            )
        elif operation == "read_file":
            instruccion = f"Lee el archivo '{filename}' y muéstrame su contenido."
        elif operation == "list_files":
            directorio = parameters.get("directory", ".")
            patron = parameters.get("pattern", "*")
            instruccion = (
                f"Lista los archivos del directorio '{directorio}' "
                f"que coincidan con el patrón '{patron}'."
            )
        elif operation == "delete_file":
            instruccion = f"Borra el archivo '{filename}' y confirma el resultado."
        elif operation == "file_info":
            instruccion = f"Dame la información del archivo '{filename}'."
        else:
            # [8.3] Operación no contemplada: se lanza para que [6.4] la convierta
            #       en una respuesta A2A de error.
            raise ValueError(f"Operación desconocida: {operation}")

        print(f"   🔧 Delegando la operación en el servidor MCP de archivos...")
        print(f"\n   🤖 Respuesta del agente:")
        print("   ", end="", flush=True)

        # [9] ⚙️ MFA: `agent.run(..., stream=True)` devuelve un flujo asíncrono de
        #     fragmentos. Por debajo, en este único await ocurre todo el ciclo:
        #       modelo -> decide llamar a write_file -> el framework ejecuta la tool
        #       por MCP -> el servidor escribe en disco -> el resultado vuelve al
        #       modelo -> el modelo redacta la confirmación.
        #     (La variante sin streaming sería `await self.agent.run(instruccion)`.)
        mensaje = ""
        async for chunk in self.agent.run(instruccion, stream=True):
            if chunk.text:
                mensaje += chunk.text
                print(chunk.text, end="", flush=True)
        print()

        # [10] Devolver la estructura que espera el Coordinador (contrato A2A).
        #      ⚠️ `message` es la clave que el Coordinador lee para su informe.
        return {
            "filename": filename,
            "operation": operation,
            "message": mensaje.strip(),
            "mcp_tool": "servidor_archivos",
        }

    # =========================================================================
    # [11] SALIDA A2A — devolver el resultado al Coordinador
    # =========================================================================
    async def send_to_coordinator(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Devuelve los resultados al Agente Coordinador vía A2A.

        ⚠️ PENDIENTE DE MIGRAR: por ahora la entrega sigue siendo SIMULADA (devuelve
        un acuse fijo sin enviar nada). Hoy la vuelta real ocurre como valor de
        retorno de la herramienta del Coordinador, no como mensaje A2A.
        """
        print(f"\n📤 Enviando resultados al Agente Coordinador...")
        print(f"   Operación: {message.get('operation', 'desconocida')}")
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
            await self.herramienta_archivos.close()
            self._conectado = False

    async def __aenter__(self) -> "ExecutorAgent":
        """Permite usar el agente como context manager (`async with ExecutorAgent() as a:`),
        que conecta el MCP al entrar y lo cierra al salir, incluso si hay excepción."""
        await self._asegurar_conexion()
        return self

    async def __aexit__(self, *_) -> None:
        await self.cerrar()


async def main():
    """Función principal para ejecutar el Agente Ejecutor de forma aislada."""
    print("\n" + "=" * 60)
    print("🤖 Agente Ejecutor (Agente 3) - Iniciando...")
    print("=" * 60)

    # [A] El context manager abre la sesión MCP ([7]) y la cierra al terminar ([12]).
    async with ExecutorAgent() as agente:

        # [B] Ejemplo 1 — escribir un archivo. Se simula el mensaje A2A que enviaría
        #     el Coordinador: esta es exactamente la forma que espera handle_message.
        print("\n--- Ejemplo 1: escribir un archivo ---")
        peticion_escritura = {
            "type": "execution_request",
            "sender": "coordinator-agent",
            "data": {
                "operation": "write_file",
                "parameters": {"filename": "informe_clima.txt"},
                "content": "Informe del clima:\nTemperatura: 22 °C\nCondiciones: Soleado",
            },
        }

        respuesta = await agente.handle_message(peticion_escritura)
        print(f"\n✅ ¡Operación completada!")
        print(f"   Estado: {respuesta['status']}")

        await agente.send_to_coordinator(respuesta)

        # [C] Ejemplo 2 — listar archivos.
        #     🐞 Antes de migrar, este ejemplo leía `response['results']['count']`,
        #        una clave que la operación NUNCA devolvía: reventaba con KeyError.
        print("\n--- Ejemplo 2: listar archivos ---")
        peticion_listado = {
            "type": "execution_request",
            "sender": "coordinator-agent",
            "data": {
                "operation": "list_files",
                "parameters": {"directory": ".", "pattern": "*.txt"},
            },
        }

        respuesta = await agente.handle_message(peticion_listado)
        print(f"\n✅ ¡Operación completada!")
        print(f"   Estado: {respuesta['status']}")

        await agente.send_to_coordinator(respuesta)

    print(f"\n✨ Demo del Agente Ejecutor finalizada correctamente.")


if __name__ == "__main__":
    asyncio.run(main())
