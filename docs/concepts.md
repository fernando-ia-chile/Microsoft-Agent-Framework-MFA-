# Conceptos Clave de Microsoft Agent Framework

Una referencia rápida de los conceptos principales que aparecen en los ejemplos.

---

## 1. ¿Qué es un Agente de IA?

Un **agente de IA** es un programa que:
1. Recibe un objetivo o mensaje.
2. Planifica los pasos necesarios para lograrlo.
3. Llama a herramientas (APIs, funciones, buscadores).
4. Produce una respuesta o ejecuta una acción.

---

## 2. Microsoft AutoGen

[AutoGen](https://github.com/microsoft/autogen) es el framework de Microsoft
Research para construir flujos de trabajo multi-agente conversacionales.

### Componentes principales

| Clase | Rol |
|-------|-----|
| `AssistantAgent` | Agente basado en LLM; responde mensajes y puede ejecutar código. |
| `UserProxyAgent` | Representa al humano; inicia conversaciones y puede ejecutar código localmente. |
| `GroupChat` | Permite que varios agentes dialoguen en un chat compartido. |
| `GroupChatManager` | Orquesta los turnos dentro de un `GroupChat`. |

### Ciclo de conversación

```
UserProxy  →  initiate_chat(message)
               ↓
         AssistantAgent responde
               ↓
         UserProxy decide si continuar
               ↓  (según max_consecutive_auto_reply)
         TERMINAR o nueva vuelta
```

### Parámetros importantes de `AssistantAgent` (AutoGen 0.7.x)

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

model_client = OpenAIChatCompletionClient(
    model="gpt-4o-mini",
    api_key="...",    # leer desde .env, nunca hardcodear
    temperature=0,    # 0 = determinista
    max_tokens=512,   # límite de respuesta
)

AssistantAgent(
    name="nombre_del_agente",
    model_client=model_client,
    system_message="Tu personalidad / instrucciones aquí.",
)
```

### Cómo iniciar una conversación (API async)

```python
import asyncio
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console

termination = MaxMessageTermination(max_messages=4)
team = RoundRobinGroupChat(
    participants=[asistente, usuario],
    termination_condition=termination,
)
asyncio.run(Console(team.run_stream(task="¿Qué es AutoGen?")))
```

### Condiciones de terminación disponibles

| Clase | Detiene cuando… |
|-------|----------------|
| `MaxMessageTermination(n)` | Se alcanza el límite de N mensajes. |
| `TextMentionTermination("TERMINATE")` | Un agente escribe la palabra clave. |
| `TimeoutTermination(60)` | Pasan más de 60 segundos. |
| `SourceMatchTermination(["agent"])` | Un agente específico responde. |


---

## 3. Microsoft Semantic Kernel

[Semantic Kernel](https://github.com/microsoft/semantic-kernel) es el SDK
de orquestación de IA de Microsoft.

### Diferencia con AutoGen

| Característica | AutoGen | Semantic Kernel |
|----------------|---------|-----------------|
| Foco | Conversaciones multi-agente | Orquestación de funciones / plugins |
| Paradigma | Chat entre agentes | Pipeline de funciones con LLM |
| Planificación | Conversacional | Función → LLM → Función |
| Mejor para | Colaboración entre agentes | Integrar IA en aplicaciones existentes |

### Componentes principales

```
Kernel
├── Services (OpenAI / Azure OpenAI / Hugging Face)
├── Plugins (colecciones de funciones)
│   └── @kernel_function  ← decorador que expone una función al LLM
└── Planner (opcional)    ← planifica el orden de llamadas automáticamente
```

### Ejemplo mínimo de plugin

```python
from semantic_kernel.functions import kernel_function

class MiPlugin:
    @kernel_function(
        name="saludar",
        description="Genera un saludo personalizado.",
    )
    def saludar(self, nombre: str) -> str:
        return f"Por favor genera un saludo formal para {nombre}."
```

---

## 4. OpenAI vs. Azure OpenAI

| Aspecto | OpenAI | Azure OpenAI |
|---------|--------|--------------|
| URL | `api.openai.com` | `<tu-recurso>.openai.azure.com` |
| Autenticación | `OPENAI_API_KEY` | `AZURE_OPENAI_API_KEY` + endpoint |
| Identificador del modelo | `gpt-4o-mini` (nombre del modelo) | Nombre de tu **despliegue** |
| Residencia de datos | Servidores de OpenAI | Tu suscripción de Azure |
| Compliance | Política de OpenAI | SLA / compliance de Azure |
| `api_type` en AutoGen | (no se especifica) | `"azure"` |

### Cuándo elegir Azure OpenAI

- Datos sensibles o regulados (HIPAA, ISO 27001, GDPR).
- Redes privadas / sin internet público.
- Facturación unificada con Azure.
- Fine-tuning de modelos propios.

---

## 5. Patrones de diseño recomendados

### 5.1 Patrón: Validación fail-fast

```python
# ✅ CORRECTO: valida al inicio, antes de hacer nada
def iniciar_agente(api_key: str) -> None:
    if not api_key:
        raise ValueError("api_key es obligatoria")
    # ... resto del código

# ❌ INCORRECTO: descubre el error tarde
def iniciar_agente(api_key: str) -> None:
    agente = crear_agente_costoso()
    resultado = agente.ejecutar()  # falla aquí con un mensaje oscuro
```

### 5.2 Patrón: Configuración por entorno

```
proyecto/
├── .env              ← local (en .gitignore)
├── .env.example      ← plantilla (SÍ se versiona)
└── config.py         ← lee variables de entorno, nunca hardcodea valores
```

### 5.3 Patrón: Un agente = una responsabilidad

```python
# ✅ CORRECTO: agentes especializados
revisor_seguridad  = AssistantAgent(name="seguridad", ...)
revisor_estilo     = AssistantAgent(name="estilo", ...)
sintetizador       = AssistantAgent(name="lider", ...)

# ❌ INCORRECTO: un agente con múltiples roles mezclados
agente_todo        = AssistantAgent(name="hace_todo", system_message="Eres revisor, escritor y QA...")
```

---

## 6. Glosario

| Término | Definición |
|---------|-----------|
| LLM | Large Language Model – modelo de lenguaje grande (p. ej. GPT-4o). |
| llm_config | Diccionario que AutoGen usa para configurar las llamadas al LLM. |
| GroupChat | Sala de chat virtual donde varios agentes se comunican. |
| Plugin (SK) | Clase con métodos decorados con `@kernel_function`. |
| Kernel (SK) | Objeto central de Semantic Kernel que gestiona servicios y plugins. |
| `temperature` | Controla la aleatoriedad: 0 = determinista, 1 = creativo. |
| `max_tokens` | Número máximo de tokens (≈ palabras) en la respuesta del LLM. |
| `timeout` | Segundos antes de cancelar una llamada a la API. |
| Rate limit | Límite de llamadas por minuto/hora impuesto por la API. |
| Backoff | Estrategia de espera creciente entre reintentos. |
