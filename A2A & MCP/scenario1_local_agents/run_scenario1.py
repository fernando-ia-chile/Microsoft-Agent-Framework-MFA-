"""
Escenario 1 - Script Principal de Orquestación
==============================================
Demuestra el flujo completo de tres agentes locales que se comunican por A2A
y usan servidores MCP locales.

Flujo:
1. El usuario escribe una petición
2. El Agente Coordinador la analiza y planifica el flujo
3. El Coordinador delega en el Agente de Investigación (MCP de clima)
4. El Coordinador delega en el Agente Ejecutor (MCP de archivos)
5. El Coordinador agrega los resultados y responde al usuario

Ejecutar:
    python run_scenario1.py

Migrado a Microsoft Agent Framework (core 1.12.0) + SDK MCP 1.28.1:
- Los tres agentes son `Agent` de MFA y hablan MCP de verdad (stdio)
- El orquestador gestiona el CICLO DE VIDA de las sesiones MCP
- `demonstrate_agent_communication` estaba muerto y roto -> resucitado y funcional

-------------------------------------------------------------------------------
ORDEN DE EJECUCIÓN (los comentarios [n] del código siguen esta numeración)
-------------------------------------------------------------------------------
  [0]-[2]  Arranque del módulo: UTF-8, .env, logging
  [3]      main()                      -> punto de entrada
  [4]      modo_interactivo()          -> crea el orquestador y abre el bucle
  [5]      Scenario1Orchestrator.__init__ -> construye los tres agentes
  [6]      __aenter__ / __aexit__      -> abre y cierra las sesiones MCP
  [7]      _verificar_configuracion    -> comprueba las credenciales
  [8]      Bucle de comandos del usuario
  [9]      ejecutar_flujo_completo()   -> delega en el Coordinador
  [10]     demostrar_comunicacion_a2a() -> mensajes A2A directos, sin Coordinador

Convención de los comentarios:
  ⚙️ MFA   = instrucción propia del Microsoft Agent Framework
  📡 A2A   = relativo a la comunicación Agente-a-Agente
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

from dotenv import load_dotenv

# [0] 🔧 Infra: forzar UTF-8 (la consola de Windows usa cp1252 y revienta con emojis).
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# [1] 🔧 Infra: cargar el .env con ruta absoluta y añadir agents/ al path.
DIRECTORIO_ESCENARIO = Path(__file__).resolve().parent
load_dotenv(DIRECTORIO_ESCENARIO / ".env", override=True)
sys.path.insert(0, str(DIRECTORIO_ESCENARIO / "agents"))

# [2] 🔧 Infra: silenciar el ruido de transporte para no tapar la interfaz didáctica.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
for _ruidoso in ("httpx", "httpcore", "mcp", "openai", "agent_framework"):
    logging.getLogger(_ruidoso).setLevel(logging.WARNING)

from agent1_research import ResearchAgent  # noqa: E402
from agent2_coordinator import CoordinatorAgent  # noqa: E402
from agent3_executor import ExecutorAgent  # noqa: E402


class Scenario1Orchestrator:
    """Orquestador del Escenario 1: agentes locales con MCP y A2A."""

    # =========================================================================
    # [5] CONSTRUCCIÓN — crea los tres agentes y los conecta entre sí
    # =========================================================================
    def __init__(self):
        """Crea los tres agentes (todavía SIN abrir las sesiones MCP)."""
        print("\n" + "=" * 70)
        print("🚀 ESCENARIO 1: Agentes locales con Azure OpenAI y servidores MCP")
        print("=" * 70)

        print("\n📋 Inicializando agentes...")

        # [5.1] Los agentes especializados se crean primero: el Coordinador necesita
        #       una referencia a cada uno para poder delegarles trabajo por A2A.
        self.research_agent = ResearchAgent()
        self.executor_agent = ExecutorAgent()

        # [5.2] 📡 A2A: el Coordinador recibe a sus dos "contactos". Sin ellos, sus
        #       herramientas devolverían un error en vez de delegar.
        self.coordinator_agent = CoordinatorAgent(
            research_agent=self.research_agent,
            executor_agent=self.executor_agent,
        )

        print("\n✅ ¡Los tres agentes se inicializaron correctamente!")

        # [7] Comprobar las credenciales antes de empezar.
        self._verificar_configuracion()

    # =========================================================================
    # [6] CICLO DE VIDA MCP — abrir y cerrar las sesiones de los servidores
    # =========================================================================
    async def __aenter__(self) -> "Scenario1Orchestrator":
        """
        Abre las sesiones MCP de los agentes que las necesitan.

        ⚙️ MFA + 🔌 MCP: cada agente lanza su servidor MCP como subproceso. Abrirlos
        aquí, una sola vez para toda la sesión interactiva, evita arrancar y matar
        los subprocesos en cada pregunta del usuario.
        """
        print("\n🔌 Abriendo las sesiones MCP de los agentes...")
        await self.research_agent.__aenter__()
        await self.executor_agent.__aenter__()
        return self

    async def __aexit__(self, *_) -> None:
        """Cierra las sesiones MCP y termina los subprocesos de los servidores."""
        print("\n🔌 Cerrando las sesiones MCP...")
        await self.executor_agent.cerrar()
        await self.research_agent.cerrar()

    # =========================================================================
    # [7] VERIFICACIÓN DE CONFIGURACIÓN
    # =========================================================================
    def _verificar_configuracion(self) -> None:
        """Comprueba que estén definidas las variables de entorno necesarias."""
        # ⚠️ Antes de la migración estas variables NO hacían falta: el cliente de
        #    Azure OpenAI se creaba pero nunca se usaba. Ahora los tres agentes
        #    llaman al modelo de verdad, así que sin credenciales no funcionan.
        requeridas = [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_DEPLOYMENT_NAME",
        ]

        faltantes = [v for v in requeridas if not os.getenv(v)]

        if faltantes:
            print(f"\n⚠️  Faltan variables de entorno: {', '.join(faltantes)}")
            print("   Configúralas en el archivo .env antes de continuar.")
        else:
            print(f"\n✅ Configuración de Azure OpenAI verificada")
            print(f"   Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
            print(f"   Modelo:   {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}")

    # =========================================================================
    # [9] FLUJO COMPLETO — el camino normal: todo pasa por el Coordinador
    # =========================================================================
    async def ejecutar_flujo_completo(self, peticion_usuario: str) -> Dict[str, Any]:
        """
        Ejecuta el flujo multiagente completo para una petición del usuario.

        Args:
            peticion_usuario: petición en lenguaje natural.
        """
        print("\n" + "=" * 70)
        print("🎯 Iniciando el flujo de trabajo completo")
        print("=" * 70)

        print(f"\n👤 Petición del usuario:")
        print(f'   "{peticion_usuario}"')

        print(f"\n{'=' * 70}")
        print(f"📍 PASO 1: el Agente Coordinador planifica el flujo")
        print(f"{'=' * 70}")

        # [9.1] 📡 A2A: el orquestador NO habla con los agentes especializados.
        #       Solo entrega la petición al Coordinador, que decide y delega.
        respuesta = await self.coordinator_agent.process_user_request(peticion_usuario)

        print(f"\n{'=' * 70}")
        print(f"✅ FLUJO COMPLETADO")
        print(f"{'=' * 70}")

        # [9.2] Mostrar el informe agregado que devuelve el Coordinador.
        print(f"\n📊 Resultados finales:")
        print(f"   Estado: {respuesta['status']}")
        print(f"   Pasos completados: {respuesta['successful_steps']}/{respuesta['total_steps']}")

        # [9.3] Detallar qué agente atendió cada paso delegado.
        for i, paso in enumerate(respuesta.get("results", []), 1):
            icono = "✅" if paso.get("status") == "success" else "❌"
            print(f"   {icono} Paso {i}: {paso.get('agent_id', 'desconocido')}")

        return respuesta

    # =========================================================================
    # [10] DEMOSTRACIÓN A2A DIRECTA — sin pasar por el Coordinador
    # =========================================================================
    async def demostrar_comunicacion_a2a(self) -> None:
        """
        Envía mensajes A2A directos a cada agente, saltándose al Coordinador.

        Sirve para ver el protocolo "desnudo": qué mensaje entra y qué respuesta
        sale, sin que un LLM decida nada por el camino.

        🐞 Este método existía antes de la migración pero **nunca se invocaba** y
           además estaba roto: hacía el ping sin `await` sobre un método asíncrono.
        """
        print("\n" + "=" * 70)
        print("🔄 Demostración de comunicación Agente-a-Agente (A2A)")
        print("=" * 70)

        # [10.1] Demo 1 — mensaje directo al Agente de Investigación.
        print(f"\n{'=' * 70}")
        print("📡 Demo 1: mensaje directo -> Agente de Investigación")
        print(f"{'=' * 70}")

        peticion_investigacion = {
            "type": "research_request",
            "sender": "orchestrator",
            "data": {
                "task": "weather_lookup",
                "parameters": {"city": "Valparaíso", "country": "Chile"},
            },
        }

        respuesta_investigacion = await self.research_agent.handle_message(peticion_investigacion)
        print(f"\n✅ Estado devuelto: {respuesta_investigacion.get('status')}")

        # [10.2] Demo 2 — mensaje directo al Agente Ejecutor, encadenando el
        #        resultado anterior. Es A2A a mano: aquí no hay LLM decidiendo.
        print(f"\n{'=' * 70}")
        print("📡 Demo 2: mensaje directo -> Agente Ejecutor")
        print(f"{'=' * 70}")

        contenido = respuesta_investigacion.get("results", {}).get("weather_data", "Sin datos")

        peticion_ejecucion = {
            "type": "execution_request",
            "sender": "orchestrator",
            "data": {
                "operation": "write_file",
                "parameters": {"filename": "demo_a2a.txt"},
                "content": contenido,
            },
        }

        respuesta_ejecucion = await self.executor_agent.handle_message(peticion_ejecucion)
        print(f"\n✅ Estado devuelto: {respuesta_ejecucion.get('status')}")

        # [10.3] Demo 3 — ping a los tres agentes. El mensaje `ping` no gasta tokens
        #        ni toca MCP: solo comprueba que el buzón del agente responde.
        print(f"\n{'=' * 70}")
        print("📡 Demo 3: comprobación de salud (ping a los tres agentes)")
        print(f"{'=' * 70}")

        ping = {"type": "ping", "sender": "orchestrator"}

        agentes = [
            ("Agente de Investigación", self.research_agent),
            ("Agente Coordinador", self.coordinator_agent),
            ("Agente Ejecutor", self.executor_agent),
        ]

        for nombre, agente in agentes:
            # 🐞 Aquí faltaba el `await`: los tres handle_message son asíncronos.
            respuesta = await agente.handle_message(ping)
            estado = respuesta.get("status", "desconocido")
            icono = "✅" if estado == "active" else "❌"
            print(f"   {icono} {nombre}: {estado}")

    # =========================================================================
    # DIAGRAMA DE ARQUITECTURA
    # =========================================================================
    def imprimir_diagrama_arquitectura(self) -> None:
        """Muestra el diagrama de arquitectura del escenario."""
        print("\n" + "=" * 70)
        print("🏗️  ARQUITECTURA DEL ESCENARIO 1")
        print("=" * 70)
        # ⚠️ El diagrama anterior dibujaba los servidores MCP escuchando en los
        #    puertos 8001 y 8002. Era falso: el transporte es stdio y no abre
        #    ningún puerto. Cada servidor es un SUBPROCESO del agente que lo usa.
        print(
            """
    ┌──────────────────────────────────────────────────────────┐
    │                    Entorno local                         │
    │                                                          │
    │                    👤 Usuario                            │
    │                        │                                 │
    │                        ▼                                 │
    │              ┌───────────────────┐                       │
    │              │  Agente 2         │                       │
    │              │  COORDINADOR      │  (decide y delega)    │
    │              └─────────┬─────────┘                       │
    │                        │ A2A                             │
    │            ┌───────────┴───────────┐                     │
    │            ▼                       ▼                     │
    │   ┌─────────────────┐    ┌──────────────────┐            │
    │   │   Agente 1      │    │   Agente 3       │            │
    │   │   INVESTIGACIÓN │    │   EJECUTOR       │            │
    │   └────────┬────────┘    └─────────┬────────┘            │
    │            │ MCP (stdio)           │ MCP (stdio)         │
    │            ▼                       ▼                     │
    │   ┌─────────────────┐    ┌──────────────────┐            │
    │   │ Servidor MCP    │    │ Servidor MCP     │            │
    │   │ Clima           │    │ Archivos         │            │
    │   │ (subproceso)    │    │ (subproceso)     │            │
    │   └────────┬────────┘    └─────────┬────────┘            │
    │            │                       │                     │
    └────────────┼───────────────────────┼─────────────────────┘
                 ▼                       ▼
        🌍 API Open-Meteo        📂 agent_workspace/

    Los tres agentes usan Azure OpenAI como modelo.
        """
        )


# =============================================================================
# PANTALLAS DE AYUDA DE LA INTERFAZ
# =============================================================================
def mostrar_ciudades_populares() -> None:
    """Muestra una lista de ciudades de ejemplo."""
    print("\n" + "=" * 70)
    print("🌆 CIUDADES POPULARES POR REGIÓN")
    print("=" * 70)

    # ✅ Antes de la migración el Coordinador solo entendía 6 ciudades australianas
    #    y mandaba todo lo demás a Melbourne. Ahora el modelo extrae la ciudad, así
    #    que funciona cualquier ciudad del mundo.
    ciudades = {
        "Sudamérica": ["Santiago", "Buenos Aires", "Lima", "Bogotá", "São Paulo"],
        "Norteamérica": ["Ciudad de México", "Nueva York", "Toronto", "Los Ángeles"],
        "Europa": ["Madrid", "Londres", "París", "Berlín", "Roma"],
        "Asia": ["Tokio", "Singapur", "Bangkok", "Seúl", "Bombay"],
        "Oceanía": ["Melbourne", "Sídney", "Auckland", "Brisbane"],
        "África": ["El Cairo", "Lagos", "Ciudad del Cabo", "Nairobi"],
    }

    for region, lista in ciudades.items():
        print(f"\n🌍 {region}:")
        print(f"   {', '.join(lista)}")

    print("\n💡 Puedes escribir el nombre en español o en inglés.")
    print("   Ejemplo: '¿Qué tiempo hace en Tokio, Japón?'")


def mostrar_protocolo_a2a() -> None:
    """Explica el protocolo A2A tal como está implementado en este escenario."""
    print("\n" + "=" * 70)
    print("📡 EL PROTOCOLO AGENTE-A-AGENTE (A2A)")
    print("=" * 70)

    print("\n🔄 ¿Qué es la comunicación A2A?")
    print("   Permite que unos agentes deleguen tareas en otros, compartan")
    print("   información y colaboren en flujos de trabajo complejos.")

    print("\n📨 Estructura del mensaje A2A:")
    print(
        """
   {
     "sender": "coordinator-agent",      // quién envía
     "recipient": "research-agent",      // quién recibe
     "type": "research_request",         // tipo de petición
     "data": {                           // carga útil
       "task": "weather_lookup",
       "parameters": {"city": "Tokio", "country": "Japón"}
     },
     "timestamp": 1234567890.123
   }
    """
    )

    print("\n📬 Estructura de la respuesta A2A:")
    print(
        """
   {
     "agent_id": "research-agent",       // quién responde
     "status": "success",                // success | error | active
     "task": "weather_lookup",
     "results": { ... },                 // el resultado real
     "metadata": {"source": "...", "confidence": "high"}
   }
    """
    )

    print("\n🎯 Tipos de mensaje admitidos:")
    print("   • research_request   - pedir información (Agente de Investigación)")
    print("   • execution_request  - pedir una acción  (Agente Ejecutor)")
    print("   • workflow_request   - delegar un flujo completo (Coordinador)")
    print("   • ping               - comprobación de salud (los tres)")

    print("\n🔍 Cómo verlo en vivo:")
    print("   • Haz una pregunta normal: verás las cajas del mensaje A2A.")
    print("   • Escribe 'a2a-directo' para enviar mensajes sin pasar por el")
    print("     Coordinador, es decir, sin ningún LLM decidiendo por el camino.")


def mostrar_ayuda() -> None:
    """Muestra la ayuda de la interfaz."""
    print("\n" + "=" * 70)
    print("❓ AYUDA - CÓMO USAR EL ASISTENTE")
    print("=" * 70)

    print("\n📖 Qué puedes pedir:")
    print("   • Clima actual:  '¿Qué tiempo hace en Santiago?'")
    print("   • Pronóstico:    'Dame el pronóstico de 5 días de Lima'")
    print("   • Avisos:        '¿Hay avisos meteorológicos en Melbourne?'")
    print("   • Guardar:       '...y guárdalo en un archivo'")

    print("\n🎯 Cómo formular la petición:")
    print("   • Indica la ciudad (obligatorio)")
    print("   • Añade el país para mayor precisión (recomendado)")
    print("   • Menciona 'guardar' o 'archivo' para generar un informe")

    print("\n✅ Buenos ejemplos:")
    print("   ✓ 'Clima en Valparaíso, Chile'")
    print("   ✓ 'Pronóstico de Tokio y guárdalo en un archivo'")
    print("   ✓ '¿Qué temperatura hace en Londres?'")

    print("\n❌ Qué no va a funcionar:")
    print("   ✗ 'Clima' (no indicas ciudad)")
    print("   ✗ 'Cuéntame un chiste' (no es meteorológico)")

    print("\n🔧 Comandos especiales:")
    print("   • 'ciudades'    - ver ciudades de ejemplo")
    print("   • 'demo'        - ejecutar ejemplos automáticos")
    print("   • 'a2a'         - explicación del protocolo A2A")
    print("   • 'a2a-directo' - mensajes A2A sin pasar por el Coordinador")
    print("   • 'arquitectura'- ver el diagrama del escenario")
    print("   • 'salir'       - terminar la sesión")


# =============================================================================
# [11] EJEMPLOS AUTOMÁTICOS
# =============================================================================
async def ejecutar_ejemplos_demo(orquestador: Scenario1Orchestrator) -> None:
    """Ejecuta una serie de peticiones de ejemplo, una tras otra."""
    print("\n\n" + "=" * 70)
    print("🎬 EJECUTANDO EJEMPLOS AUTOMÁTICOS")
    print("=" * 70)

    peticiones = [
        "¿Qué tiempo hace en Santiago, Chile? Guárdalo en informe_santiago.txt",
        "Dame el pronóstico de 3 días de Madrid, España",
        "¿Hay avisos meteorológicos en Melbourne, Australia?",
    ]

    for i, peticion in enumerate(peticiones, 1):
        print(f"\n{'#' * 70}")
        print(f"# EJEMPLO {i}/{len(peticiones)}")
        print(f"{'#' * 70}")

        await orquestador.ejecutar_flujo_completo(peticion)

        if i < len(peticiones):
            print("\n⏸️  Pulsa Enter para pasar al siguiente ejemplo...")
            input()

    print("\n✅ Ejemplos completados.")


# =============================================================================
# [8] BUCLE INTERACTIVO
# =============================================================================
async def modo_interactivo() -> None:
    """Modo interactivo: el usuario escribe sus propias peticiones."""
    print("\n" + "=" * 70)
    print("🎮 MODO INTERACTIVO")
    print("=" * 70)

    # [4] Crear el orquestador ([5]) y abrir las sesiones MCP ([6]).
    #     El `async with` garantiza que los subprocesos de los servidores MCP se
    #     cierren aunque el usuario interrumpa la sesión con Ctrl+C.
    async with Scenario1Orchestrator() as orquestador:

        orquestador.imprimir_diagrama_arquitectura()

        print("\n\n" + "=" * 70)
        print("💡 ASISTENTE METEOROLÓGICO MULTIAGENTE")
        print("=" * 70)
        print("\n🌍 ¡Pregúntame por el clima de cualquier ciudad del mundo!")
        print("\n📝 Ejemplos:")
        print("   • ¿Qué tiempo hace en Santiago, Chile?")
        print("   • Dame el pronóstico de Tokio, Japón")
        print("   • Clima en Londres y guárdalo en un archivo")
        print("\n🎯 Comandos rápidos:")
        print("   • 'ciudades' | 'demo' | 'a2a' | 'a2a-directo' | 'arquitectura'")
        print("   • 'ayuda' para más información")
        print("   • 'salir' para terminar\n")

        # [8.1] Bucle principal: leer, clasificar y ejecutar.
        while True:
            print("\n" + "-" * 70)
            entrada = input("🤔 Tu pregunta: ").strip()

            if not entrada:
                print("⚠️  Escribe una pregunta.")
                continue

            comando = entrada.lower()

            # [8.2] Comandos de salida.
            if comando in ("salir", "quit", "exit", "q"):
                print("\n👋 ¡Gracias por usar el asistente multiagente!")
                break

            # [8.3] Comandos de la interfaz (no consumen tokens).
            if comando == "demo":
                await ejecutar_ejemplos_demo(orquestador)
                continue

            if comando == "ciudades":
                mostrar_ciudades_populares()
                continue

            if comando in ("ayuda", "help"):
                mostrar_ayuda()
                continue

            if comando == "a2a":
                mostrar_protocolo_a2a()
                continue

            if comando in ("a2a-directo", "a2a-direct"):
                # [8.4] Demostración A2A sin Coordinador ([10]).
                await orquestador.demostrar_comunicacion_a2a()
                continue

            if comando in ("arquitectura", "arch"):
                orquestador.imprimir_diagrama_arquitectura()
                continue

            # [8.5] Cualquier otra cosa es una petición para el flujo multiagente.
            print(f"\n{'=' * 70}")
            print(f"🔄 Procesando tu petición...")
            print(f"{'=' * 70}")

            try:
                await orquestador.ejecutar_flujo_completo(entrada)
                print(f"\n✨ ¡Listo! Haz otra pregunta o escribe 'salir'.")
            except Exception as e:
                print(f"\n❌ Error procesando la petición: {e}")
                print("💡 Comprueba que has indicado una ciudad.")
                import traceback

                traceback.print_exc()


# =============================================================================
# [3] PUNTO DE ENTRADA
# =============================================================================
async def main():
    """Punto de entrada del Escenario 1."""
    print("\n" + "=" * 70)
    print("🚀 BIENVENIDO AL ESCENARIO 1")
    print("Asistente meteorológico multiagente con comunicación A2A")
    print("=" * 70)
    print("\n🎮 Iniciando el modo interactivo...")
    print("💡 Verás las estructuras de los mensajes A2A en tiempo real.\n")

    await modo_interactivo()

    print(
        """
    ✅ Se ha demostrado:
       • Tres agentes locales (Investigación, Coordinación, Ejecución)
       • Comunicación Agente-a-Agente (A2A)
       • Integración con servidores MCP reales (clima y archivos)
       • Orquestación de flujos multiagente decidida por el modelo
       • Uso de modelos de Azure OpenAI a través de Microsoft Agent Framework

    📚 Siguientes pasos:
       • Explora el Escenario 2 para ver agentes alojados en Azure AI Foundry
       • Modifica las instrucciones de los agentes y observa el cambio
       • Añade herramientas nuevas a los servidores MCP

    💡 Consejos:
       • Los archivos generados quedan en agent_workspace/
       • Cambia el modelo en el archivo .env
    """
    )


if __name__ == "__main__":
    print(
        """
    ╔═══════════════════════════════════════════════════════════╗
    ║   Microsoft Agent Framework - Escenario 1                 ║
    ║   Agentes locales con comunicación A2A y servidores MCP   ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
