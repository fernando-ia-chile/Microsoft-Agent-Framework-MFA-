"""
Ejemplo 02 – Agente conectado a OpenAI
=======================================
Demuestra cómo conectar un AssistantAgent de AutoGen 0.7.x al servicio
público de OpenAI usando tu clave API.

Prerequisitos
-------------
1. Instala las dependencias:
       pip install -r requirements.txt
2. Copia el archivo de entorno de ejemplo:
       cp .env.example .env
3. Edita .env y pon tu OPENAI_API_KEY real.

Cómo ejecutar
-------------
    python examples/02_openai_agent.py

Conceptos clave
---------------
* OpenAIChatCompletionClient – cliente que AutoGen usa para llamar a
  la API de OpenAI.  Acepta model, api_key, temperature, max_tokens, etc.
* AssistantAgent(model_client=...)  – recibe el cliente como parámetro.
* RoundRobinGroupChat – orquesta los turnos entre agentes.
* Console(team.run_stream(...))  – imprime la conversación en la terminal.
* MaxMessageTermination  – detiene la conversación tras N mensajes.
"""

import asyncio
import os
import sys

# ── Carga de variables de entorno ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("Ejecuta: pip install python-dotenv  (o pip install -r requirements.txt)")

load_dotenv()

# ── Verificar que la clave está presente ──────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key.startswith("sk-..."):
    sys.exit(
        "ERROR: OPENAI_API_KEY no configurada.\n"
        "Copia .env.example → .env y rellena tu clave de OpenAI."
    )

# ── Importar AutoGen ──────────────────────────────────────────────────────────
try:
    from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
    from autogen_agentchat.conditions import MaxMessageTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.ui import Console
    from autogen_ext.models.openai import OpenAIChatCompletionClient
except ImportError:
    sys.exit(
        "Ejecuta: pip install pyautogen autogen-ext[openai]\n"
        "(o pip install -r requirements.txt)"
    )

# ── Configuración del modelo ──────────────────────────────────────────────────
# Best practice: nunca pongas la api_key directamente aquí; léela desde .env.
model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# OpenAIChatCompletionClient acepta los mismos parámetros que la API de OpenAI.
# temperature=0  →  respuestas deterministas y reproducibles.
# max_tokens     →  evita respuestas extremadamente largas / costosas.
model_client = OpenAIChatCompletionClient(
    model=model,
    api_key=api_key,
    temperature=0,
    max_tokens=512,
)

# ── Definición de agentes ─────────────────────────────────────────────────────
assistant = AssistantAgent(
    name="asistente_openai",
    model_client=model_client,
    system_message=(
        "Eres un experto en Microsoft Agent Framework (AutoGen). "
        "Responde siempre en español, de forma concisa y con ejemplos de código "
        "cuando sea útil. Si una pregunta está fuera de tu área de expertise, "
        "indícalo claramente. Cuando termines de responder, escribe TERMINATE."
    ),
)

# UserProxyAgent sin input_func → no interrumpe la ejecución automatizada.
user_proxy = UserProxyAgent(name="desarrollador")

# ── Condición de terminación ──────────────────────────────────────────────────
# La conversación se detiene cuando el asistente escribe "TERMINATE" o tras
# 3 mensajes (lo que ocurra primero).
from autogen_agentchat.conditions import TextMentionTermination

termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(3)

# ── Equipo de agentes ─────────────────────────────────────────────────────────
team = RoundRobinGroupChat(
    participants=[assistant, user_proxy],
    termination_condition=termination,
)

# ── Conversación de ejemplo ───────────────────────────────────────────────────
PREGUNTA = (
    "En tres puntos breves, explica qué es Microsoft AutoGen y para qué sirve."
)


async def main() -> None:
    print("=" * 60)
    print("Ejemplo 02 – Agente conectado a OpenAI")
    print(f"Modelo: {model}")
    print("=" * 60)
    print(f"\nPregunta del desarrollador:\n  {PREGUNTA}\n")
    print("-" * 60)

    await Console(team.run_stream(task=PREGUNTA))

    print("-" * 60)
    print("\nConversación completada.")
    print("Próximo paso → ejecuta:  python examples/03_azure_openai_agent.py")
    await model_client.close()


if __name__ == "__main__":
    asyncio.run(main())
