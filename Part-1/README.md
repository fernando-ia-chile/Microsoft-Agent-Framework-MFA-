# Microsoft Agent Framework — Parte 1 · Fundamentos (modernizado a core 1.11.0)

> Serie práctica de aprendizaje del **Microsoft Agent Framework (MFA)** sobre Azure.
> Esta **Parte 1** cubre los fundamentos en 8 demos interactivas de terminal, **migradas desde la API beta original a la API estable actual (core `1.11.0`)**.

**Autor:** Fernando Valdés H.

---

## 📑 Tabla de contenidos

- [Descripción](#-descripción)
- [Estado de la migración](#-estado-de-la-migración)
- [Requisitos e instalación](#-requisitos-e-instalación)
- [Configuración (.env)](#-configuración-env)
- [Cómo ejecutar](#-cómo-ejecutar)
- [Tabla comparativa maestra (API beta → API 1.11.0)](#-tabla-comparativa-maestra-api-beta--api-1110)
- [Detalle de cambios por demo](#-detalle-de-cambios-por-demo)
- [Componentes deprecados / en preview (reporte MFA)](#-componentes-deprecados--en-preview-reporte-mfa)
- [Notas técnicas y gotchas](#-notas-técnicas-y-gotchas)
- [Roadmap / pendientes](#-roadmap--pendientes)
- [Autoría](#-autoría)

---

## 🎯 Descripción

Cada archivo `new_0N_*.py` es una **demo autónoma, ejecutable e interactiva** que enseña un concepto del framework, ordenadas como progresión de aprendizaje:

1. Crear un agente persistente en Azure AI Foundry
2. Reutilizar un agente existente
3. Chat directo con Azure OpenAI
4. Búsqueda en documentos (File Search / vector store)
5. Una herramienta (function tool)
6. Múltiples herramientas
7. Human-in-the-loop (aprobación humana)
8. Salida estructurada con Pydantic

### El porqué de la modernización

El código del tutorial original fue escrito para una **API beta de 2025** (`ChatAgent`, `run_stream`, `AzureAIAgentClient`, `HostedFileSearchTool`) que **ya no existe**. El entorno actual usa la línea estable **core `1.11.0`**, que renombró, movió o eliminó esas piezas. Este proyecto **moderniza cada demo manteniendo su objetivo pedagógico**, usando siempre métodos vigentes dentro de MFA.

---

## ✅ Estado de la migración

| # | Demo | Estado | Cliente / patrón |
|:-:|------|:------:|------------------|
| 01 | `new_01_create_agent.py` | ✅ | Foundry (persistente) |
| 02 | `new_02_use_existing_agent.py` | ✅ | Foundry (existente) |
| 03 | `new_03_direct_openai_chat.py` | ✅ | Azure OpenAI directo |
| 04 | `new_04_file_search_tool.py` | ✅ | Foundry + File Search |
| 05 | `new_05_function_tool_calculator.py` | ✅ | Azure OpenAI + 1 tool |
| 06 | `new_06_multiple_tools.py` | ✅ | Azure OpenAI + N tools |
| 07 | `new_07_human_in_the_loop.py` | ✅ | Azure OpenAI + aprobación nativa |
| 08 | `new_08_structured_output.py` | ✅ | Azure OpenAI + Pydantic |

**Las 8 demos de Parte 1 están migradas a core `1.11.0`.**

---

## 📦 Requisitos e instalación

- **Python 3.14** (probado en 3.14.2)
- Una suscripción de Azure con **Azure AI Foundry** y/o **Azure OpenAI**
- **Azure CLI** (`az login`) para las demos de Foundry (01, 02, 04)

```powershell
# Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # PowerShell

# Instalar dependencias
pip install -r requirements.txt
```

### Dependencias fijadas (`requirements.txt`)

> ⚠️ Se evita el meta-paquete `agent-framework` porque arrastra `agent-framework-azure-ai==1.0.0rc6`, **incompatible** con core 1.11.0. Se instalan los subpaquetes concretos:

| Paquete | Versión | Rol |
|---------|:-------:|-----|
| `agent-framework-core` | `1.11.0` | Núcleo (`Agent`, `tool`, `Message`, …) |
| `agent-framework-foundry` | `1.10.1` | `FoundryChatClient`, `FoundryAgent`, `to_prompt_agent` |
| `agent-framework-openai` | `1.10.1` | `OpenAIChatClient` (nativo-Azure) |
| `azure-ai-projects` | `2.3.0` | Publicar/gestionar agentes en Foundry |
| `azure-identity` | `>=1.25.0` | `AzureCliCredential` |
| `python-dotenv` | `>=1.0.0` | Carga de archivos `.env` |
| `requests` | `>=2.31.0` | Usado por la demo 06 |

---

## 🔧 Configuración (.env)

Cada demo carga **su propio archivo `.env`** de forma explícita (no hay un `.env` compartido).

**`.env01` / `.env02`** — Azure AI Foundry (requiere `az login`):

```dotenv
# .env01 (demos 01 y 04)
AZURE_AI_PROJECT_ENDPOINT=https://<recurso>.services.ai.azure.com/api/projects/<proyecto>
AZURE_AI_MODEL_DEPLOYMENT_NAME=<nombre-del-deployment>
VECTOR_STORE_ID=<id-del-vector-store>   # solo demo 04

# .env02 (demo 02)
AZURE_AI_PROJECT_ENDPOINT=https://<recurso>.services.ai.azure.com/api/projects/<proyecto>
AZURE_AI_AGENT_NAME=DemoAssistant
# AZURE_AI_AGENT_VERSION=1               # opcional; si se omite, se usa la última
```

**`.env03`** — Azure OpenAI directo (demos 03, 05, 06, 07, 08):

```dotenv
AZURE_OPENAI_ENDPOINT=https://<recurso>.services.ai.azure.com   # SOLO la base, sin /openai/...
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<nombre-del-deployment>
AZURE_OPENAI_API_KEY=<tu-api-key>
AZURE_OPENAI_API_VERSION=preview        # alias rolling = última preview de Azure
```

---

## ▶️ Cómo ejecutar

```powershell
# Con el venv activo, desde el directorio Part-1:
python new_01_create_agent.py       # (o cualquier otra demo)
```

Cada script abre un bucle de chat con `input()`; escribe `quit`, `exit` o `q` para salir.

---

## 🔁 Tabla comparativa maestra (API beta → API 1.11.0)

Componentes y métodos actualizados, transversales a todas las demos:

| Concepto | API beta (original) | API 1.11.0 (actual) |
|----------|---------------------|---------------------|
| Clase de agente | `ChatAgent(chat_client=...)` | `Agent(client, ...)` |
| Cliente Foundry | `AzureAIAgentClient(...)` | `FoundryChatClient(...)` / `FoundryAgent(...)` |
| Cliente Azure OpenAI | `AzureOpenAIChatClient(endpoint=, deployment_name=, ...)` | `OpenAIChatClient(azure_endpoint=, model=, api_key=, api_version=)` |
| Crear agente persistente | `project_client.agents.create_agent(model, name, instructions)` | `to_prompt_agent(agent)` → `AIProjectClient.agents.create_version(agent_name, definition=)` |
| Conectar a agente existente | `AzureAIAgentClient(agent_id=...)` | `FoundryAgent(agent_name=, agent_version=)` |
| Streaming | `agent.run_stream(texto)` | `agent.run(texto, stream=True)` (el chunk trae `.text`) |
| File search | `HostedFileSearchTool(inputs=[HostedVectorStoreContent(vector_store_id=)], max_results=)` | `chat_client.get_file_search_tool(vector_store_ids=[...], max_num_results=)` |
| Function tools | funciones con `Annotated[..., Field(...)]` en `tools=[...]` | **sin cambios** |
| Aprobación humana | wrapper casero `ApprovalRequiredTool` | `@tool(approval_mode="always_require")` + `result.user_input_requests` + `req.to_function_approval_response(bool)` |
| Salida estructurada | `agent.run(texto, response_format=Modelo)` | `agent.run(texto, options={"response_format": Modelo})` (se lee `response.value`) |
| Versión de API (Azure OpenAI) | `2025-01-01-preview` (fecha fija) | `preview` (alias rolling = última) |
| Import Foundry | `from agent_framework.azure import AzureAIAgentClient` | `from agent_framework.foundry import FoundryChatClient, FoundryAgent, to_prompt_agent` |
| Import OpenAI | `from agent_framework.azure import AzureOpenAIChatClient` | `from agent_framework.openai import OpenAIChatClient` |

---

## 📝 Detalle de cambios por demo

### 01 · `new_01_create_agent.py` — Crear agente persistente
- `ChatAgent` → `Agent`; `AzureAIAgentClient` → `FoundryChatClient` (definir) + `FoundryAgent` (chatear).
- Creación de agente persistente vía `to_prompt_agent(agent)` → `AIProjectClient.agents.create_version(agent_name, definition=)`.
- `run_stream(x)` → `run(x, stream=True)`.
- Nota: `to_prompt_agent` es **experimental** (emite `ExperimentalWarning`).

### 02 · `new_02_use_existing_agent.py` — Reutilizar agente
- `AzureAIAgentClient(agent_id=)` → `FoundryAgent(agent_name=, agent_version=)`.
- Cambio de semántica: antes se identificaba por **ID**, ahora por **nombre + versión**. La demo resuelve la **última versión** automáticamente con `project_client.agents.list_versions(name, order="desc", limit=1)` si no se fija `AZURE_AI_AGENT_VERSION`.
- Reutiliza un único `AIProjectClient` para listar versiones y para chatear.

### 03 · `new_03_direct_openai_chat.py` — Chat directo Azure OpenAI
- `AzureOpenAIChatClient(...)` → `OpenAIChatClient(azure_endpoint=, model=, api_key=, api_version=)` (nativo-Azure, Responses API).
- `client.create_agent(...)` → `Agent(client, ...)`.
- `AZURE_OPENAI_API_VERSION`: `2025-01-01-preview` → `preview` (default del framework para la Responses API).

### 04 · `new_04_file_search_tool.py` — File Search / vector store
- `AzureAIAgentClient` → `FoundryChatClient`.
- `HostedFileSearchTool(inputs=[HostedVectorStoreContent(...)], max_results=5)` → `chat_client.get_file_search_tool(vector_store_ids=[...], max_num_results=5)`.
- Método confirmado con la documentación oficial de Microsoft (sección *Hosted Agents*).

### 05 · `new_05_function_tool_calculator.py` — Una function tool
- Mismo patrón que la demo 03; `client.create_agent(..., tools=[calculate])` → `Agent(client, ..., tools=[calculate])`.
- Las function tools **no cambian**: siguen siendo funciones con `Annotated[..., Field(...)]`.

### 06 · `new_06_multiple_tools.py` — Múltiples function tools
- Igual que la 05, con `tools=[get_weather, calculate, get_time]`.
- `get_time` usa `requests` contra una API externa; si falla, la tool devuelve el error y el agente continúa. (Mejora futura opcional: usar `zoneinfo`/`datetime` local.)

### 07 · `new_07_human_in_the_loop.py` — Aprobación humana **nativa**
- Se **eliminó** el wrapper casero `ApprovalRequiredTool` (con su desanidado manual y prints `[DEBUG]`).
- Aprobación nativa de MFA: `@tool(approval_mode="always_require")` para la operación peligrosa (`delete_file`); `create_file` es un `@tool` normal.
- El bucle inspecciona `result.user_input_requests`, pide aprobación por cada uno y responde con `req.to_function_approval_response(bool)` reenviando el contexto con `Message`.

### 08 · `new_08_structured_output.py` — Salida estructurada
- `AzureOpenAIChatClient` → `OpenAIChatClient` (nativo-Azure).
- Cambio clave: `response_format` **ya no es kwarg directo** de `run()`; ahora va en `options`: `agent.run(texto, options={"response_format": PersonInfo})`.
- El objeto Pydantic se lee igual desde `response.value`.

---

## 🧭 Componentes deprecados / en preview (reporte MFA)

Componentes que, por la evolución del framework, quedaron **eliminados**, **experimentales** o en **preview** (siempre dentro de MFA):

| Componente | Estado | Reemplazo / nota |
|------------|:------:|------------------|
| `HostedFileSearchTool`, `HostedVectorStoreContent` | ❌ Eliminados | `FoundryChatClient.get_file_search_tool(...)` |
| `ChatAgent`, `AzureAIAgentClient`, `AzureOpenAIChatClient`, `run_stream` | ❌ Renombrados/eliminados | Ver tabla comparativa maestra |
| `to_prompt_agent` | ⚗️ Experimental | Funciona; puede cambiar sin aviso (`ExperimentalWarning`) |
| Wrapper casero `ApprovalRequiredTool` | ❌ Obsoleto | Aprobación nativa `@tool(approval_mode=...)` |
| Providers de memoria (Mem0, Neo4j, Purview, Redis) | 🔬 Preview | Relevantes para Parte 2/3 |
| Providers RAG (Azure AI Search, Neo4j GraphRAG) | 🔬 Preview | Relevantes para Parte 2/3 |

> Dato de infraestructura (no de código): los roles RBAC de Foundry se renombraron (*Azure AI User/Owner…* → *Foundry User/Owner…*); los IDs y permisos no cambian.

---

## ⚠️ Notas técnicas y gotchas

- **Endpoint de Azure OpenAI (Responses):** `AZURE_OPENAI_ENDPOINT` debe ser **solo la base** del recurso (`https://<recurso>.services.ai.azure.com`). El framework agrega `/openai/v1/` automáticamente; incluir la ruta completa provoca un **404 Resource not found**.
- **Precedencia de variables (PowerShell):** `load_dotenv()` no sobrescribe variables ya presentes en la sesión. Si defines `$env:AZURE_OPENAI_*` a mano, esos valores **pisan** al `.env`. Las demos 03 y 05–08 usan `load_dotenv('.env03', override=True)` para que el archivo mande. Alternativa: usar una terminal nueva o `Remove-Item Env:AZURE_OPENAI_ENDPOINT`.
- **Diagnóstico:** `diag_env.py` imprime las variables efectivas, la URL final y **lista los deployments** del recurso (útil para depurar 404 / nombres de modelo).
- **Modelos:** las demos leen el **nombre del deployment** (no el de la familia del modelo) desde las variables de entorno. Cambiar de modelo = cambiar el deployment en el `.env` (y re-publicar el agente de la demo 01 para que tome el nuevo modelo).
- **Seguridad:** este repositorio versiona los `.env`. **No** subas claves reales; se recomienda añadir un `.gitignore` para `.env*` y regenerar cualquier clave que haya sido expuesta.

---

## 🗺️ Roadmap / pendientes

- [ ] Pruebas end-to-end de las demos 03–08 con credenciales reales.
- [ ] Añadir `.gitignore` para `.env*` y sacar los `.env` del control de versiones.
- [ ] (Opcional) Aplicar `load_dotenv(override=True)` también en las demos 01 y 02.
- [ ] Migrar **Parte 2** (threading, memoria, middleware, observabilidad, MCP) y **Parte 3** (workflows).

---

## ✍️ Autoría

**Fernando Valdés H.**

Proyecto educativo de modernización del *Microsoft Agent Framework* (Parte 1). El código de las demos se basa en el tutorial original de la serie y fue actualizado a la API estable `core 1.11.0`.
