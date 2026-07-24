# Memory.md — Bitácora de A2A & MCP

Registro de evolución de este bloque. **La entrada más reciente va arriba.**

Formato de cada entrada:

```
## AAAA-MM-DD — <archivo/componente>
**Cambio:** qué se hizo.
**Motivo:** por qué (API eliminada, bug, dependencia, decisión de diseño).
**Notas:** trampas encontradas, qué queda por probar end-to-end, enlaces.
```

Se registra TODO: cambios de código, cambios de dependencias y decisiones relevantes.

---

## 2026-07-23 — `scenario2_azure_foundry_CSharp/`: réplica completa del escenario 2 en C# ✅

**Cambio:** proyecto **nuevo**: el escenario 2 reimplementado en C#/.NET 10, réplica fiel del `interactive_maf_demo.py` recién migrado — mismas 9 capas, mismos 7 pasos, mismos textos, mismos comentarios numerados y mismos principios SOLID.

**Estructura** (solución con **un** proyecto; aquí no hay servidores MCP propios, el MCP es remoto):
- `Scenario2.Host` — `Program.cs` (arranque + ficha JSON + cierre), `Configuracion.cs`, `Consola.cs`, `A2A/MensajeA2A.cs` (contrato + `IAgenteA2A`), `A2A/RedA2A.cs`, `Aprobacion/PoliticasDeAprobacion.cs`, `Agents/` (base + los tres agentes), `FabricaDeAgentes.cs` y `DemostracionA2A.cs`.

**Equivalencias de librerías** (buscadas en NuGet):

| Python | C# / .NET |
|---|---|
| `agent-framework-core` 1.12.1 | **`Microsoft.Agents.AI` 1.15.0** |
| `agent-framework-foundry` 1.10.3 | **`Microsoft.Agents.AI.Foundry` 1.5.0** |
| `mcp` 1.28.1 | **`ModelContextProtocol` 1.4.1** |
| `azure-identity` 1.25.3 | **`Azure.Identity` 1.21.0** |
| `python-dotenv` + `.env` | **`Microsoft.Extensions.Configuration`** + `appsettings.json` |
| `dataclass(frozen=True)` | `sealed record` |
| `Protocol` (typing) | `interface` |

**Equivalencias de API** (verificadas por reflexión sobre los ensamblados, no por documentación):

| Python | C# |
|---|---|
| `FoundryChatClient(project_endpoint=…, model=…, credential=…)` | `new AIProjectClient(new Uri(…), new DefaultAzureCredential())` |
| `Agent(cliente, name=…, instructions=…, tools=[…])` | `proyecto.AsAIAgent(model:…, name:…, instructions:…, tools:…)` — extensión de `Azure.AI.Projects`, devuelve `ChatClientAgent` **efímero** |
| `agente.create_session()` / `session=` | `await agente.CreateSessionAsync()` / `sesion` |
| `agente.run(x, stream=True)` | `agente.RunStreamingAsync(x, sesion)` |
| `MCPStreamableHTTPTool(name=…, url=…)` | `new HttpClientTransport(new HttpClientTransportOptions{…})` + `McpClient.CreateAsync` |
| `herramienta.functions` | `await cliente.ListToolsAsync()` |
| **`approval_mode="always_require"`** | **`new ApprovalRequiredAIFunction(herramienta)`** — envolver cada tool |
| `respuesta.user_input_requests` | `actualizacion.Contents.OfType<ToolApprovalRequestContent>()` |
| `solicitud.to_function_approval_response(bool)` | `solicitud.CreateResponse(bool)` |
| `not sys.stdin.isatty()` | `Console.IsInputRedirected` |
| `sys.stdout.reconfigure(encoding="utf-8")` | `Console.OutputEncoding = Encoding.UTF8` |

**Mejora que aporta C#:** igual que en el escenario 1, el contrato A2A pasa de convención a **interfaz `IAgenteA2A`** (el compilador exige `AtenderAsync`, `TiposAdmitidos`, `Ficha`), y los mensajes dejan de ser diccionarios sueltos para ser los `record` inmutables `MensajeA2A` / `RespuestaA2A`. La política de aprobación es `IPoliticaDeAprobacion`, no un *Protocol* implícito.

