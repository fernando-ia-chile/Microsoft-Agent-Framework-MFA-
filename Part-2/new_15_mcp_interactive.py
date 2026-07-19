"""
NUEVO 15: MCP interactivo — agente + servidor de calculadora (Demo interactiva)

Objetivo pedagógico (sin cambios respecto del original):
    Mostrar que un agente puede usar herramientas que NO están definidas en su
    propio código, sino que vienen de un servidor MCP externo. El agente descubre
    las tools en tiempo de ejecución y las llama cuando las necesita.

    MCP (Model Context Protocol) es un estándar: el mismo servidor lo podría
    consumir Claude Desktop, VS Code u otro agente. El cliente y el servidor se
    desarrollan por separado.

Cómo funciona esta demo:
    1. `MCPStdioTool` lanza `mcp_calculator_server.py` como proceso hijo.
    2. Cliente y servidor se hablan por STDIO con mensajes JSON-RPC.
    3. El agente descubre las tools del servidor (sumar, dividir, raiz_cuadrada...).
    4. Tú preguntas en lenguaje natural y el agente decide qué tool llamar.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---

  * AzureOpenAIChatClient(...)      -> OpenAIChatClient(azure_endpoint=, model=, ...)
  * client.create_agent(...)        -> Agent(client, instructions=, name=)
  * agent.run(x) sin sesión         -> agent.run(x, stream=True, session=s)
  * `MCPStdioTool` sobrevive sin cambios (misma clase, mismos argumentos).

Además se arreglaron dos defectos del original:
  1. El comando estaba codificado como `venv\\Scripts\\uvx.exe`: una ruta relativa
     de Windows a un venv que no existe en esta carpeta. Fallaba siempre.
  2. El agente no usaba sesión, así que no recordaba nada entre preguntas
     (no se podía decir "y ahora divídelo por 2").

Servidor propio en vez de descargar uno de terceros:
    El original hacía `uvx mcp-server-calculator`, que requiere tener `uv`
    instalado y descargar un paquete de terceros en la primera ejecución. Aquí el
    servidor viene incluido (`mcp_calculator_server.py`), así que la demo funciona
    offline y además se puede LEER el código del servidor, que es la mitad
    interesante de MCP.

    Si prefieres el camino original con un servidor de terceros, instala uv
    (`pip install uv`) y reemplaza el bloque de MCPStdioTool por:

        async with MCPStdioTool(
            name="calculadora",
            command="uvx",
            args=["mcp-server-calculator"],
        ) as servidor_mcp:
            ...

Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT (¡solo la base!), AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.
  2. `mcp_calculator_server.py` en esta misma carpeta.

Utilidad:
    - Integrar herramientas de terceros sin escribir un wrapper por cada una.
    - Reutilizar el mismo servidor de tools en varios agentes o aplicaciones.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from agent_framework import Agent, MCPStdioTool
from agent_framework.openai import OpenAIChatClient

# override=True: el .env03 manda sobre variables $env: viejas de la terminal.
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "preview")

# Ruta absoluta al servidor, junto a este archivo. Así la demo funciona aunque se
# lance desde otro directorio de trabajo (el original usaba una ruta relativa
# frágil que fallaba siempre).
SERVIDOR_MCP = Path(__file__).parent / "mcp_calculator_server.py"


async def main():
    print("\n" + "=" * 75)
    print("🔌 DEMO MCP INTERACTIVA - Servidor de calculadora")
    print("=" * 75)
    print(f"""
Esta demo conecta el agente a un servidor MCP LOCAL.

CÓMO FUNCIONA:
1. Se lanza el servidor MCP como proceso hijo ({SERVIDOR_MCP.name})
2. Cliente y servidor se comunican por STDIO (JSON-RPC)
3. El agente DESCUBRE las tools del servidor en tiempo de ejecución
4. Tú preguntas en lenguaje natural y el agente elige qué tool usar

