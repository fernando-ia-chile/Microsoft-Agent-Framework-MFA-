"""
Ejemplo 01 – Agente básico con AutoGen (sin API externa)
=========================================================
Este ejemplo muestra la forma más sencilla de crear un agente con AutoGen.
No realiza ninguna llamada a una API real: sirve para familiarizarte con
la API de AutoGen antes de conectarte a un servicio externo.

Conceptos clave
---------------
* AssistantAgent  – agente basado en LLM; recibe un model_client y un
                    system_message que define su personalidad.
* UserProxyAgent  – representa al "humano" en la conversación.
* RoundRobinGroupChat – orquesta el diálogo entre varios agentes.
* MaxMessageTermination – condición de parada (N mensajes máximo).

Cómo ejecutar (sin costo, sin clave de API)
--------------------------------------------
    python examples/01_basic_agent.py
"""

import sys

# ── Verificar la instalación ──────────────────────────────────────────────────
try:
    from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
    from autogen_agentchat.conditions import MaxMessageTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
except ImportError:
    sys.exit(
        "AutoGen no está instalado.\n"
        "Ejecuta:  pip install pyautogen autogen-ext[openai]\n"
        "O bien:   pip install -r requirements.txt"
    )


# ── Demostración de la estructura SIN llamadas a la API ──────────────────────
def demo_sin_api() -> None:
    """Muestra la estructura de los agentes AutoGen sin llamar a ninguna API."""

    print("=" * 60)
    print("Ejemplo 01 – Agente básico con AutoGen")
    print("=" * 60)
    print()
    print("Clases principales de AutoGen 0.7.x:")
    print()
    print("  AssistantAgent(")
    print('      name="asistente_educativo",')
    print('      model_client=<OpenAIChatCompletionClient>,  # ver ejemplo 02')
    print('      system_message="Eres un experto en..."')
    print("  )")
    print()
    print("  UserProxyAgent(")
    print('      name="estudiante",')
    print('      # input_func=None  →  sin intervención humana (modo demo)')
    print("  )")
    print()
    print("  termination = MaxMessageTermination(max_messages=2)")
    print()
    print("  team = RoundRobinGroupChat(")
    print("      participants=[asistente, usuario],")
    print("      termination_condition=termination,")
    print("  )")
    print()
    print("  # Para iniciar la conversación (requiere API key):")
    print("  # asyncio.run(")
    print('  #     Console(team.run_stream(task="¿Qué es AutoGen?"))')
    print("  # )")
    print()

    # Verifica que las clases se pueden instanciar (sin model_client)
    user_proxy = UserProxyAgent(name="estudiante")
    termination = MaxMessageTermination(max_messages=2)
    print("Verificación de importaciones:")
    print(f"  ✓ UserProxyAgent creado: '{user_proxy.name}'")
    print(f"  ✓ MaxMessageTermination creada: max={termination._max_messages}")
    print()
    print(
        "Próximo paso → ejecuta:  python examples/02_openai_agent.py\n"
        "(necesitas OPENAI_API_KEY en tu archivo .env)"
    )
    print("=" * 60)


if __name__ == "__main__":
    demo_sin_api()
