# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Idioma:** todo en español — comunicación, documentación y comentarios del código.
> **Bitácora:** registra TODO cambio de código, dependencia o decisión en [Memory.md](Memory.md) (más reciente arriba), con el formato `## AAAA-MM-DD — <archivo/componente>` + **Cambio / Motivo / Notas**.
> **Migración:** una demo a la vez, esperando confirmación del usuario antes de pasar a la siguiente. Métodos modernos pero **equivalentes**, sin salirse de MFA, preservando el objetivo pedagógico.

## Qué es esto

Cuarto bloque de la serie, junto a `Part-1/` (fundamentos), `Part-2/` (transversales) y `Part-3/` (workflows). Este bloque cubre **A2A (Agent-to-Agent) + MCP** mediante dos escenarios independientes que resuelven lo mismo de dos formas:

- **`scenario1_local_agents/`** — tres agentes Python locales (Research, Coordinator, Executor) + dos servidores MCP locales (clima, ficheros).
- **`scenario2_azure_foundry/`** — tres agentes alojados en Azure AI Foundry Agent Service + el MCP remoto de Microsoft Learn.

Los dos escenarios **no comparten código, ni `requirements.txt`, ni `.env`**. Se desarrollan por separado.

## 🚨 Punto de partida: aquí NO se usa `agent_framework` en absoluto

Diferencia estructural frente a Part-1/2/3: **este bloque nunca importó MFA.** El escenario 1 usa `openai.AzureOpenAI` en crudo más clases Python propias; el escenario 2 usa `azure.ai.projects` / `azure.ai.agents` en crudo.

Por tanto la migración aquí **no** es "API vieja de `agent_framework` → API 1.11.0" como en las partes anteriores. Es una **reescritura sobre MFA**: sustituir simulaciones hechas a mano por los mecanismos nativos del framework. Las tablas de equivalencias de Part-1/2/3 aplican solo de forma parcial (ver más abajo).

## Estado del entorno (verificado 2026-07-22)

| Ubicación | Estado |
|---|---|
| `scenario1_local_agents/.venv` | Python 3.14.2. **Stack MFA instalado el 2026-07-22** (estaba vacío, solo `pip`). |
| `scenario2_azure_foundry/` | **Sin venv.** |

Las versiones de referencia salen del venv ya migrado de Part-1: `agent-framework-core` **1.11.0**, `agent-framework-foundry` 1.10.1, `agent-framework-openai` 1.10.1, `agent-framework-a2a` 1.0.0b260212, `a2a-sdk` 1.1.0, `mcp` 1.28.1, `httpx` 0.28.1, `openai` 2.45.0, `pydantic` 2.13.4.

Últimas versiones publicadas en PyPI a esa fecha: core **1.12.0**, foundry/openai **1.10.2**, `agent-framework-a2a` **1.0.0b260721**, `a2a-sdk` **1.1.2**, `mcp` **1.28.1** (ya al día).

## Estado de migración

Stack **ya instalado** en `scenario1_local_agents/.venv` (2026-07-22): core **1.12.0**, openai **1.10.2**, a2a **1.0.0b260721**, a2a-sdk **1.1.2**, mcp **1.28.1**, httpx 0.28.1, rich 15.0.0. Ver [requirements.txt](scenario1_local_agents/requirements.txt), con versiones pinneadas.

| Componente | Tema | Estado |
|---|---|---|
| `scenario1/agents/agent1_research.py` | Agente Research (consume MCP clima) | ✅ **Migrado y probado end-to-end** |
| `scenario1/agents/agent2_coordinator.py` | Agente Coordinator (orquesta A2A) | ✅ **Migrado y probado end-to-end** |
| `scenario1/agents/agent3_executor.py` | Agente Executor (consume MCP ficheros) | ✅ **Migrado y probado end-to-end** |
| `scenario1/mcp_servers/weather_server.py` | Servidor MCP: clima vía Open-Meteo | ✅ **Migrado al SDK MCP 1.28.1 y probado** |
| `scenario1/mcp_servers/file_operations_server.py` | Servidor MCP: operaciones de fichero | ✅ **Migrado al SDK MCP 1.28.1 y probado** |
| `scenario1/run_scenario1.py` | Orquestador + UI interactiva | ✅ **Migrado y probado end-to-end** |
| `scenario2/interactive_maf_demo.py` | Agentes Foundry + MCP Microsoft Learn | ⏳ Pendiente |

