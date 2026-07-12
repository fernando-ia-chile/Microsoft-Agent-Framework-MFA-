"""
Ejemplo 03 – Agente conectado a Azure OpenAI
=============================================
Idéntico en lógica al ejemplo 02, pero apuntando al endpoint de
Azure OpenAI en lugar del API público de OpenAI.

Cuándo usar Azure OpenAI en lugar de OpenAI público
----------------------------------------------------
* Datos en reposo dentro de tu suscripción de Azure (compliance / GDPR).
* Integración con redes privadas (VNet, Private Link).
* Uso de modelos fine-tuned desplegados en tu propio recurso.
* Facturación unificada con otros servicios Azure.

Prerequisitos
-------------
1. Recurso de Azure OpenAI creado en tu suscripción.
2. Despliegue de un modelo (p.ej. gpt-4o) en Azure OpenAI Studio.
3. Variables en tu .env:
       AZURE_OPENAI_ENDPOINT
       AZURE_OPENAI_API_KEY
       AZURE_OPENAI_DEPLOYMENT
       AZURE_OPENAI_API_VERSION

Cómo ejecutar
-------------
    python examples/03_azure_openai_agent.py

Conceptos clave
---------------
* AzureOpenAIChatCompletionClient – cliente de AutoGen para Azure OpenAI.
* azure_endpoint  – tu URL de Azure OpenAI (no la de OpenAI público).
* azure_deployment – nombre de tu DESPLIEGUE en Azure (no del modelo base).
* api_version      – versión de la REST API de Azure OpenAI.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ── Verificar variables de entorno ────────────────────────────────────────────
required_vars = {
    "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
    "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
    "AZURE_OPENAI_DEPLOYMENT": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
}

missing = [k for k, v in required_vars.items() if not v or "..." in (v or "")]
if missing:
    sys.exit(
        "ERROR: Faltan las siguientes variables en tu .env:\n"
        + "\n".join(f"  • {v}" for v in missing)
        + "\n\nCopia .env.example → .env y rellena los valores de Azure OpenAI."
    )

try:
    from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.ui import Console
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
except ImportError:
    sys.exit(
        "Ejecuta: pip install pyautogen autogen-ext[openai]\n"
        "(o pip install -r requirements.txt)"
    )

# ── Configuración del modelo ──────────────────────────────────────────────────
model_client = AzureOpenAIChatCompletionClient(
    model=required_vars["AZURE_OPENAI_DEPLOYMENT"],       # nombre del despliegue
    azure_endpoint=required_vars["AZURE_OPENAI_ENDPOINT"],
    api_key=required_vars["AZURE_OPENAI_API_KEY"],
    api_version=required_vars["AZURE_OPENAI_API_VERSION"],
    temperature=0,
    max_tokens=512,
)

# ── Definición de agentes ─────────────────────────────────────────────────────
assistant = AssistantAgent(
    name="asistente_azure",
    model_client=model_client,
    system_message=(
        "Eres un experto en arquitecturas de IA en la nube con Azure. "
        "Explica siempre los conceptos con claridad y en español. "
        "Cuando menciones servicios de Azure, incluye el nombre oficial "
        "tal como aparece en el portal de Azure. "
        "Cuando termines de responder, escribe TERMINATE."
    ),
)

user_proxy = UserProxyAgent(name="arquitecto")

termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(3)

team = RoundRobinGroupChat(
    participants=[assistant, user_proxy],
    termination_condition=termination,
)

# ── Conversación de ejemplo ───────────────────────────────────────────────────
PREGUNTA = (
    "¿Cuáles son las tres principales diferencias entre usar OpenAI directamente "
    "y usar Azure OpenAI Service desde el punto de vista de seguridad y compliance?"
)


async def main() -> None:
    endpoint = required_vars["AZURE_OPENAI_ENDPOINT"]
    deployment = required_vars["AZURE_OPENAI_DEPLOYMENT"]

    print("=" * 60)
    print("Ejemplo 03 – Agente conectado a Azure OpenAI")
    print(f"Endpoint:   {endpoint}")
    print(f"Despliegue: {deployment}")
    print("=" * 60)
    print(f"\nPregunta del arquitecto:\n  {PREGUNTA}\n")
    print("-" * 60)

    await Console(team.run_stream(task=PREGUNTA))

    print("-" * 60)
    print("\nConversación completada.")
    print("Próximo paso → ejecuta:  python examples/04_multi_agent_workflow.py")
    await model_client.close()


if __name__ == "__main__":
    asyncio.run(main())