Lo interesante: el agente no tiene ninguna función matemática en su código.
Todo lo que sabe hacer con números se lo da el servidor MCP.
""")

    if not SERVIDOR_MCP.exists():
        print(f"❌ ERROR: no se encuentra {SERVIDOR_MCP}")
        print("   El servidor MCP debe estar en la misma carpeta que esta demo.")
        return

    try:
        print("Iniciando el servidor MCP de calculadora...")
        print(f"Comando: {Path(sys.executable).name} {SERVIDOR_MCP.name}\n")

        # MCPStdioTool lanza el servidor como proceso hijo y mantiene la conexión
        # abierta mientras dure el bloque `async with`. Usamos sys.executable para
        # garantizar que el servidor corre con el MISMO intérprete del venv.
        async with MCPStdioTool(
            name="calculadora",
            command=sys.executable,
            args=[str(SERVIDOR_MCP)],
        ) as servidor_mcp:

            print("✅ ¡Servidor MCP iniciado!\n")

            print("Creando el agente con las tools del servidor MCP...")
            chat_client = OpenAIChatClient(
                model=DEPLOYMENT,
                azure_endpoint=ENDPOINT,
                api_key=API_KEY,
                api_version=API_VERSION,
            )

            # El servidor MCP se pasa como una tool más. El framework se encarga
            # de exponerle al modelo todas las funciones que el servidor publica.
            agent = Agent(
                chat_client,
                instructions=(
                    "Eres un asistente matemático. Usa SIEMPRE las herramientas de "
                    "la calculadora para hacer cálculos, nunca calcules de cabeza. "
                    "Explica brevemente los pasos que seguiste."
                ),
                name="CalculadoraMCP",
                tools=servidor_mcp,
            )

            print("✅ ¡Agente listo con la calculadora MCP!\n")

            # Mostramos qué tools trajo el servidor: es la prueba de que el
            # descubrimiento en tiempo de ejecución funcionó.
            try:
                nombres = [f.name for f in servidor_mcp.functions]
                print(f"🔧 Tools descubiertas ({len(nombres)}): {', '.join(nombres)}\n")
            except Exception:
                pass

            print("=" * 75)
            print("MODO INTERACTIVO")
            print("=" * 75)
            print("""
Prueba con estos ejemplos:
1. "¿Cuánto es 15 * 23 + 45?"
2. "Calcula la raíz cuadrada de 256"
3. "¿Cuánto es 2 elevado a 16?"
4. "Calcula (100 + 50) * 3 / 2"
5. "Dame el seno de 45 grados"

Como hay sesión, también puedes encadenar:
   "suma 10 y 5"  ->  "ahora divide ese resultado por 3"

Escribe 'quit' para salir
            """)

            # Sesión para que el agente recuerde el hilo de la conversación
            # (el original no la tenía: cada pregunta empezaba de cero).
            session = agent.create_session()

            while True:
                try:
                    user_input = input("\n💭 Tú: ").strip()

                    if not user_input:
                        continue

                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("\n✅ ¡Gracias por probar MCP! Hasta luego.")
                        break

                    print("\n🤖 Agente: ", end="", flush=True)
                    async for chunk in agent.run(user_input, stream=True, session=session):
                        if chunk.text:
                            print(chunk.text, end="", flush=True)
                    print()

                except KeyboardInterrupt:
                    print("\n\n✅ Saliendo...")
                    break
                except Exception as e:
                    print(f"\n❌ Error: {e}")

    except FileNotFoundError:
        print("\n❌ ERROR: no se pudo lanzar el servidor MCP.")
        print(f"   Intérprete: {sys.executable}")
        print(f"   Servidor  : {SERVIDOR_MCP}")
        print("\nVerifica que el paquete 'mcp' esté instalado:")
        print("   pip install -r requirements.txt")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nDIAGNÓSTICO:")
        print("   1. ¿Está instalado el paquete 'mcp'?  pip install mcp")
        print(f"   2. ¿Corre el servidor a mano?  python {SERVIDOR_MCP.name}")
        print("   3. ¿El endpoint de .env03 es solo la base, sin /openai/...?")


if __name__ == "__main__":
    asyncio.run(main())