🎉 **Escenario 1 completo**: los 6 componentes migrados y probados. Ejecutar con `python run_scenario1.py`; comandos del bucle: `ciudades`, `demo`, `a2a`, `a2a-directo`, `arquitectura`, `ayuda`, `salir`.

**Contrato que respeta la migración:** los componentes migrados conservan `handle_message(dict) -> dict` y `process_research_request(dict) -> dict` con la misma forma de mensaje A2A, para no romper a los que aún no se han migrado.

## Convenciones de la migración

- **Todo en español**: `print()`, `input()`, comentarios, docstrings y las `instructions` del agente — que deben pedir explícitamente responder en español, o el modelo contesta en inglés.
- **Comentarios de secuencia numerados** `[0]`, `[1]`, `[2]`… siguiendo el **orden real de ejecución en runtime**, NO el orden de aparición en el archivo. El punto de entrada (`handle_message`) va numerado aunque esté al final del archivo. Sub-numerar los pasos internos: `[4.1]`, `[5.2]`…
- **Mapa del flujo en el docstring del módulo**: tabla `[n] -> método -> qué hace`, para seguir la demo sin leer todo el archivo.
- **Clasificar cada comentario** con una marca, para que el alumno distinga materia de andamiaje:
  - `⚙️ MFA` — instrucción propia del framework (lo que se está estudiando)
  - `🔌 MCP` — relativo al protocolo
  - `🔧 Infra` — Python/entorno, no es del framework
- **Explicar los elementos de MFA que generan dudas**, no solo nombrarlos: diferencia `ChatClient` vs `Agent`, qué hace `tools=[...]`, qué demuestra `.functions` (descubrimiento por protocolo), y qué ocurre dentro del `await` de `agent.run(stream=True)`.
- **Marcar lo que sigue simulado** con `⚠️ PENDIENTE DE MIGRAR` y decir por qué reemplazo se cambiará.
- 🚨 **En servidores MCP stdio, stdout ES el canal JSON-RPC.** Todo `print()` informativo va a **stderr**, o el cliente corta con `McpError: Connection closed`.
- 🚨 **UTF-8 obligatorio en Windows**: `sys.stdout.reconfigure(encoding="utf-8")` al inicio de cada archivo ejecutable, o los emojis revientan con `UnicodeEncodeError` (consola cp1252).
- **Silenciar el logging de transporte** (`httpx`, `httpcore`, `mcp`, `openai`, `agent_framework`) a `WARNING`, en el agente **y** en el servidor: el stderr del subproceso se mezcla con la interfaz y tapa la demo.
- **Ciclo de vida MCP**: `MCPStdioTool` es *async context manager*; usar `connect()` perezoso + `close()` y exponer `__aenter__`/`__aexit__` en el agente.
- **Lanzar el servidor MCP con `sys.executable`**, no con `"python"`: garantiza el intérprete del venv.

## Lo que el código realmente hace (≠ lo que dice el README)

El [README.md](README.md) describe la arquitectura *ideal*. El código implementa una **simulación didáctica** de esa arquitectura. Estas cuatro cosas son el verdadero objeto de la migración — ninguna es evidente leyendo un solo archivo:

