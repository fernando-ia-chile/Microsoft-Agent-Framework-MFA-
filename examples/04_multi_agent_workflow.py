"""
Ejemplo 04 – Flujo multi-agente
================================
Muestra cómo orquestar varios agentes especializados en una única
conversación de grupo usando AutoGen 0.7.x.

Escenario: Revisión de código
------------------------------
Un desarrollador envía un fragmento de código Python.  Tres agentes
especializados colaboran en rondas:

  1. Revisor de seguridad  – detecta vulnerabilidades.
  2. Revisor de estilo     – verifica PEP-8 / buenas prácticas.
  3. Sintetizador          – consolida los comentarios en un resumen
                             accionable.

Conceptos clave
---------------
* RoundRobinGroupChat – cada agente habla una vez por turno (round robin).
* MaxMessageTermination – detiene la conversación tras N mensajes.
* TextMentionTermination – detiene cuando un agente escribe "REVISION COMPLETADA".
* Console(team.run_stream(...)) – muestra el chat en la terminal.

Prerequisitos
-------------
* OPENAI_API_KEY  (o variables de Azure, ver ejemplo 03)
* pip install -r requirements.txt

Como ejecutar
-------------
    python examples/04_multi_agent_workflow.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key.startswith("sk-..."):
    sys.exit(
        "ERROR: OPENAI_API_KEY no configurada.\n"
        "Copia .env.example -> .env y rellena tu clave de OpenAI."
    )

try:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.ui import Console
    from autogen_ext.models.openai import OpenAIChatCompletionClient
except ImportError:
    sys.exit(
        "Ejecuta: pip install pyautogen autogen-ext[openai]\n"
        "(o pip install -r requirements.txt)"
    )

# -- Cliente de modelo compartido ----------------------------------------------
model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

model_client = OpenAIChatCompletionClient(
    model=model,
    api_key=api_key,
    temperature=0,
    max_tokens=400,
)

# -- Definicion de los agentes especializados ----------------------------------

revisor_seguridad = AssistantAgent(
    name="Revisor_Seguridad",
    model_client=model_client,
    system_message=(
        "Eres un experto en seguridad de software Python. "
        "Analiza el codigo que se te presenta y lista SOLO los problemas "
        "de seguridad (inyeccion, gestion de secretos, validacion de entradas, etc.). "
        "Se conciso: usa vinetas, maximo 5 puntos. Responde en espanol. "
        "Cuando termines, escribe HANDOFF."
    ),
)

revisor_estilo = AssistantAgent(
    name="Revisor_Estilo",
    model_client=model_client,
    system_message=(
        "Eres un experto en calidad de codigo Python (PEP-8, type hints, "
        "docstrings, nombres descriptivos). "
        "Analiza el codigo y lista SOLO los problemas de estilo y mantenibilidad. "
        "Se conciso: usa vinetas, maximo 5 puntos. Responde en espanol. "
        "Cuando termines, escribe HANDOFF."
    ),
)

sintetizador = AssistantAgent(
    name="Sintetizador",
    model_client=model_client,
    system_message=(
        "Eres el lider tecnico del equipo. Recibiras comentarios de un revisor "
        "de seguridad y uno de estilo. Tu trabajo es consolidar todos los "
        "hallazgos en un resumen ejecutivo ordenado por prioridad (Alta / Media / Baja). "
        "Termina siempre con 'REVISION COMPLETADA'. Responde en espanol."
    ),
)

# -- Condicion de terminacion --------------------------------------------------
termination = TextMentionTermination("REVISION COMPLETADA") | MaxMessageTermination(10)

# -- Equipo en rondas alternadas -----------------------------------------------
# Orden: revisor_seguridad -> revisor_estilo -> sintetizador -> (repite si es necesario)
team = RoundRobinGroupChat(
    participants=[revisor_seguridad, revisor_estilo, sintetizador],
    termination_condition=termination,
)

# -- Codigo de ejemplo a revisar -----------------------------------------------
CODIGO_A_REVISAR = """\
import os, subprocess, sys

def ejecutar_comando(cmd):
    password = "admin123"  # contrasena hardcodeada
    result = subprocess.run(cmd, shell=True, capture_output=True)
    return result.stdout

def obtener_usuario(id):
    query = f"SELECT * FROM users WHERE id={id}"
    return query
"""

TAREA = (
    "Por favor revisar el siguiente codigo Python:\n\n"
    "```python\n"
    f"{CODIGO_A_REVISAR}"
    "```\n\n"
    "Necesito analisis de seguridad, estilo y un resumen final."
)


async def main() -> None:
    print("=" * 60)
    print("Ejemplo 04 - Flujo multi-agente (revision de codigo)")
    print(f"Modelo: {model}")
    print("=" * 60)
    print("\nAgentes en el equipo:")
    for agent in team._participants:
        print(f"  * {agent.name}")
    print(f"\nCodigo enviado para revision:\n{CODIGO_A_REVISAR}")
    print("-" * 60)

    await Console(team.run_stream(task=TAREA))

    print("-" * 60)
    print("\nFlujo multi-agente completado.")
    print("Proximo paso -> ejecuta:  python examples/05_semantic_kernel_agent.py")
    await model_client.close()


if __name__ == "__main__":
    asyncio.run(main())
