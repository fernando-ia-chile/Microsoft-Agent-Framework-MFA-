"""
NUEVO 13: Middleware completo (Demo interactiva)

Objetivo pedagógico (sin cambios respecto del original):
    Mostrar los TRES tipos de middleware de MFA trabajando a la vez, y dónde se
    engancha cada uno en el ciclo de vida de una petición:

      1. TIMING     (agent)    -> mide cuánto tarda el run completo
      2. SEGURIDAD  (agent)    -> bloquea peticiones con contenido sensible
      3. LOGGER     (function) -> registra cada llamada a una tool
      4. TOKENS     (chat)     -> informa el consumo de tokens de cada llamada al modelo

    Los 1 y 2 son agent middleware, el 3 es function middleware y el 4 es chat
    middleware: cuatro piezas, tres tipos.

--- Migrado a la API actual del Microsoft Agent Framework (core 1.11.0) ---

  * AzureOpenAIChatClient(...)      -> OpenAIChatClient(azure_endpoint=, model=, ...)
  * client.create_agent(...)        -> Agent(client, instructions=, name=)
  * agent.get_new_thread()          -> agent.create_session()
  * agent.run_stream(x, thread=t)   -> agent.run(x, stream=True, session=s)
  * AgentRunContext                 -> AgentContext
  * async def mw(context, next)     -> async def mw(context, call_next)
  * await next(context)             -> await call_next()          (¡sin argumento!)
  * context.terminate = True        -> raise MiddlewareTermination(...)

Dos mejoras que trae la migración:
  1. TOKENS REALES. El middleware viejo estimaba tokens a ojo (`len(texto) // 4`)
     y leía `context.result.choices[0].message.content`, que es la forma cruda de
     la API de OpenAI y en MFA nunca existió: ese bloque no llegaba a ejecutarse.
     Ahora se leen los tokens de verdad desde `response.usage_details`.
  2. TIMING REAL EN STREAMING. Con `stream=True`, `call_next()` retorna cuando el
     stream queda *listo para consumirse*, no cuando termina. El middleware viejo
     medía solo la preparación. Ahora se usa `context.stream_result_hooks`, que se
     dispara cuando la respuesta está finalizada de verdad.

Requisitos:
  1. .env03 con AZURE_OPENAI_ENDPOINT (¡solo la base!), AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
     AZURE_OPENAI_API_KEY y AZURE_OPENAI_API_VERSION.

Utilidad:
    - Observabilidad, auditoría y control de costos sin ensuciar la lógica del agente.
    - Políticas de seguridad centralizadas (un solo punto que bloquea).
"""

import asyncio
import os
import unicodedata
from datetime import datetime
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field

from agent_framework import (
    Agent,
    AgentContext,
    ChatContext,
    FunctionInvocationContext,
    MiddlewareTermination,
    agent_middleware,
    chat_middleware,
    function_middleware,
)
from agent_framework.openai import OpenAIChatClient

# override=True: el .env03 manda sobre variables $env: viejas de la terminal.
load_dotenv('.env03', override=True)

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "preview")


# ============================================================================
# MIDDLEWARE 1: TIMING (Agent Middleware)
# ============================================================================

@agent_middleware
async def timing_middleware(context: AgentContext, call_next) -> None:
    """Mide cuánto tarda el run completo del agente.

    OJO con el streaming: `call_next()` vuelve cuando el stream está listo para
    consumirse, NO cuando terminó de emitir tokens. Por eso el tiempo final se
    reporta desde un hook de `stream_result_hooks`, que corre cuando la respuesta
    ya está finalizada.
    """
    inicio = datetime.now()
    print(f"\n⏱️  [TIMING] Inicio {inicio.strftime('%H:%M:%S')}")

    def informar(prefijo: str = "") -> None:
        duracion = (datetime.now() - inicio).total_seconds()
        print(f"{prefijo}⏱️  [TIMING] Completado en {duracion:.2f} s")

    def al_finalizar(response):
        # Corre cuando el stream terminó de emitir tokens (el caso normal).
        informar("\n")
        return response

    context.stream_result_hooks.append(al_finalizar)

    try:
        await call_next()          # antes: await next(context)
    except BaseException:
        # Otro middleware cortó la ejecución (p. ej. seguridad): el hook nunca
        # se disparará, así que informamos aquí antes de re-lanzar.
        informar()
        raise
    else:
        # Sin streaming no hay hook: `call_next()` ya devolvió la respuesta final.
        # Con streaming NO informamos aquí, porque en ese punto el stream todavía
        # no se consumió: de eso se encarga `al_finalizar`.
        if not context.stream:
            informar()


