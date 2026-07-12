"""
Ejemplo 05 - Agente con Semantic Kernel
========================================
Muestra como usar Microsoft Semantic Kernel (SK) como alternativa /
complemento a AutoGen para construir agentes con herramientas (plugins).

¿Qué es Semantic Kernel?
-------------------------
Semantic Kernel es el SDK de orquestación de IA de Microsoft.  Permite:
  * Definir "plugins" (funciones Python decoradas con @kernel_function).
  * Encadenar llamadas al LLM con logica de negocio propia.
  * Conectar a OpenAI, Azure OpenAI y modelos Hugging Face.

Escenario: Asistente de aprendizaje con herramientas
-----------------------------------------------------
El agente puede:
  1. Responder preguntas sobre un tema.
  2. Evaluar respuestas del alumno y dar retroalimentacion.
  3. Generar un quiz de practica.

Prerequisitos
-------------
* OPENAI_API_KEY  (o variables de Azure)
* pip install -r requirements.txt   # incluye semantic-kernel>=1.3.0

Como ejecutar
-------------
    python examples/05_semantic_kernel_agent.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# -- Verificar dependencias ----------------------------------------------------
try:
    import semantic_kernel as sk
    from semantic_kernel.connectors.ai.open_ai import (
        AzureChatCompletion,
        OpenAIChatCompletion,
    )
    from semantic_kernel.contents import ChatHistory
    from semantic_kernel.functions import kernel_function
except ImportError:
    sys.exit(
        "Semantic Kernel no esta instalado.\n"
        "Ejecuta: pip install semantic-kernel  (o pip install -r requirements.txt)"
    )

# -- Seleccion del backend: OpenAI o Azure OpenAI ------------------------------
USE_AZURE = bool(
    os.getenv("AZURE_OPENAI_ENDPOINT")
    and os.getenv("AZURE_OPENAI_API_KEY")
    and "..." not in (os.getenv("AZURE_OPENAI_ENDPOINT") or "")
)


def build_kernel() -> sk.Kernel:
    """Construye y devuelve un Kernel configurado segun las variables de entorno."""
    kernel = sk.Kernel()

    if USE_AZURE:
        service = AzureChatCompletion(
            service_id="chat",
            deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )
        print("Backend: Azure OpenAI")
    else:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-..."):
            sys.exit(
                "ERROR: Configura OPENAI_API_KEY o las variables de Azure en .env"
            )
        service = OpenAIChatCompletion(
            service_id="chat",
            ai_model_id=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=api_key,
        )
        print(f"Backend: OpenAI ({os.getenv('OPENAI_MODEL', 'gpt-4o-mini')})")

    kernel.add_service(service)
    return kernel


# -- Plugin: Asistente de Aprendizaje -----------------------------------------
class AsistenteAprendizaje:
    """Plugin con funciones educativas disponibles para el agente."""

    @kernel_function(
        name="explicar_concepto",
        description="Explica un concepto de Microsoft Agent Framework de forma sencilla.",
    )
    def explicar_concepto(self, concepto: str) -> str:
        # Esta funcion genera el prompt que el kernel enviara al LLM.
        return (
            f"Explica el concepto '{concepto}' de Microsoft Agent Framework "
            f"en dos parrafos cortos, con un ejemplo practico en Python al final. "
            f"Habla en espanol."
        )

    @kernel_function(
        name="generar_quiz",
        description="Genera preguntas de practica sobre un tema.",
    )
    def generar_quiz(self, tema: str, num_preguntas: int = 3) -> str:
        return (
            f"Genera {num_preguntas} preguntas de opcion multiple sobre '{tema}' "
            f"en el contexto de Microsoft AutoGen / Semantic Kernel. "
            f"Incluye la respuesta correcta al final de cada pregunta. "
            f"Responde en espanol."
        )

    @kernel_function(
        name="evaluar_respuesta",
        description="Evalua la respuesta de un alumno y da retroalimentacion.",
    )
    def evaluar_respuesta(self, pregunta: str, respuesta_alumno: str) -> str:
        return (
            f"Pregunta: {pregunta}\n"
            f"Respuesta del alumno: {respuesta_alumno}\n\n"
            f"Evalua si la respuesta es correcta, explica los aciertos y errores, "
            f"y da una calificacion de 0 a 10.  Responde en espanol."
        )


async def invocar_con_plugin(
    service: OpenAIChatCompletion,
    plugin: AsistenteAprendizaje,
    func_name: str,
    **kwargs,
) -> str:
    """Genera el prompt via el plugin y luego lo envia al LLM."""
    func = getattr(plugin, func_name)
    prompt = func(**kwargs)

    history = ChatHistory()
    history.add_user_message(prompt)

    settings = service.instantiate_prompt_execution_settings(
        service_id="chat",
        temperature=0,
        max_tokens=512,
    )

    responses = await service.get_chat_message_contents(
        chat_history=history,
        settings=settings,
    )
    return str(responses[0]) if responses else "(sin respuesta)"


async def demo_semantic_kernel(kernel: sk.Kernel) -> None:
    """Ejecuta una demostracion de las funciones del plugin."""
    print("\n-- Demostracion de funciones del plugin --")

    plugin = AsistenteAprendizaje()
    service: OpenAIChatCompletion = kernel.get_service("chat")

    # 1. Explicar un concepto
    print("\n[1] Explicando el concepto 'RoundRobinGroupChat'...")
    respuesta = await invocar_con_plugin(
        service, plugin, "explicar_concepto", concepto="RoundRobinGroupChat"
    )
    print(respuesta)

    # 2. Generar un quiz
    print("\n[2] Generando quiz sobre AutoGen...")
    quiz = await invocar_con_plugin(
        service, plugin, "generar_quiz", tema="AutoGen", num_preguntas=2
    )
    print(quiz)

    # 3. Evaluar una respuesta
    print("\n[3] Evaluando respuesta del alumno...")
    evaluacion = await invocar_con_plugin(
        service,
        plugin,
        "evaluar_respuesta",
        pregunta="Que hace MaxMessageTermination en AutoGen?",
        respuesta_alumno="Detiene la conversacion cuando se alcanza el numero maximo de mensajes.",
    )
    print(evaluacion)


async def main() -> None:
    print("=" * 60)
    print("Ejemplo 05 - Agente con Semantic Kernel")
    print("=" * 60)

    kernel = build_kernel()
    await demo_semantic_kernel(kernel)

    print("\n" + "-" * 60)
    print("Demostracion Semantic Kernel completada.")
    print("Proximo paso -> ejecuta:  python examples/06_best_practices.py")


if __name__ == "__main__":
    asyncio.run(main())