1. **Nunca se habla protocolo MCP.** Los servidores declaran tools con `@mcp.tool()` y arrancan con `mcp.run(transport="stdio")`, pero los agentes **importan las funciones directamente** (`from mcp_servers.weather_server import get_weather` en [agent1_research.py:132](scenario1_local_agents/agents/agent1_research.py#L132), equivalente en [agent3_executor.py:134](scenario1_local_agents/agents/agent3_executor.py#L134)). Es una llamada Python normal: sin JSON-RPC, sin proceso aparte.
   - ⚠️ Por eso **NO hace falta arrancar los servidores en terminales separadas**, pese a lo que dice el README.
   - ⚠️ `MCP_WEATHER_SERVER_PORT` (8001) y `MCP_FILE_SERVER_PORT` (8002) son **decorativos**: solo se imprimen; el transporte es stdio y no abre ningún puerto.

2. **Nunca se llama al LLM en el escenario 1.** Los tres agentes construyen un `AzureOpenAI` y definen `system_instructions`, pero **ni el cliente ni las instrucciones se usan jamás** — no hay una sola llamada a `chat.completions`. La "planificación" del Coordinator es *keyword matching* (`_plan_workflow`) y la extracción de ciudad es un diccionario fijo (`_extract_weather_params`). Las credenciales de Azure OpenAI **no son necesarias para que corra**.

3. **A2A también es simulado.** `CoordinatorAgent._send_to_agent` imprime una caja con la "estructura del mensaje A2A" y luego **llama al método Python del otro agente** vía las referencias del constructor. `send_to_coordinator` no envía nada: devuelve un dict fijo con timestamp hardcodeado (`"2024-01-01T12:00:00Z"`). Sin referencias, el Coordinator cae a respuestas *simuladas* explícitamente etiquetadas.

4. **La única llamada real a red es el clima.** [weather_server.py](scenario1_local_agents/mcp_servers/weather_server.py) sí consulta Open-Meteo (geocoding + forecast), sin API key y con cobertura mundial.

El contraste (UI que enseña el mecanismo / implementación simplificada) es **deliberado y pedagógico**. Al migrar, mantén el estilo de terminal — banderas `===`, emojis, cajas `┌─┐` de mensajes A2A, pausas con `input()`. Es material didáctico, no ruido.

## Equivalencias objetivo (viejo → MFA 1.11.0)

Verificadas por introspección del venv de Part-1. Se irá completando conforme se migre cada componente.

**MCP — está en el core, no hace falta subpaquete** (`agent_framework._mcp`, reexportado en `agent_framework`):

| Hoy en el código | MFA 1.11.0 |
|---|---|
| `from mcp_servers.weather_server import get_weather` (import directo) | `MCPStdioTool(name=…, command=…, args=[…])` — habla MCP de verdad contra el servidor como subproceso |
| Servidor remoto por HTTP a mano (`requests` crudo) | `MCPStreamableHTTPTool(name=…, url=…)` |
| (no existe) | `MCPWebsocketTool(name=…, url=…)` |
| Aprobación de tools MCP por REST crudo | kwarg `approval_mode="always_require"` / `MCPSpecificApproval` en la propia tool |
| (no existe) | `allowed_tools=[…]`, `use_progressive_disclosure`, `task_options=MCPTaskOptions(...)`, sampling (`sampling_approval_callback`, `sampling_max_tokens`) |

**Modernización de los servidores MCP (SDK `mcp` 1.28.1)** — el esqueleto `FastMCP` + `@mcp.tool()` se conserva; lo que cambia son los metadatos:

| API mínima anterior | SDK 1.28.1 |
|---|---|
| `FastMCP(nombre)` | `FastMCP(nombre, instructions=…)` — el servidor anuncia su propósito en el handshake |
| `@mcp.tool()` a secas | `@mcp.tool(title=…, description=…, annotations=ToolAnnotations(...))` |
| (no existía) | `ToolAnnotations`: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` — pistas de comportamiento para el cliente |
| Parámetros solo tipados | `Annotated[tipo, Field(description=…)]` — el modelo ve para qué sirve cada argumento |
| Todo devolvía `str` | **Salida estructurada** con modelos Pydantic; el cliente recibe el `outputSchema` |
| `return "Error: ..."` | **Lanzar excepción** — MCP la transporta como error de herramienta |

🎯 **Por qué importa la salida estructurada:** con texto plano el modelo tenía que *inferir* los datos; con esquema los recibe como campos. Efecto medido en el Agente Ejecutor: pasó a reportar "58 caracteres" y "2 encontrados" leyendo `caracteres` y `total`.

🎯 **`destructiveHint=True`** (en `delete_file`) es la pista que permite exigir aprobación humana desde MFA con `approval_mode="always_require"`.

🎯 **`openWorldHint` contrasta los dos servidores**, y ese contraste es didáctico: `False` en el de archivos (opera sobre un espacio local y aislado) y `True` en el de clima (consulta Open-Meteo, puede fallar por red y su resultado cambia con el tiempo aunque los argumentos sean idénticos).

**A2A — subpaquete `agent-framework-a2a`, se importa como `agent_framework.a2a`:**

| Hoy en el código | MFA 1.11.0 |
|---|---|
| Dicts `{"sender","recipient","type","data"}` a mano | `A2AAgent` (cliente A2A sobre un `AgentCard`) |
| `coordinator._send_to_agent(...)` → llamada Python directa | `A2AExecutor` para usar un agente A2A como ejecutor dentro de un `Workflow` |
| `send_to_coordinator()` → dict fijo, no envía nada | `A2AAgentSession` / `A2AServiceSessionId` para hilo de conversación persistente |

**Heredadas de Part-1/2/3 (aplican al escenario 2 y a los agentes del escenario 1):**

| API vieja | MFA 1.11.0 |
|---|---|
| `ChatAgent` | `Agent` |
| `AzureAIAgentClient` | `FoundryChatClient` + `FoundryAgent` (`agent_framework.foundry`) |
| `AzureOpenAIChatClient` | `OpenAIChatClient` (`agent_framework.openai`), nativo-Azure vía `azure_endpoint` |
| `AIProjectClient.agents.create_agent(...)` | `Agent(client, instructions=…, name=…)` — agentes **efímeros**, no se crea nada en el servicio |
| `agent.run_stream(x)` | `agent.run(x, stream=True)` |
| Wrapper casero de aprobación humana | `@tool(approval_mode="always_require")` + `result.user_input_requests` + `req.to_function_approval_response(bool)` |

## Trampas de dependencias (críticas)

1. **NO instalar el meta-paquete `agent-framework`**: arrastra `agent-framework-azure-ai==1.0.0rc6`, incompatible con core 1.11.0. Instalar subpaquetes concretos y pinneados. (El venv de Part-1 sí lo tiene instalado por arrastre histórico; no lo tomes como modelo.)

2. 🚨 **`agent-framework-a2a==1.0.0b260212` está ROTO contra `a2a-sdk` 1.x.** Declara `a2a-sdk>=0.3.5` sin techo, pero la línea 1.0 eliminó `FilePart` / `FileWithBytes` / `FileWithUri` de `a2a.types`. Con el venv de Part-1, `import agent_framework.a2a` revienta con `ImportError: cannot import name 'FilePart'`. `a2a.compat.v0_3` **no** los reexpone.
   - **Solución:** usar `agent-framework-a2a==1.0.0b260721` o superior, que ya declara `a2a-sdk>=1.0.0,<2` y `agent-framework-core>=1.11.0,<2`. Verificar el import tras instalar.
   - A2A sigue **en beta** (`1.0.0bAAMMDD`), a diferencia del core, que es estable.

3. **`agent-framework-core` declara muy poco** (`opentelemetry-api`, `pydantic`, `python-dotenv`, `typing-extensions`). Todo lo demás hay que pinnearlo explícitamente aunque "funcione" en el venv.

4. Los `requirements.txt` actuales están inflados y desalineados: en el escenario 1 solo se usan `mcp`, `httpx`, `openai` y `python-dotenv` — `azure-ai-projects`, `azure-identity`, `aiohttp`, `pydantic` y `rich` no se importan en ninguna parte. Reescribirlos al migrar, con versiones pinneadas.

## Escenario 1 — ejecutar

```powershell
cd "scenario1_local_agents"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # el venv está vacío: obligatorio la primera vez
python run_scenario1.py
```

**Ejecutar desde `scenario1_local_agents/`**: `BASE_DIR = pathlib.Path("./agent_workspace")` es relativo al **cwd** y se crea al *importar* [file_operations_server.py](scenario1_local_agents/mcp_servers/file_operations_server.py). Desde otro directorio los ficheros acaban en otro sitio. `agent_workspace/` no está versionado; borrarlo reinicia el estado.

`run_scenario1.py` arranca **directamente en modo interactivo** (no hay menú). Comandos: `ciudades`, `demo` (3 ejemplos encadenados), `a2a` (explicación del protocolo), `a2a-directo` (mensajes A2A **sin Coordinador**, es decir sin LLM decidiendo), `arquitectura`, `ayuda`, `salir`.

**El orquestador gestiona el ciclo de vida MCP**: es un *async context manager* que abre las sesiones de los dos servidores una sola vez para toda la sesión y las cierra al salir. No arranques los servidores a mano.

### Trampas del escenario 1

- ✅ ~~Solo funcionan 6 ciudades australianas~~ — **resuelto** al migrar el Coordinador: los parámetros los extrae el LLM, ya no un diccionario fijo.
- ✅ ~~La geocodificación ignoraba el país~~ — **resuelto**: Open-Meteo **no acepta un parámetro `country`** y lo ignoraba en silencio, así que "Tokio, Japón" devolvía Tokio (Dakota del Norte). Ahora se piden 10 candidatos y se filtra en el cliente.
- ✅ ~~`handle_message` síncrono en Executor~~ — **resuelto**: los tres agentes exponen el mismo `handle_message` **asíncrono**. Ese contrato común es lo que los hace intercambiables como destinos A2A, y permitió retirar el `asyncio.iscoroutine()` del Coordinador.
- ✅ ~~`main()` de los agentes rotos~~ — **los tres corregidos** (faltaba `await` en el 1; `KeyError` por `results['count']` en el 3; el 2 construía el Coordinador sin referencias y todo salía simulado).
- ⚠️ **`send_to_coordinator` sigue simulado** en los agentes 1 y 3: la vuelta real ocurre hoy como valor de retorno de la herramienta del Coordinador, no como mensaje A2A.
- 🐞 **`Scenario1Orchestrator.demonstrate_agent_communication` es código muerto** — nunca se invoca; su "ping a todos los agentes" también fallaría por el `await` faltante sobre el Research Agent.
- ⚠️ El README menciona un `.env.template` que **no existe**.

## Escenario 2 — ejecutar

```powershell
cd "scenario2_azure_foundry"
az login
python interactive_maf_demo.py
```

Autentica con `DefaultAzureCredential` → **requiere `az login`**. Este escenario **sí llama a modelos de verdad**: consume cuota y no es determinista.

Variables de [.env](scenario2_azure_foundry/.env): `AZURE_AI_PROJECT_ENDPOINT` (o se compone desde `AZURE_AI_FOUNDRY_ENDPOINT` + `AZURE_AI_FOUNDRY_PROJECT`) y `AZURE_OPENAI_DEPLOYMENT_NAME`, que aquí nombra el **modelo de Foundry**, no un deployment de Azure OpenAI. La URL del MCP de Microsoft Learn (`https://learn.microsoft.com/api/mcp`) está **hardcodeada**, no se lee de `MCP_MS_LEARN_SERVER_URL`.

### Trampas del escenario 2

- 🚨 **Los agentes creados son persistentes y NUNCA se borran.** Cada ejecución crea `research-agent-interactive`, `executor-agent-interactive` y `coordinator-agent-interactive` en el proyecto de Foundry. No hay `cleanup`: **se acumulan**. Al migrar a `Agent(client, …)` pasan a ser efímeros y el problema desaparece.
- ⚠️ **La orquestación la hace el script, no el Coordinator.** Se crea el thread del coordinador y se lanza su run… pero `run_coord` **nunca se consulta** ([interactive_maf_demo.py:363](scenario2_azure_foundry/interactive_maf_demo.py#L363)): su respuesta se descarta. Los pasos 2–7 son threads separados que el Python encadena a mano. El "A2A" es la narración, no el mecanismo.
- ⚠️ **La aprobación de tools MCP se hace por REST crudo** (`submit_tool_approvals` → `POST .../submit_tool_outputs?api-version=v1` con `requests` y un token de `https://ai.azure.com/.default`), porque el SDK no la exponía. Por eso `requests` está en `requirements.txt`. Además, la extracción de `tool_calls` desde `required_action` prueba **tres métodos** en cascada, incluido `required_action._data` (atributo privado). Todo esto lo reemplaza el kwarg `approval_mode` de las tools MCP de MFA.
- ⚠️ Los `import` de `RequiredMcpToolCall` y `SubmitToolApprovalAction` están envueltos en `try/except` anidados y pueden acabar en `None`. No asumas que existen.
- El script detecta modo no interactivo con `sys.stdin.isatty()` y auto-avanza con `time.sleep(2)`; en Windows fuerza UTF-8 reenvolviendo `sys.stdout`. Escribe `agents_info_interactive.json` en el **cwd**.

## Configuración y credenciales

- `AZURE_OPENAI_ENDPOINT` debe ser **solo la base**, sin `/openai/...` — el framework agrega `/openai/v1/`. Si incluyes la ruta sale 404. Diagnóstico: imprime `client.base_url`.
- Usar `api_version="preview"`.
- En PowerShell, `load_dotenv(..., override=True)` para que el `.env` mande sobre variables `$env:` viejas de la sesión.

## Nota sobre secretos / env

**Los dos `.env` están versionados en git** y no hay `.gitignore` en el repositorio (mismo problema que en Part-1 y Part-3). Los valores de Azure son placeholders cortos, pero `RENDER_API_KEY` en `scenario2_azure_foundry/.env` tiene pinta de valor real. No añadas secretos nuevos a estos archivos, y ten en cuenta que cualquier edición aparecerá en `git status`.