# ============================================================================
# MIDDLEWARE 2: SEGURIDAD (Agent Middleware)
# ============================================================================

PALABRAS_BLOQUEADAS = ["password", "contraseña", "secret", "hack", "exploit", "bypass"]


@agent_middleware
async def security_middleware(context: AgentContext, call_next) -> None:
    """Bloquea la petición si detecta contenido sensible.

    En la API vieja se cortaba con `context.terminate = True`. Ahora se lanza
    `MiddlewareTermination`: el framework la trata como control de flujo, corta
    el run y NO la propaga al bucle de chat, así que la demo sigue viva.
    """
    texto = " ".join((msg.text or "") for msg in context.messages).lower()

    for palabra in PALABRAS_BLOQUEADAS:
        if palabra in texto:
            print(f"\n🚫 [SEGURIDAD] ¡Petición BLOQUEADA! Detectado: '{palabra}'")
            print("🚫 [SEGURIDAD] Contiene contenido sensible y no se procesará.")
            raise MiddlewareTermination(f"Bloqueado por la palabra '{palabra}'")

    await call_next()


# ============================================================================
# MIDDLEWARE 3: LOGGER DE FUNCIONES (Function Middleware)
# ============================================================================

@function_middleware
async def function_logger_middleware(context: FunctionInvocationContext, call_next) -> None:
    """Registra cada llamada a una tool: nombre, argumentos y resultado."""
    print(f"\n🔧 [FUNCIÓN] Llamando a la tool: {context.function.name}")
    print(f"🔧 [FUNCIÓN] Argumentos: {context.arguments}")

    await call_next()

    # context.result queda disponible después de call_next(). Viene como lista de
    # objetos Content, así que hay que convertir cada uno a texto: imprimir la
    # lista directamente mostraría '<Content object at 0x...>'.
    resultado = context.result
    if isinstance(resultado, list):
        resultado = " ".join(str(parte) for parte in resultado)
    print(f"🔧 [FUNCIÓN] Resultado: {resultado}")


# ============================================================================
# MIDDLEWARE 4: CONTADOR DE TOKENS (Chat Middleware)
# ============================================================================

@chat_middleware
async def token_counter_middleware(context: ChatContext, call_next) -> None:
    """Informa el consumo REAL de tokens de cada llamada al modelo.

    `usage_details` viene del propio proveedor, no es una estimación. Trae
    input_token_count, output_token_count y total_token_count (más campos
    específicos del proveedor, como tokens cacheados o de razonamiento).
    """
    # Nota: context.messages son los mensajes NUEVOS de esta llamada; el historial
    # que aporta el history provider se resuelve en otra capa y no se cuenta aquí.
    print(f"\n🤖 [LLAMADA IA] Enviando {len(context.messages)} mensaje(s) nuevos al modelo")

    def al_finalizar(response):
        uso = response.usage_details
        if uso:
            print(f"\n🤖 [LLAMADA IA] Tokens de entrada : {uso.get('input_token_count')}")
            print(f"🤖 [LLAMADA IA] Tokens de salida  : {uso.get('output_token_count')}")
            print(f"🤖 [LLAMADA IA] Tokens totales    : {uso.get('total_token_count')}")
        return response

    context.stream_result_hooks.append(al_finalizar)

    await call_next()


# ============================================================================
# TOOLS DE LA DEMO
# ============================================================================
# Estilo Part-1: parámetros tipados con Annotated + Field(description=...) para
# que el modelo reciba un esquema claro de cada herramienta.

def get_weather(
    ciudad: Annotated[str, Field(description="Nombre de la ciudad, p. ej. 'Tokio' o 'París'")]
) -> str:
    """Consulta el clima actual de una ciudad."""
    datos = {
        "seattle": "☁️ Nublado, 15°C, llovizna ligera",
        "londres": "🌧️ Lluvioso, 12°C, lluvia fuerte",
        "tokio": "☀️ Soleado, 22°C, cielo despejado",
        "mumbai": "🌤️ Parcialmente nublado, 28°C, húmedo",
        "paris": "⛅ Parcialmente nublado, 18°C, templado",
        "santiago": "🌤️ Despejado, 24°C, seco",
        "nueva york": "🌨️ Nevando, -2°C, nieve ligera",
    }
    # Normalizamos acentos para que 'París' y 'Paris' encuentren lo mismo.
    clave = unicodedata.normalize("NFKD", ciudad.lower())
    clave = "".join(c for c in clave if not unicodedata.combining(c))
    return datos.get(clave, f"No hay datos de clima para {ciudad}")