**Notas y hallazgos:**
- 🔑 **El equivalente de `FoundryChatClient` en .NET no es una clase, es una extensión**: `AzureAIProjectChatClientExtensions.AsAIAgent(...)`, que llega en `Microsoft.Agents.AI.Foundry` pero se importa desde el namespace `Azure.AI.Projects`. Hay dos familias de sobrecargas: las que reciben `AgentReference`/`ProjectsAgentRecord` devuelven `FoundryAgent` (**persistente**, registrado en el servicio) y la que recibe `model` + `instructions` devuelve `ChatClientAgent` (**efímero**). Se usa la segunda: es la que replica el comportamiento del Python migrado.
- ⚠️ **Versiones desalineadas a propósito**: `Microsoft.Agents.AI` va por 1.15.0 pero `Microsoft.Agents.AI.Foundry` estable va por **1.5.0** (su rama 1.15 solo existe como *preview* y arrastra `Azure.AI.Projects` beta). Se eligió la combinación **todo estable**; NuGet resuelve sin conflicto porque Foundry pide `Microsoft.Agents.AI >= 1.5.0`.
- 🐞 **Trampa NU1605**: fijar `Azure.Identity` 1.17.1 rompe la compilación — `Microsoft.Agents.AI.Foundry` exige **>= 1.21.0** y NuGet trata la degradación como error. Subido a 1.21.0.
- 🐞 **`ListToolsAsync()` devuelve `IList<McpClientTool>`**, no `IReadOnlyList`; hace falta `[.. herramientas]` para adaptarlo.
- 🐞 **`File.WriteAllText(..., Encoding.UTF8)` escribe BOM.** El JSON salía con un carácter invisible al principio. Corregido con `new UTF8Encoding(false)`. Además se aplicó `JsonNamingPolicy.SnakeCaseLower` para que la ficha salga con las mismas claves que la de Python (`nombre`, `tipos_admitidos`…).
- 🔧 La ficha `agents_info_interactive.json` se ancla a la **raíz de la solución** (buscando `*.sln`/`*.slnx` hacia arriba), no a `bin/Debug/net10.0`.
- 🔑 **`appsettings.json` usa las MISMAS claves que el `.env` de Python** (`AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_FOUNDRY_ENDPOINT`, `AZURE_AI_FOUNDRY_PROJECT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `MCP_MS_LEARN_SERVER_URL`), a petición del usuario. Se versiona con placeholders `<…>`; los valores reales van en `appsettings.Development.json` (en `.gitignore`) o en variables de entorno, que mandan.
- 🎯 **Pequeña mejora sobre Python**: la URL del MCP se lee de `MCP_MS_LEARN_SERVER_URL` (con la constante como valor por defecto); en Python sigue siendo una constante del módulo.

**Pruebas realizadas (contra Azure real, modelo `gpt-5.4-mini`):**
- ✅ `dotnet build`: **0 errores, 0 advertencias**.
- ✅ **Flujo completo end-to-end cuatro veces**: **7/7 pasos**, con datos reales y enlaces a Microsoft Learn.
- ✅ **Descubrimiento MCP por protocolo**: las 3 herramientas de Microsoft Learn (`microsoft_docs_search`, `microsoft_code_sample_search`, `microsoft_docs_fetch`).
- ✅ **Aprobación de herramientas**: hasta 4 llamadas interceptadas en una ejecución, autorizadas y ejecutadas después. Verificado también el **camino interactivo** (la caja `┌─┐` y el prompt `[S/n]`) instanciando `AprobacionInteractiva` desde un proyecto de prueba.
- ✅ **Streaming + aprobación en el mismo bucle**: confirmado que las solicitudes llegan como un contenido más dentro del flujo de `RunStreamingAsync`.
- ✅ **Fallo por configuración incompleta**: quitando `appsettings.Development.json` sale el mensaje guiado en vez de una excepción críptica.
- ✅ **Verificado que NO se crean agentes persistentes**: el proyecto de Foundry sigue con los 7 agentes preexistentes tras todas las ejecuciones.

**README.md** propio con la misma estructura y nivel de detalle que el de Python (portada con diagrama, "lo elemental en 60 segundos", comparativa escenario 1 vs 2, arquitectura, puesta en marcha, anatomía de una ejecución, aplicabilidad real, las 9 capas + tabla SOLID, problemas comunes, glosario, tecnologías y 6 ejercicios), **más una tabla de equivalencias Python ↔ C#** de librerías y de API. Autoría: Fernando Valdés H.

---

## 2026-07-23 — `scenario2_azure_foundry/interactive_maf_demo.py` migrado a MFA ✅ — 🎉 ESCENARIO 2 COMPLETO

**Cambio:** reescritura completa del único componente del escenario 2. De SDK crudo de Azure (`azure.ai.projects` / `azure.ai.agents`) a **Microsoft Agent Framework**, en español, con arquitectura en 9 capas y comentarios numerados por flujo de ejecución.

**Equivalencias aplicadas:**

| Antes | Ahora |
|---|---|
| `AIProjectClient(...)` + `agents_client.create_agent(...)` | `FoundryChatClient(project_endpoint, model, credential)` + `Agent(cliente, name, instructions, tools)` |
| Agentes **persistentes** creados en cada ejecución | Agentes **efímeros**: no se registra nada en Foundry |
| `threads.create()` / `messages.create()` / `runs.create()` / bucle de *polling* con `time.sleep(2)` | `agente.create_session()` + `await agente.run(..., stream=True, session=…)` |
| Herramienta MCP como **diccionario suelto** `{"type": "mcp", "server_url": …}` | `MCPStreamableHTTPTool(name=…, url=…)` — del **core** de MFA |
| `submit_tool_approvals()`: `POST …/submit_tool_outputs?api-version=v1` con `requests` y token de `https://ai.azure.com/.default` obtenido a mano | kwarg **`approval_mode="always_require"`** + `respuesta.user_input_requests` + `solicitud.to_function_approval_response(bool)` |
| Extracción de `tool_calls` probando **tres métodos** en cascada, incluido `required_action._data` (atributo privado) | Ya no existe: lo resuelve el framework |
| `import` de `RequiredMcpToolCall` / `SubmitToolApprovalAction` en `try/except` anidados que podían acabar en `None` | Eliminados |
| `io.TextIOWrapper(sys.stdout.buffer, …)` | `sys.stdout.reconfigure(encoding="utf-8")` (igual que el escenario 1) |
| `DefaultAzureCredential` síncrona | `azure.identity.aio.DefaultAzureCredential` dentro de `async with` |

**Arquitectura nueva (SOLID), a petición del usuario** — 9 capas, cada una con una responsabilidad:
`Configuracion` (SRP: única lectura del `.env`, validación temprana) · `Consola` (SRP+DIP: **nadie más llama a `print()`**; los agentes reciben la consola) · `MensajeA2A`/`RespuestaA2A`/`TipoMensaje` (contrato inmutable, en vez de diccionarios sueltos) · `PoliticaDeAprobacion` + `AprobacionInteractiva`/`AprobacionAutomatica` (OCP+DIP: la decisión de autorizar es una pieza intercambiable) · `AgenteA2A` base abstracta con *método plantilla* `atender()` + `_conversar()` y tres agentes concretos (LSP: intercambiables como destinos A2A; ISP: cada uno publica `tipos_admitidos` y rechaza el resto con error explícito) · `RedA2A` (OCP: registrar un cuarto agente es **una línea**) · `FabricaDeAgentes` · `DemostracionA2A` (el guion de los 7 pasos) · `main()`.

**Esencia preservada** (petición explícita del usuario): las dos fases, los 7 pasos narrados, las cajas `▔▔▔` de mensaje A2A, las pausas con Enter, el modo automático sin TTY y el archivo `agents_info_interactive.json`.

**Motivo:** el escenario 2 era el último componente sin migrar del bloque.

**🐞 Bugs corregidos por el camino:**
- **`run_coord` ya no se descarta.** Antes se creaba el thread del Coordinador, se lanzaba su run y **nunca se consultaba** (línea 363 del original): su respuesta se tiraba. Ahora el Coordinador interviene de verdad dos veces — al principio redacta el **encargo** que se envía al Agente de Investigación (y ese texto **se usa**), y al final redacta la respuesta para el usuario.
- **`agents_info_interactive.json` se escribía en el cwd**; ahora se ancla a `Path(__file__).resolve().parent`.
- **`load_dotenv()` dependía del cwd**; ahora ruta absoluta con `override=True`.
- **Configuración validada al arrancar**: antes, con el `.env` incompleto, `PROJECT_ENDPOINT` quedaba en `None` y el fallo aparecía mucho más tarde y sin explicación.
- **Cierre garantizado** de la sesión MCP en un `finally`.

**Notas y hallazgos:**
- 🚨 **Cambio de API en core 1.12.1**: `agent.get_new_thread()` **ya no existe**; ahora es `agent.create_session()` y el kwarg pasa de `thread=` a `session=`. Descubierto por `AttributeError` en la prueba de humo.
- ⚙️ **Patrón de aprobación verificado**: `flujo = agente.run(x, stream=True, session=s)` → `async for` sobre el flujo → `await flujo.get_final_response()` → si `user_input_requests` no está vacío, se vuelve a llamar a `run()` pasándole la lista de `to_function_approval_response(bool)`. Se hace en bucle acotado (`MAXIMO_RONDAS = 6`).
- 🔌 **El MCP de Microsoft Learn publica 3 herramientas**, no 2 como decían las instrucciones del agente original: `microsoft_docs_search`, `microsoft_code_sample_search` y `microsoft_docs_fetch`. Ahora se listan por descubrimiento (`.functions`), no a mano.
- ✅ **Verificado que NO se crean agentes persistentes**: listados los agentes del proyecto tras varias ejecuciones → los 7 que ya había (`PruebaIndex`, `DemoAssistant`, `fnd2016-agent`, `analista-antecedentes-tecnicos`, `aiep-rag-knowledge-workflow`, `seguridad-y-Cumplimiento`, `soluciones-troubleshooting`), ninguno de la demo. **La acumulación de agentes queda resuelta.**
- ⚠️ **Decisión de diseño:** la coreografía de los 7 pasos la sigue marcando el guion (`DemostracionA2A`), no el modelo. Es deliberado y está documentado: el escenario 1 ya enseña la versión donde el modelo decide con *function tools*; aquí el objetivo es ver **la mecánica paso a paso**. El README compara ambos enfoques.
- ⚠️ `azure-ai-projects` subió a **2.3.0** y reorganizó la API: `client.agents.list_agents()` ya no existe, ahora es `client.agents.list()`. Solo afecta a scripts de inspección, no a la demo (que no usa ese SDK).

**Dependencias:** venv del escenario creado e instalado desde cero (estaba vacío, solo `pip`). [requirements.txt](scenario2_azure_foundry/requirements.txt) reescrito y pinneado: `agent-framework-core` **1.12.1** (una versión por delante del escenario 1), `agent-framework-foundry` **1.10.3**, `mcp` **1.28.1**, `azure-identity` **1.25.3**, `python-dotenv` **1.2.2**. Por arrastre: `agent-framework-openai` 1.11.0, `azure-ai-projects` 2.3.0, `openai` 2.48.0, `pydantic` 2.13.4, `httpx` 0.28.1. **Eliminadas** `azure-ai-agents` y `requests` (esta última solo existía para la aprobación por REST). Instalación limpia, sin conflictos.

**Pruebas realizadas (contra Azure real, modelo `gpt-5.4-mini`):**
- ✅ **Flujo completo end-to-end tres veces.** Pregunta por defecto (*"¿Qué niveles de servicio admiten servidores MCP en Azure API Management?"*) → **7/7 pasos**, con datos reales y enlaces a Microsoft Learn.
- ✅ **Descubrimiento MCP por protocolo**: las 3 herramientas del servidor de Microsoft Learn.
- ✅ **Aprobación de herramientas**: 4 llamadas interceptadas en una ejecución (3 × `microsoft_docs_search` + 1 × `microsoft_docs_fetch`), todas autorizadas y ejecutadas después.
- ✅ **Ruta de aprobación interactiva** probada por separado (la caja `┌─┐` y el prompt `[S/n]`).
- ✅ **Modo automático sin TTY**: la demo avanza sola y aprueba automáticamente, dejando constancia en pantalla.
- ✅ **Ficha JSON** generada en el directorio del script, con los tres agentes marcados como efímeros.

**Documentación:** [README.md](scenario2_azure_foundry/README.md) nuevo (no existía), con la misma estructura que el del escenario 1: portada con diagrama, "lo elemental en 60 segundos", **tabla comparativa escenario 1 vs escenario 2**, arquitectura, puesta en marcha, anatomía de una ejecución, aplicabilidad real, **las 9 capas + tabla de dónde está cada principio SOLID**, problemas comunes, glosario, tecnologías y 6 ejercicios propuestos. Autoría: Fernando Valdés H.

**Pendiente:** el usuario creó [.gitignore](scenario2_azure_foundry/.gitignore) y [.env.example](scenario2_azure_foundry/.env.example) durante la sesión (se les añadieron `.venv/` y el JSON generado). ⚠️ **El `.env` sigue estando TRACKEADO en git**: `.gitignore` no destraquea lo ya versionado, hace falta `git rm --cached scenario2_azure_foundry/.env`. Las claves que contiene (Foundry y Render) han estado en el historial del repositorio.

---

## 2026-07-23 — `scenario1_local_agents_CSharp/`: réplica completa del escenario 1 en C# ✅

**Cambio:** proyecto **nuevo** (no una migración): todo el escenario 1 reimplementado en C#/.NET 10, con la misma arquitectura, los mismos conceptos y el mismo estilo didáctico que el gemelo en Python.

**Estructura** (solución con 3 proyectos):
- `Scenario1.Host` — programa principal: `Program.cs` (UI interactiva), `Orquestador.cs`, `Configuracion.cs`, `A2A/MensajeA2A.cs` y los tres agentes en `Agents/`.
- `McpServers/Scenario1.WeatherServer` — servidor MCP de clima (3 herramientas).
- `McpServers/Scenario1.FileOperationsServer` — servidor MCP de archivos (5 herramientas).

**Equivalencias de librerías** (buscadas en NuGet):

| Python | C# / .NET |
|---|---|
| `agent-framework-core` 1.12.0 | **`Microsoft.Agents.AI` 1.15.0** |
| `agent-framework-openai` 1.10.2 | **`Microsoft.Agents.AI.OpenAI` 1.15.0** + `Azure.AI.OpenAI` 2.1.0 |
| `mcp` 1.28.1 | **`ModelContextProtocol` 1.4.1** |
| `python-dotenv` + `.env` | **`Microsoft.Extensions.Configuration`** + `appsettings.json` |
| `httpx` | `HttpClient` (BCL) |
| `pydantic.BaseModel` | `record` + `[Description]` |
| `rich` | No hace falta: `Console` con UTF-8 |

**Equivalencias de API:** `OpenAIChatClient(...)` → `new AzureOpenAIClient(...).GetChatClient(...)`; `Agent(client, instructions, tools=[...])` → `chatClient.AsAIAgent(instructions, name, tools: [...])`; `agent.run(x, stream=True)` → `agent.RunStreamingAsync(x)`; `MCPStdioTool` → `StdioClientTransport` + `McpClient.CreateAsync`; `tool.functions` → `cliente.ListToolsAsync()`; `@mcp.tool(annotations=ToolAnnotations(...))` → `[McpServerTool(ReadOnly=…, Destructive=…, Idempotent=…, OpenWorld=…, UseStructuredContent=true)]`; `FastMCP(instructions=…)` → `AddMcpServer(o => o.ServerInstructions = …)`; `mcp.run(transport="stdio")` → `.WithStdioServerTransport()`.

**Mejora que aporta C#:** el contrato A2A pasa de convención a **interfaz `IAgenteA2A`**. En Python todos los agentes *tenían* un `handle_message` por acuerdo; aquí el compilador lo exige. Los mensajes dejan de ser diccionarios sueltos y son los records `MensajeA2A` / `RespuestaA2A`.

**Notas y hallazgos:**
- ⚠️ **No existe `Microsoft.Agents.AI.A2A` en NuGet.** El paquete `agent-framework-a2a` (beta) de Python no tiene equivalente publicado en .NET. No afecta: igual que en Python, la delegación se implementa con herramientas sobre un contrato de mensajes propio.
- 🐞 **Trampa .NET 10:** `dotnet new sln` genera el formato nuevo **`.slnx`**, no `.sln`. La detección de la raíz de la solución fallaba al buscar solo `*.sln`; ahora busca ambos. Afectaba a `Configuracion.ResolverRaiz()` y a `Workspace.ResolverEspacioDeTrabajo()`.
- 🔌 **Los servidores MCP son proyectos ejecutables aparte.** El Host los referencia con `ReferenceOutputAssembly="false"`: se compilan antes que él pero **no** se enlazan sus tipos, porque se lanzan como procesos.
- 🚨 **Misma trampa de stdout que en Python**, resuelta a la manera de .NET: `builder.Logging.AddConsole(o => o.LogToStandardErrorThreshold = LogLevel.Trace)` y `Console.Error.WriteLine` para los mensajes de arranque.
- 🔒 El guardián anti-escape usa comparación con separador de ruta final en vez de `StartsWith` a secas, para evitar el fallo del directorio hermano `agent_workspace_evil`.
- 🔑 **Credenciales:** `appsettings.json` se versiona con valores de EJEMPLO; las claves reales van en `appsettings.Development.json` (en `.gitignore`) o en variables de entorno, que tienen prioridad. Se añadió `.gitignore` (que el proyecto Python **no** tiene).

**Pruebas realizadas:**
- ✅ `dotnet build` de la solución completa: **0 errores, 0 advertencias**.
- ✅ Arranque y **descubrimiento MCP por protocolo**: 3 herramientas del servidor de clima y 5 del de archivos.
- ✅ **Flujo multiagente completo contra Azure real**: *"¿Qué tiempo hace en Valparaíso, Chile? Guárdalo en informe_valpo.txt"* → **2/2 pasos**, archivo generado con datos reales (15,1 °C, llovizna ligera).
- ✅ **`a2a-directo`**: las tres demos y el ping a los tres agentes.
- ✅ **Las 5 operaciones de archivo** en ciclo completo (escribir → leer → info → listar → borrar).
- ✅ **Seguridad**: bloqueados `../../secreto.txt` y `../agent_workspace_evil/x.txt`.
- ✅ **Errores**: archivo inexistente lanza `FileNotFoundException`.

**README.md** propio, con la misma estructura que el de Python (progresión por niveles, aplicabilidad real, glosario, ejercicios), más una **tabla de equivalencias Python ↔ C#** para quien venga del otro proyecto. Autoría: Fernando Valdés H.

---

## 2026-07-22 — `run_scenario1.py` migrado ✅ — 🎉🎉 ESCENARIO 1 COMPLETO AL 100 %

**Cambio:** migrado el orquestador y la interfaz interactiva, último componente del escenario.

- **Traducción total al español** de las cinco pantallas (bienvenida, ayuda, ciudades, protocolo A2A, arquitectura) y de todos los mensajes.
- **Gestión del CICLO DE VIDA MCP**: el orquestador es ahora un *async context manager* (`__aenter__`/`__aexit__`) que abre las sesiones MCP de los agentes **una sola vez para toda la sesión interactiva** y las cierra al salir, incluso con Ctrl+C. Antes no existía ese ciclo de vida porque no había MCP real.
- 🐞 **`demonstrate_agent_communication` resucitado**: existía pero **nunca se invocaba** (código muerto) y además estaba roto — hacía el `ping` **sin `await`** sobre métodos asíncronos. Ahora es `demostrar_comunicacion_a2a()`, funciona y está accesible con el comando **`a2a-directo`**. Es didácticamente valioso: envía mensajes A2A **sin pasar por el Coordinador**, es decir, sin ningún LLM decidiendo por el camino.
- **`_verificar_configuracion`**: mismas variables, pero ahora son **realmente obligatorias**. Antes el cliente de Azure OpenAI se creaba y nunca se usaba, así que el escenario corría sin credenciales válidas.
- **Presentación de resultados** adaptada al contrato del Coordinador migrado: detalla qué agente atendió cada paso delegado, en vez de hurgar en claves como `weather_data` / `raw_data`.
- ⚠️ **Diagrama de arquitectura corregido**: el anterior dibujaba los servidores MCP escuchando en los **puertos 8001 y 8002**. Era falso — el transporte es stdio y no abre ningún puerto. Ahora se dibujan como **subprocesos** de cada agente, con el flujo real Usuario → Coordinador → (A2A) → Investigación/Ejecutor → (MCP stdio) → servidores.
- **Ciudades de ejemplo ampliadas al mundo entero** (con Sudamérica primero), ahora que el Coordinador ya no está limitado a 6 ciudades australianas.
- **Comandos nuevos**: `a2a-directo` y `arquitectura`; `salir` además de `quit`/`exit`/`q`; `ayuda` además de `help`.
- Documentación con numeración por flujo `[0]…[11]` y marcas `⚙️ MFA` / `📡 A2A` / `🔌 MCP` / `🔧 Infra`.

**Motivo:** cerrar el escenario 1 con la interfaz alineada a lo que el código hace de verdad.

**Notas:**
- ✅ **Probado el arranque completo**: los dos servidores MCP se lanzan como subprocesos y se descubren sus 3 + 5 herramientas por protocolo.
- ✅ **Probados los comandos de interfaz** (`arquitectura`, `ciudades`, `ayuda`, `a2a`, `salir`) sin consumir tokens.
- ✅ **Probado el flujo completo** contra Azure real: *"¿Qué tiempo hace en Valparaíso, Chile? Guárdalo en informe_valpo.txt"* → **2/2 pasos**, con el detalle por agente.
- ✅ **Probado `a2a-directo`**: las tres demos (investigación directa, ejecución encadenada y ping a los tres agentes) responden correctamente. Genera `demo_a2a.txt`.
- ✅ **Probado el cierre limpio** de las sesiones MCP al salir.

**🎉 ESCENARIO 1 TERMINADO.** Los 6 componentes migrados y probados end-to-end. Siguiente fase: `scenario2_azure_foundry/interactive_maf_demo.py`.

---

## 2026-07-22 — `mcp_servers/weather_server.py` modernizado al SDK MCP 1.28.1 ✅ — 🎉 ESCENARIO 1 COMPLETO

**Cambio:** migración completa del último componente del escenario 1 (antes solo se habían corregido `main()` y `geocode_city()`).

- **Traducción total al español**: títulos, descripciones, docstrings y campos. Los **nombres de las herramientas se mantienen** (`get_weather`, `get_forecast`, `get_alerts`): son identificadores de protocolo y el Agente de Investigación los referencia en sus `instructions`.
- **`FastMCP(nombre, instructions=…)`**: anuncia que acepta nombres de ciudad en español o inglés y que indicar el país mejora la precisión.
- **`annotations=ToolAnnotations(...)`** en las tres: `readOnlyHint=True`, `idempotentHint=True` y ⚠️ **`openWorldHint=True`** — al revés que el servidor de archivos. Contraste didáctico: estas herramientas consultan un sistema **externo** (Open-Meteo), pueden fallar por red y su resultado cambia con el tiempo aunque los argumentos sean idénticos.
- **Salida estructurada** con cinco modelos Pydantic: `ClimaActual`, `Pronostico` (+ `DiaPronostico`) y `AvisosMeteorologicos`. Antes las tres devolvían **texto con emojis embebidos**, que el agente tenía que interpretar.
- **`Annotated[..., Field(description=…)]`** en todos los parámetros, con validación de rango (`ge=1, le=16`) en `days`.
- **Errores como excepciones**: `LookupError` si no se encuentra la ciudad, `ConnectionError` si falla la API, `ValueError` si la respuesta viene incompleta. Antes `make_api_request` devolvía `None` y cada herramienta lo traducía a un texto de error indistinguible de un resultado válido.
- 🐞 **Unificados los DOS diccionarios de códigos WMO** (uno con emojis para el clima actual, otro sin ellos para el pronóstico) en un único `CODIGOS_TIEMPO` en español. Estaban duplicados y podían desincronizarse.
- **Umbrales de aviso como constantes con nombre** (`UMBRAL_RACHAS_FUERTES_KMH`, `UMBRAL_VIENTO_FUERTE_KMH`, `UMBRAL_LLUVIA_INTENSA_MM`); antes eran números sueltos dentro de la función.
- **`hay_avisos` viaja explícito** en la respuesta: el agente ya no tiene que deducir la ausencia de avisos de una frase como *"No active weather warnings"*.
- Documentación con numeración por flujo `[1]…[9]` y marcas `🔌 MCP` / `🌍 API` / `🔧 Infra`.

**Motivo:** cerrar la fase MCP dejando los dos servidores al día con el SDK 1.28.1 y con la misma estructura didáctica.

**Notas:**
- ✅ **Verificado por protocolo** (`list_tools()`): las 3 herramientas publican `title`, anotaciones y `outputSchema`.
- ✅ **Probadas las 3 herramientas** contra la API real: clima de Tokio pidiéndolo en español, pronóstico de 3 días de Santiago, avisos de Melbourne.
- ✅ **Casos límite**: ciudad inexistente → `LookupError`; `days=99` → se ajusta a 16.
- ✅ **Probado end-to-end con el Agente de Investigación** contra Azure real.
- ✅ **Regresión de la cadena completa**: los 3 agentes + los 2 servidores MCP. **2/2 pasos**, `informe_tokio.txt` regenerado con datos reales (34,6 °C).

**Dependencias:** sin cambios; todas ya estaban en su última versión (ver entrada anterior).

**🎉 Escenario 1 terminado salvo `run_scenario1.py`** (orquestador + interfaz interactiva), único componente que sigue pendiente.

---

## 2026-07-22 — `mcp_servers/file_operations_server.py` modernizado al SDK MCP 1.28.1 ✅

**Cambio:** migración completa del servidor (la anterior fue solo el arreglo de arranque y bugs). Empieza la fase MCP.

- **Traducción total al español**: títulos, descripciones, docstrings, mensajes y nombres de campos. Los **nombres de las herramientas se mantienen en inglés** (`read_file`, `write_file`, `list_files`, `delete_file`, `file_info`) porque son identificadores de protocolo y el Agente Ejecutor los referencia en sus `instructions`.
- **`FastMCP(nombre)` → `FastMCP(nombre, instructions=…)`**: el servidor ahora anuncia en el handshake para qué sirve en conjunto, no solo herramienta por herramienta.
- **`@mcp.tool()` a secas → `title` + `description` + `annotations=ToolAnnotations(...)`**. Las anotaciones son pistas de comportamiento para el cliente:
  - `read_file`, `list_files`, `file_info` → `readOnlyHint=True`, `idempotentHint=True`
  - `write_file` → `readOnlyHint=False`, `destructiveHint=False`
  - `delete_file` → **`destructiveHint=True`** ← es la pista que permitiría exigir aprobación humana desde MFA (`approval_mode="always_require"`)
- **Parámetros sin describir → `Annotated[..., Field(description=…)]`**: ahora el modelo ve para qué sirve cada argumento, no solo su tipo.
- **Todo devolvía `str` → salida estructurada con modelos Pydantic**: `ResultadoOperacion`, `ListadoArchivos` (+ `ArchivoListado`) e `InfoArchivo`. El cliente recibe el JSON Schema junto con la herramienta.
- **Errores como texto → excepciones** (`FileNotFoundError`, `ValueError`), que MCP transporta como error de herramienta. Antes se devolvía `"Error: ..."` como si fuera contenido válido, así que el modelo no podía distinguir un fallo de un archivo cuyo contenido empezara por "Error:".
- Documentación con numeración por flujo `[1]…[10]` y marcas `🔌 MCP` / `🔒 Seg.` / `🔧 Infra`.

**Motivo:** el servidor usaba la API mínima de FastMCP. El SDK 1.28.1 ofrece metadatos que el agente aprovecha de verdad, y la salida estructurada elimina el *parsing* de texto.

**Notas:**
- ✅ **Verificado por protocolo** (`list_tools()`): las 5 herramientas publican `title`, anotaciones y `outputSchema` correctos.
- ✅ **Probado end-to-end con el Agente Ejecutor** contra Azure real. Efecto visible de la salida estructurada: el modelo ahora dice *"58 caracteres guardados"* y *"2 encontrados"* — datos que antes tenía que **inferir del texto** y ahora recibe como campos (`caracteres`, `total`).
- ✅ **Probadas las 5 operaciones** en ciclo completo (escribir → leer → info → listar → borrar) y los casos de error.
- ✅ **Probada la seguridad**: `../../.env` y `../agent_workspace_evil/x.txt` quedan bloqueados. El segundo es justamente el caso que el antiguo `str.startswith()` dejaba pasar.
- 📌 `total` viaja ahora explícito en `ListadoArchivos`. Es el dato que el `main()` viejo de `agent3_executor.py` intentaba leer como `results['count']` y que **nunca existió**.

**Dependencias:** revisadas todas contra PyPI — `mcp` 1.28.1, `agent-framework-core` 1.12.0, `agent-framework-openai` 1.10.2, `a2a-sdk` 1.1.2, `httpx` 0.28.1, `rich` 15.0.0, `python-dotenv` 1.2.2, `openai` 2.47.0, `pydantic` 2.13.4. **Todas están en la última versión publicada**: no hubo nada que actualizar ni que tocar en `requirements.txt`.

---

## 2026-07-22 — `mcp_servers/file_operations_server.py`: preparado para stdio + 2 bugs 🐞

**Cambio:** tres correcciones, análogas a las del servidor de clima:

1. **`main()`**: los `print()` informativos pasan a **stderr**, se fuerza UTF-8 y se baja el logging a `WARNING`.
2. **`BASE_DIR`**: era `pathlib.Path("./agent_workspace")`, **relativo al directorio de trabajo**. Al lanzarse como subproceso MCP, el espacio de trabajo cambiaba según desde dónde se ejecutara. Ahora se ancla con `Path(__file__).resolve().parent.parent / "agent_workspace"`.
3. **`get_safe_path()`**: la comprobación anti-escape usaba `str(resolved).startswith(str(BASE_DIR))`, que es **comparación de texto, no de rutas**: un directorio hermano llamado `agent_workspace_evil` pasaba el filtro. Sustituido por `Path.is_relative_to()`, que compara por componentes.

**Motivo:** (1) es prerrequisito para que el Agente Ejecutor hable MCP por stdio; (2) y (3) son bugs reales encontrados al revisar el archivo para la migración.

**Notas:** las cinco herramientas y sus textos **siguen en inglés**, pendientes de la migración formal de este componente. ✅ Verificado que `BASE_DIR` resuelve al directorio del escenario.

---

## 2026-07-22 — `agents/agent3_executor.py` migrado a MFA + MCP real ✅

**Cambio:** el Agente Ejecutor pasa de simulación a MFA real, con el mismo patrón que `agent1_research.py`:

- `openai.AzureOpenAI` (creado y **nunca usado**) → `OpenAIChatClient` + `Agent`. **Ahora sí se invoca al LLM.**
- `from mcp_servers.file_operations_server import write_file, read_file, ...` (import de Python directo) → `MCPStdioTool(name="servidor_archivos", command=sys.executable, args=[...])`. **Protocolo MCP real**: las cinco tools (`read_file`, `write_file`, `list_files`, `delete_file`, `file_info`) se descubren por protocolo.
- `_execute_operation()` con un `if/elif` de **cinco ramas** que llamaba la función Python correspondiente → traduce la operación A2A a una **instrucción en lenguaje natural** y deja que el modelo elija la tool MCP.
- **`handle_message` pasa de SÍNCRONO a asíncrono**, unificando el contrato de los tres agentes.
- Salida en streaming con `agent.run(instruccion, stream=True)`.
- Ciclo de vida MCP: `connect()` perezoso + `close()`, y soporte de `async with ExecutorAgent()`.
- Documentación con numeración por flujo `[0]…[12]` y marcas `⚙️ MFA` / `🔌 MCP` / `📡 A2A` / `🔧 Infra`.
- 🐞 Arreglado el `main()`: el ejemplo 2 leía `response['results']['count']`, **una clave que la operación nunca devolvía** → `KeyError` garantizado.

**Motivo:** completar el escenario 1 con los tres agentes hablando MCP y A2A de verdad.

**Notas:**
- ✅ **Probado end-to-end contra Azure real**: escritura de `informe_clima.txt` y listado con patrón `*.txt` (encontró los dos archivos del espacio de trabajo). Todo en español.
- ✅ **Prueba de regresión de la cadena completa** (`agent2_coordinator.py` con los dos agentes migrados): Coordinador → Investigación → MCP clima → Coordinador → Ejecutor → MCP archivos. **2/2 pasos**, `agent_workspace/informe_tokio.txt` regenerado (698 bytes, 34,5 °C de Tokio).
- 🎉 **Retirado el apaño de compatibilidad** en `_delegar_por_a2a` del Coordinador: ya no hace falta `asyncio.iscoroutine()`, porque **los tres agentes exponen el mismo `handle_message` asíncrono**. Ese contrato común es lo que los hace intercambiables como destinos A2A.
- El `main()` del Coordinador ahora abre ambos agentes con `async with ResearchAgent() as …, ExecutorAgent() as …`, de modo que cada uno gestiona su propia sesión MCP.
- ⚠️ `send_to_coordinator` sigue **simulado** en los agentes 1 y 3: la vuelta real ocurre hoy como valor de retorno de la herramienta del Coordinador, no como mensaje A2A.

---

## 2026-07-22 — `mcp_servers/weather_server.py`: corregida la geocodificación 🐞

**Cambio:** reescrita `geocode_city()`. Antes: `count=1`, `language="en"` y `params["country"] = country`. Ahora: `count=10`, `language="es"` y **filtrado del país en el cliente** (acepta el nombre "Japón" o el código ISO "JP", sin distinguir mayúsculas); si ningún candidato coincide, se conserva el mejor resultado global en vez de fallar.

**Motivo:** 🚨 **la API de geocodificación de Open-Meteo NO acepta un parámetro `country`: lo ignora en silencio.** El código creía estar filtrando y no lo hacía. Con `count=1` + `language="en"`, la petición "Tokio, Japón" devolvía **Tokio, Dakota del Norte (EE. UU.)**. El bug lo destapó el propio modelo durante la prueba del Coordinador, que avisó de que los datos no correspondían a Japón.

**Notas:**
- `language="es"` permite además buscar por el nombre en español ("Tokio", "Londres") y devuelve los países en español, coherente con el idioma del bloque.
- ✅ Verificado: `Tokio/Japón` → *Tokio, Tokio, Japón*; `Tokyo/Japan` → *Tokio, Tokio, Japón*; `Santiago/Chile` → *Santiago de Chile*; `Londres/Reino Unido` → *Londres, Inglaterra*; `Melbourne/Australia` → *Melbourne, Victoria*.
- Segundo cambio en este archivo fuera de turno (el primero fue el `main()`); sus herramientas y textos **siguen en inglés**, pendientes de su migración formal.

---

## 2026-07-22 — `agents/agent2_coordinator.py` migrado a MFA + delegación A2A real ✅

**Cambio:** el Coordinador pasa de simulación a orquestación real con MFA:

- `openai.AzureOpenAI` (creado y **nunca usado**) → `OpenAIChatClient` + `Agent`.
- `_plan_workflow()` (planificación por **palabras clave**: buscaba "weather", "save"…) → **la planificación la hace el LLM**. Método eliminado.
- `_extract_weather_params()` (diccionario fijo de **6 ciudades australianas**, con *default* Melbourne) → **la extracción la hace el LLM**. Método eliminado.
- `_send_to_agent()` con `if/elif` que llamaba métodos Python → **dos function tools** (`investigar_clima`, `guardar_en_archivo`) declaradas con `@tool` + `Annotated[..., Field(description=…)]`, que delegan por A2A. Es el modelo quien decide a cuál llamar, en qué orden y con qué argumentos.
- `_execute_workflow()` (bucle secuencial escrito a mano) → sustituido por el único `await` de `agent.run(user_request, stream=True)`; el encadenamiento (clima → guardar) lo hace el modelo.
- Nuevo `_delegar_por_a2a()`: concentra el "protocolo" (construir el sobre, mostrarlo, entregarlo al buzón del destino). Conserva las cajas `┌─┐` con la estructura del mensaje A2A, que son el objetivo didáctico del bloque.
- `handle_message` pasa de **síncrono a asíncrono** y se documenta como buzón A2A, con las ramas `ping` y `workflow_request` (esta última ahora resuelve el flujo de verdad, antes solo devolvía "aceptado").
- Eliminado el **fallback simulado**: si un agente destino no está conectado, la herramienta devuelve un error explícito en vez de inventar una respuesta.
- Documentación con numeración por flujo `[0]…[10]` y marcas `⚙️ MFA` / `📡 A2A` / `🔧 Infra`, igual que en `agent1_research.py`.
- `main()` reescrito: antes construía el Coordinador **sin referencias** a los otros agentes y todo salía simulado; ahora los crea de verdad y pide una ciudad **no australiana** a propósito.

**Motivo:** el Coordinador narraba una orquestación que no existía. Se conserva el contrato de salida de `process_user_request` (`status`, `total_steps`, `successful_steps`, `results`, `summary`) porque lo consume `run_scenario1.py`, aún sin migrar.

**Notas:**
- ✅ **Probado end-to-end contra Azure real.** Petición: *"¿Qué clima hace en Tokio, Japón? Guárdalo en informe_tokio.txt"* → el modelo delegó en cadena a los dos agentes, **2/2 pasos correctos**, y se verificó el archivo `agent_workspace/informe_tokio.txt` (468 bytes, datos reales de Tokio: 34,5 °C).
- 🎯 **Bug de las 6 ciudades resuelto**: al extraer el LLM los parámetros, funciona con cualquier ciudad del mundo.
- ⚠️ **Compatibilidad hacia atrás:** `_delegar_por_a2a` detecta con `asyncio.iscoroutine()` si el `handle_message` del destino es asíncrono (Investigación, ya migrado) o síncrono (Ejecutor, sin migrar), y espera solo cuando toca. Este apaño se podrá quitar al migrar `agent3_executor.py`.
- ⚠️ `run_scenario1.py` llama a `coordinator.handle_message(...)` **sin `await`** dentro de `demonstrate_agent_communication`, que es **código muerto** (nunca se invoca). Al migrar `run_scenario1.py` hay que corregirlo o eliminarlo.
- ⚠️ `send_to_coordinator` de `agent1_research.py` sigue **simulado**: la vuelta Investigación → Coordinador ocurre hoy como valor de retorno de la herramienta, no como mensaje A2A.
- 📌 **Decisión de diseño (A2A):** se evaluó `agent_framework.a2a.A2AAgent`, pero **exige que cada agente esté publicado como servidor A2A por HTTP** (`url=` o `agent_card=`). Eso obligaría a levantar servidores para Investigación y Ejecutor y reestructurar el escenario entero. Se descartó por ahora para respetar "una demo a la vez"; la delegación se hace con function tools sobre el contrato de mensajes A2A ya existente. También se evaluó `Agent.as_tool()` (delegación agente→agente nativa de MFA): se descartó porque no deja interceptar la llamada para **mostrar el sobre A2A**, que es justamente lo que la demo debe enseñar. Queda anotado como posible evolución.

---

## 2026-07-22 — `agents/agent1_research.py`: documentación didáctica reforzada

**Cambio:** solo comentarios y docstrings; **cero cambios de lógica**. Reescritura de la documentación interna a petición del usuario (feedback de aula):

- **Renumeración por FLUJO DE EJECUCIÓN real**, no por orden de aparición en el archivo. Antes `handle_message` quedaba al final sin número pese a ser el punto de entrada; ahora es el paso **[5]** y el orden es: arranque `[0]-[3]` → `__init__` `[4]` → `handle_message` `[5]` → `process_research_request` `[6]` → `_asegurar_conexion` `[7]` → `_consultar_clima_por_mcp` `[8]` → `agent.run` `[9]` → respuesta A2A `[10]` → `send_to_coordinator` `[11]` → `cerrar` `[12]`.
- **Mapa del flujo en el docstring del módulo**, para poder seguir la demo sin leer todo el archivo.
- **Sub-numeración** `[4.1]`, `[5.2]`, `[7.1]`… en los pasos internos de cada método.
- **Clasificación por tipo de instrucción** con marcas: `⚙️ MFA` (propio del framework, materia de estudio), `🔌 MCP` (protocolo) y `🔧 Infra` (Python/entorno). El objetivo es que el alumno distinga qué está aprendiendo del framework y qué es andamiaje.
- **`handle_message` documentado como "buzón"/enrutador A2A**, explicando que es la única puerta de entrada y que cada rama (`research_request`, `ping`, desconocido) es una capacidad publicada hacia otros agentes.
- Explicaciones ampliadas de los elementos MFA que generaban dudas: qué es un `ChatClient` frente a un `Agent`, qué hace `tools=[...]`, por qué `.functions` demuestra el descubrimiento por protocolo, y qué ocurre realmente dentro del único `await` de `agent.run(stream=True)` (modelo → decide tool → framework la ejecuta por MCP → servidor consulta Open-Meteo → modelo redacta).
- Marcado explícito de `send_to_coordinator` como **⚠️ PENDIENTE DE MIGRAR** (sigue simulado hasta que se migre el Coordinador).

**Motivo:** los alumnos preguntaban qué hacen las instrucciones propias de MFA, y la numeración anterior no permitía seguir el orden de ejecución.

**Notas:** ✅ Reejecutado end-to-end tras la reescritura: sigue funcionando contra Azure real y devolviendo datos reales de Santiago en español.

---

## 2026-07-22 — `agents/agent1_research.py` migrado a MFA + MCP real ✅

**Cambio:** primera migración del bloque. El Agente de Investigación pasa de simulación a MFA real:

- `openai.AzureOpenAI` (creado y **nunca usado**) → `OpenAIChatClient` + `Agent` de `agent_framework`. **Ahora sí se invoca al LLM.**
- `from mcp_servers.weather_server import get_weather` (import de Python directo) → `MCPStdioTool(name="servidor_clima", command=sys.executable, args=[...])`. **Se habla protocolo MCP de verdad**: el servidor arranca como subproceso y las herramientas se descubren por protocolo (`get_alerts`, `get_forecast`, `get_weather`), no escritas a mano.
- Es el **modelo** quien decide qué herramienta MCP llamar, en vez del `if/elif` anterior.
- Salida en streaming con `agent.run(consulta, stream=True)`.
- Ciclo de vida MCP: `connect()` perezoso + `close()`, y soporte de `async with ResearchAgent()`.
- Todos los textos de interfaz traducidos al español; las instrucciones del agente exigen responder SIEMPRE en español.
- Comentarios de secuencia numerados `[0]…[12]` siguiendo el orden real de ejecución.
- 🐞 Arreglado: el `main()` llamaba a `handle_message` (asíncrono) **sin `await`**, y reventaba en `json.dumps` con una corrutina.
- `load_dotenv()` dependiente del cwd → ruta absoluta (`Path(__file__).parent.parent / ".env"`) con `override=True`.

**Motivo:** el objetivo pedagógico del bloque es enseñar MCP y A2A; el código los *narraba* pero no los ejecutaba. Se conserva el contrato externo (`handle_message` / `process_research_request` con los mismos dicts A2A) para no romper `agent2_coordinator.py` ni `run_scenario1.py`, que aún no están migrados.

**Notas:**
- ✅ **Probado end-to-end contra Azure real** (deployment `gpt-5.4-mini`): el agente llamó a `get_weather` vía MCP, Open-Meteo devolvió datos de Santiago de Chile y la respuesta salió en español.
- 🚨 **Trampa MCP stdio (crítica):** en transporte stdio, **stdout ES el canal JSON-RPC**. Los `print()` de arranque de `weather_server.py` corrompían el protocolo → `McpError: Connection closed`. Se movieron a **stderr**. Cualquier servidor MCP stdio futuro debe respetar esto.
- 🚨 **Encoding en Windows:** la consola usa cp1252 y los emojis de la interfaz provocan `UnicodeEncodeError`. Se fuerza UTF-8 con `sys.stdout.reconfigure(encoding="utf-8")` (más limpio que el `io.TextIOWrapper` que usa el escenario 2). Hace falta **en cada archivo ejecutable** del escenario.
- Se bajó a `WARNING` el logging de `httpx`/`httpcore`/`mcp`/`openai`/`agent_framework` en el agente **y en el servidor**: al correr como subproceso, el stderr del servidor se mezcla con la interfaz y tapaba la demo.

**Cambio colateral necesario en `mcp_servers/weather_server.py`** (aún no migrado formalmente): solo su `main()` — prints a stderr, UTF-8 y silenciado de logs. Las herramientas y sus textos **siguen en inglés**; se traducirán al migrar ese componente.

**Pendiente de probar:** nada en este archivo. `agent2_coordinator.py` y `run_scenario1.py` siguen invocando al Research Agent por el contrato antiguo, que se respetó, pero **no se han reejecutado** todavía.

---

## 2026-07-22 — `requirements.txt` del escenario 1 reescrito y pinneado

**Cambio:** sustituido el `requirements.txt` heredado (rangos `>=`, dependencias inexistentes) por versiones pinneadas y verificadas:

| Paquete | Versión | Nota |
|---|---|---|
| `agent-framework-core` | **1.12.0** | última estable; trae MCP en el core |
| `agent-framework-openai` | **1.10.2** | `OpenAIChatClient` nativo-Azure |
| `agent-framework-a2a` | **1.0.0b260721** | beta; para el Coordinador |
| `a2a-sdk` | **1.1.2** | pinneado junto al anterior |
| `mcp` | **1.28.1** | última |
| `httpx` | **0.28.1** | |
| `python-dotenv` | **1.2.2** | |
| `rich` | **15.0.0** | |

**Motivo:** decisión del usuario de trabajar con lo más reciente para no quedar obsoletos pronto. El venv del escenario estaba **vacío** (solo `pip`), así que se instaló todo desde cero. Eliminados `azure-ai-projects`, `azure-identity`, `aiohttp` y `pydantic` como dependencias directas: no se importan en ningún archivo del escenario 1 (`pydantic` entra igualmente por arrastre del core).

**Notas:**
- Instalación limpia, **sin conflictos de resolución**.
- ✅ Verificado que `from agent_framework.a2a import A2AAgent, A2AExecutor` **ya funciona** con `a2a-sdk 1.1.2`: la incompatibilidad del `FilePart` documentada en el inventario queda **resuelta**.
- Versiones que quedaron por arrastre: `openai==2.47.0`, `pydantic==2.13.4`, `opentelemetry-api==1.44.0`.
- Subimos de core 1.11.0 (el de Part-1/2/3) a **1.12.0**: este bloque queda una versión por delante del resto de la serie.

---

## 2026-07-22 — Inventario inicial del entorno + creación de la bitácora

**Cambio:** se crean [CLAUDE.md](CLAUDE.md) (con estado de migración por componente y equivalencias de API) y este `Memory.md`. Todavía **no se ha migrado ni una línea de código**.

**Motivo:** arrancar el trabajo de modernización de este bloque con la misma modalidad usada en Part-1, Part-2 y Part-3.

**Notas — hallazgos del inventario:**

- **`agent_framework` NO está instalado en este bloque, y el código nunca lo importó.** El venv de `scenario1_local_agents` tiene Python 3.14.2 y **solo `pip==25.3`**; `scenario2_azure_foundry` **no tiene venv**. El escenario 1 usa `openai.AzureOpenAI` en crudo; el escenario 2 usa `azure.ai.projects` / `azure.ai.agents` en crudo. La migración aquí no es "API vieja de MFA → 1.11.0" sino una **reescritura sobre MFA**.
- **Versiones de referencia** (venv ya migrado de Part-1): core 1.11.0, foundry 1.10.1, openai 1.10.1, `agent-framework-a2a` 1.0.0b260212, `a2a-sdk` 1.1.0, `mcp` 1.28.1, `httpx` 0.28.1, `openai` 2.45.0, `pydantic` 2.13.4.
- **Últimas publicadas en PyPI:** core **1.12.0**, foundry/openai **1.10.2**, `agent-framework-a2a` **1.0.0b260721**, `a2a-sdk` **1.1.2**, `mcp` **1.28.1** (ya al día).
- 🚨 **Trampa de dependencias nueva:** `agent-framework-a2a==1.0.0b260212` está **roto** contra `a2a-sdk` 1.x. Declara `a2a-sdk>=0.3.5` sin techo, pero la línea 1.0 eliminó `FilePart` / `FileWithBytes` / `FileWithUri` de `a2a.types`; `import agent_framework.a2a` falla con `ImportError: cannot import name 'FilePart'`. `a2a.compat.v0_3` no los reexpone. **Resuelto aguas arriba**: `agent-framework-a2a==1.0.0b260721` ya declara `a2a-sdk>=1.0.0,<2` y `agent-framework-core>=1.11.0,<2` (verificado en los metadatos de PyPI).
- **MCP vive en el core**, no en un subpaquete: `agent_framework._mcp` exporta `MCPStdioTool`, `MCPStreamableHTTPTool`, `MCPWebsocketTool`, `MCPTaskOptions`, `MCPSkill`, `MCPSkillResource`, `MCPSkillsSource`, `SupportsMCPTool`. Traen `approval_mode`, `allowed_tools`, `use_progressive_disclosure` y sampling nativos.
- **A2A vive en `agent_framework.a2a`** (shim perezoso sobre `agent_framework_a2a`) y expone `A2AAgent`, `A2AAgentSession`, `A2AExecutor`, `A2AServiceSessionId`. **Sigue en beta**, a diferencia del core.
- **El código actual simula MCP y A2A**: los agentes importan las funciones de los servidores MCP directamente (sin JSON-RPC ni proceso aparte), el escenario 1 nunca llama al LLM (cliente `AzureOpenAI` e `instructions` creados pero jamás usados), y el "A2A" son llamadas Python directas entre objetos. Detalle completo en [CLAUDE.md](CLAUDE.md).

**Pendiente de decisión del usuario:** fijar `agent-framework-core` en **1.11.0** (alineado con Part-1/2/3, recomendado) o subir a **1.12.0**. Nada instalado ni pinneado todavía.