def calculate(
    expresion: Annotated[str, Field(description="Expresión matemática, p. ej. '2 + 2' o '10 * 5'")]
) -> str:
    """Evalúa una expresión matemática."""
    try:
        # Evaluación acotada: sin builtins y con una lista blanca de funciones.
        resultado = eval(
            expresion,
            {"__builtins__": {}},
            {"abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow},
        )
        return f"Resultado: {resultado}"
    except Exception:
        return f"Error: no se pudo calcular '{expresion}'"


def get_time() -> str:
    """Devuelve la hora actual."""
    return f"Hora actual: {datetime.now().strftime('%H:%M:%S')}"


def search_database(
    consulta: Annotated[str, Field(description="Qué buscar: 'usuarios', 'productos' u 'ordenes'")]
) -> str:
    """Simula una búsqueda en una base de datos."""
    resultados = {
        "usuarios": "Se encontraron 150 usuarios que cumplen el criterio",
        "productos": "Se encontraron 45 productos en inventario",
        "ordenes": "Se encontraron 230 órdenes en los últimos 30 días",
    }
    return resultados.get(consulta.lower(), f"Sin resultados para: {consulta}")


# ============================================================================
# DEMO INTERACTIVA
# ============================================================================

async def main():
    print("\n" + "=" * 75)
    print("🎯 DEMO COMPLETA DE MIDDLEWARE - Los 3 tipos trabajando juntos")
    print("=" * 75)
    print("""
Esta demo ejecuta 4 middleware al mismo tiempo:

1️⃣  TIMING (agent)       → mide cuánto tarda cada petición
2️⃣  SEGURIDAD (agent)    → bloquea contenido sensible
3️⃣  LOGGER (function)    → registra todas las llamadas a tools
4️⃣  TOKENS (chat)        → informa el consumo real de tokens

¡Observa cómo se combinan en una conversación real!
""")
    print("=" * 75)
    print("\n🔧 Creando el agente con los 4 middleware...\n")

    chat_client = OpenAIChatClient(
        model=DEPLOYMENT,
        azure_endpoint=ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    agent = Agent(
        chat_client,
        instructions=(
            "Eres un asistente útil con acceso a varias herramientas. "
            "Sé amable, conciso y directo en tus respuestas."
        ),
        name="MiddlewareBot",
        tools=[get_weather, calculate, get_time, search_database],
        middleware=[
            timing_middleware,           # agent middleware #1
            security_middleware,         # agent middleware #2
            function_logger_middleware,  # function middleware
            token_counter_middleware,    # chat middleware
        ],
    )

    print("✅ ¡Agente creado con 4 capas de middleware!")

    print("\n" + "=" * 75)
    print("📝 PRUEBAS SUGERIDAS:")
    print("=" * 75)
    print("""
✅ PRUEBA 1: "cuéntame un chiste"
   → Dispara: Timing + Tokens
   → Petición simple, sin tools

✅ PRUEBA 2: "¿qué clima hace en Tokio?"
   → Dispara: Timing + Logger + Tokens
   → Llama a la tool get_weather

✅ PRUEBA 3: "¿qué hora es y cuánto es 15 * 8?"
   → Dispara: Timing + Logger (2 llamadas) + Tokens
   → Varias tools en un mismo turno

✅ PRUEBA 4: "¿cuál es mi password?"
   → Dispara: Seguridad (BLOQUEA) + Timing
   → ¡El middleware de seguridad corta la petición!

✅ PRUEBA 5: "busca usuarios y dame el clima de París"
   → Dispara: LOS 4 middleware
   → Varias tools, flujo completo

Escribe 'quit' para salir
""")
    print("=" * 75 + "\n")

    # Una sola sesión para toda la conversación (antes: agent.get_new_thread()).
    session = agent.create_session()

    while True:
        try:
            user_input = input("💬 Tú: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q', 'bye']:
                print("\n👋 ¡Demo terminada! Gracias por probar los middleware.")
                break

            print("\n" + "-" * 75)
            print("🔄 PROCESANDO TU PETICIÓN...")
            print("-" * 75)

            print("\n🤖 Agente: ", end="", flush=True)
            async for chunk in agent.run(user_input, stream=True, session=session):
                if chunk.text:
                    print(chunk.text, end="", flush=True)
            print("\n")

            print("-" * 75)
            print("✅ ¡Petición completada!\n")

        except KeyboardInterrupt:
            print("\n\n👋 ¡Demo terminada!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
