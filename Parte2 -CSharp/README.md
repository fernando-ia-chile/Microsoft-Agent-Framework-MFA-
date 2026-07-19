# Microsoft Agent Framework — Parte 2 en C# (.NET 10)

**Autor: Fernando Valdés Herrera**
*Material con fines educativos.*

Réplica en **C#** de la Parte 2 del laboratorio de Python. Mismos cinco ejemplos, mismo objetivo
pedagógico, misma salida por consola — pero usando el **Microsoft Agent Framework para .NET**
(`Microsoft.Agents.AI`).

Todo vive en **un único proyecto de consola** con un menú, igual que `Parte1 -CSharp`.

---

## Correspondencia con el proyecto de Python

| # | Python (`Part-2/`) | C# (este proyecto) |
|---|---|---|
| 11 | `new_11_threading_auto.py` | `Examples/Example11_ThreadingAuto.cs` |
| 12 | `new_12_long_term_memory_AI.py` | `Examples/Example12_LongTermMemoryAI.cs` |
| 13 | `new_13_middleware_complete.py` | `Examples/Example13_MiddlewareComplete.cs` |
| 14 | `new_14_observability_COMPLETE.py` | `Examples/Example14_ObservabilityComplete.cs` |
| 15 | `new_15_mcp_interactive.py` | `Examples/Example15_McpInteractive.cs` |
| — | `mcp_calculator_server.py` | `Examples/McpCalculatorServer.cs` |
| — | `.env03` | `appsettings03.json` |
| — | `requirements.txt` | `MFA.CSharp.Part2.csproj` |

> Los archivos usan `PascalCase` en vez de `snake_case` porque es la convención de C# (el nombre
> del archivo debe coincidir con el del tipo) y porque así queda consistente con `Parte1 -CSharp`.
> La numeración y el orden son idénticos a los de Python.

---

## Puesta en marcha

### 1. Requisitos

- **.NET 10 SDK**
- Un recurso de **Azure OpenAI** con un deployment de chat

### 2. Credenciales

Edita `appsettings03.json`:

```json
{
  "AzureOpenAI": {
    "Endpoint": "https://<recurso>.services.ai.azure.com",
    "ChatDeploymentName": "<nombre-de-tu-deployment>",
    "ApiKey": "<tu-api-key>"
  }
}
```

⚠️ **El error más común de toda la serie.** `Endpoint` debe ser **solo la base**, sin
`/openai/v1/...`. El SDK agrega esa ruta por su cuenta; si la incluyes, la URL sale duplicada y
obtienes un **404 Resource not found**.

🔒 **No subas credenciales reales a git.**

### 3. Ejecutar

```powershell
cd "Parte2 -CSharp"
dotnet run              # muestra el menú
dotnet run -- 13        # ejecuta un ejemplo directamente
```

Dentro de cada ejemplo, escribe `quit`, `exit` o `q` para volver al menú.

---

## Ejemplo 11 — Sesiones y persistencia

**Qué enseña.** Que el estado de una conversación se puede guardar en disco y restaurar. Tras cada
mensaje: serializar → guardar a JSON → leer → deserializar → seguir conversando con lo restaurado.

### Python → C#

| Python (`agent_framework`) | C# (`Microsoft.Agents.AI`) |
|---|---|
| `agent.create_session()` | `await agent.CreateSessionAsync()` |
| `agent.run(x, stream=True, session=s)` | `agent.RunStreamingAsync(x, session)` |
| `session.to_dict()` → `dict` | `await agent.SerializeSessionAsync(session)` → `JsonElement` |
| `AgentSession.from_dict(d)` (estático) | `await agent.DeserializeSessionAsync(json)` (**desde el agente**) |
| `json.dump(...)` | `JsonSerializer.Serialize(...)` |

**Diferencia de diseño interesante:** en Python la sesión se reconstruye con un método *estático*
(`AgentSession.from_dict`). En C# se reconstruye **a través del agente**
(`agent.DeserializeSessionAsync`), porque es el agente quien le adjunta los comportamientos
(historial, context providers). Por eso en .NET la sesión tampoco se puede reutilizar entre
agentes distintos.

### Pruébalo

```
Tú: Me llamo Fernando y trabajo en admisiones
Tú: quit
```
Vuelve a entrar al ejemplo 11 y pregunta:
```
Tú: ¿Cómo me llamo y en qué área trabajo?
```

Artefacto: `session_history.json`

---

## Ejemplo 12 — Memoria de largo plazo con IA

**Qué enseña.** Dos capas de memoria: **corto plazo** (historial de la sesión, se pierde al abrir
una nueva) y **largo plazo** (perfil del usuario en disco, sobrevive a sesiones y reinicios). El
perfil lo llena la propia IA decidiendo qué vale la pena recordar.

### Python → C#

| Python | C# |
|---|---|
| `class X(ContextProvider)` | `class X : AIContextProvider` |
| `before_run(*, agent, session, context, state)` | `ProvideAIContextAsync(InvokingContext, ct)` |
| `after_run(*, agent, session, context, state)` | `StoreAIContextAsync(InvokedContext, ct)` |
| `context.extend_instructions(id, texto)` (muta) | `return new AIContext { Instructions = ... }` (**devuelve**) |
| `super().__init__(source_id="...")` | `: base(null, null)` |
| `context.input_messages` | `context.RequestMessages` |
| `options={"response_format": Modelo}` → `.value` | `GetResponseAsync<T>(...)` → `TryGetResult(out T)` |
| Modelo `pydantic.BaseModel` | Clase con `[Description]` + `[JsonPropertyName]` |

**Diferencia importante:** Python **muta** el contexto (`extend_instructions`); C# **devuelve** un
`AIContext` nuevo. Es el mismo concepto con estilos opuestos.

### Pruébalo

```
Tú: Hola, me llamo Fernando, soy arquitecto de software y programo en C#
Tú: new          ← abre una sesión limpia
Tú: ¿Cómo me llamo y a qué me dedico?
```
`profile` muestra lo aprendido. Artefacto: `ai_memory_profile.json`

---

## Ejemplo 13 — Middleware: los 3 tipos juntos

**Qué enseña.** Dónde se engancha cada tipo de middleware. Cuatro piezas, tres tipos: Timing
(agent), Seguridad (agent), Logger (function), Tokens (chat client).

### Python → C#

| Python | C# |
|---|---|
| `middleware=[...]` en el constructor | `agent.AsBuilder().Use(...).Build()` (**patrón builder**) |
| `@agent_middleware` | `.Use(runFunc:, runStreamingFunc:)` — **dos delegados** |
| `@function_middleware` | `.Use(funcMiddleware)` |
| `@chat_middleware` | `chatClient.AsBuilder().Use(normal, streaming)` |
| `await call_next()` | `await innerAgent.RunAsync(...)` / `await next(context, ct)` |
| `raise MiddlewareTermination(...)` | No llamar al `innerAgent` y devolver tu propia respuesta |
| `response.usage_details` | `response.Usage` (`InputTokenCount`, `OutputTokenCount`) |
| `context.stream_result_hooks` | `try/finally` alrededor del `await foreach` |

**Dos diferencias que importan:**

1. **En C# hay que escribir cada middleware dos veces** (normal y streaming). Python resuelve
   ambos casos con una sola función.
2. **Medir tiempo en streaming es más simple en C#.** En Python un `finally` alrededor de
   `call_next()` reporta 0.00 s y hay que registrar un hook. En C#, como el middleware de
   streaming es un iterador (`IAsyncEnumerable` con `yield return`), el `finally` que envuelve al
   `await foreach` corre cuando el stream terminó de verdad.

### Pruébalo

```
Tú: ¿qué hora es y cuánto es 15 * 8?      ← Timing + Logger (2 tools) + Tokens
Tú: ¿cuál es mi password?                  ← Seguridad BLOQUEA
Tú: busca usuarios y dame el clima de París   ← los 4 middleware
```

---

## Ejemplo 14 — Observabilidad con OpenTelemetry

**Qué enseña.** Todo lo que el framework emite como telemetría, capturado con un exportador propio
y volcado a un reporte HTML navegable.

### Python → C#

| Python | C# |
|---|---|
| `configure_otel_providers(exporters=[c], enable_sensitive_data=True)` | `Sdk.CreateTracerProviderBuilder()...Build()` + `.UseOpenTelemetry(...)` |
| `class C(SpanExporter)` con `export(spans)` | `class C : BaseExporter<Activity>` con `Export(in Batch<Activity>)` |
| *(instrumentación global)* | `agent.AsBuilder().UseOpenTelemetry(sourceName, cfg => cfg.EnableSensitiveData = true)` |
| `trace.get_tracer_provider().force_flush()` | `tracerProvider.ForceFlush()` |
| `span.attributes` | `activity.TagObjects` |
| `opentelemetry-sdk` (pip) | `OpenTelemetry` (NuGet) |

**Diferencia importante:** en Python una sola llamada activa la instrumentación globalmente. En C#
son **dos pasos separados**: montar el `TracerProvider` (infraestructura) y envolver el agente con
`.UseOpenTelemetry(...)` (instrumentación). **Sin el segundo paso no se captura nada**, aunque el
provider esté montado — y el `sourceName` debe coincidir en ambos.

> En .NET, `Activity` es la implementación de "Span" y `ActivitySource` la de "Tracer". Los nombres
> son anteriores a OpenTelemetry y se conservaron por compatibilidad.

### Pruébalo

```
Tú: ¿qué clima hace en Tokio y cuánto es 50*50?
Tú: quit
```
Se genera `complete_telemetry_report.html`, autocontenido (abre sin conexión).

---

## Ejemplo 15 — Model Context Protocol (MCP)

**Qué enseña.** Que un agente puede usar herramientas que **no están en su código**, sino que vienen
de un servidor externo que descubre en tiempo de ejecución. Incluye **las dos mitades**: cliente y
servidor (8 herramientas).

### Python → C#

| Python | C# |
|---|---|
| `MCPStdioTool(name=, command=, args=)` | `McpClient.CreateAsync(new StdioClientTransport(...))` |
| *(las tools se pasan implícitas)* | `await mcpClient.ListToolsAsync()` → `[.. tools.Cast<AITool>()]` |
| `FastMCP("calculadora")` | `AddMcpServer().WithStdioServerTransport().WithTools<T>()` |
| `@mcp.tool()` | `[McpServerTool(Name = "...")]` + `[Description]` |
| `command=sys.executable`, archivo aparte | `Environment.ProcessPath` + argumento `mcp-server` |
| `log_level="WARNING"` | `LogToStandardErrorThreshold = LogLevel.Trace` |
| paquete `mcp` (pip) | `ModelContextProtocol` (NuGet) |

**Un solo proyecto.** En Python el servidor es un archivo `.py` aparte. Aquí, para respetar el
"un único proyecto", el cliente **relanza este mismo ejecutable** con el argumento `mcp-server`
(ver el inicio de `Program.cs`). Mismo binario, dos modos.

### Pruébalo

**Ejecuta solo el ejemplo 15**; el servidor lo lanza él como proceso hijo:

```
🔧 Tools descubiertas (8): potencia, multiplicar, restar, seno_grados,
                            dividir, coseno_grados, raiz_cuadrada, sumar
```

```
Tú: suma 10 y 5
Tú: ahora divide ese resultado por 3        ← la sesión recuerda el 15
Tú: calcula la raíz cuadrada de -4          ← dispara el error del servidor
```

La última prueba es la interesante: ese mensaje de error solo existe en *tu* servidor, así que
demuestra que la llamada pasó de verdad por `McpCalculatorServer.cs`.

> ⚠️ Un servidor MCP por stdio **nunca debe escribir a la salida estándar**: ese canal es el del
> protocolo JSON-RPC. Por eso los logs se redirigen a stderr.

---

## Diferencias generales entre Python y C#

| Aspecto | Python | C# |
|---|---|---|
| Crear sesión | `agent.create_session()` (sync) | `await agent.CreateSessionAsync()` (async) |
| Streaming | `async for chunk in agent.run(x, stream=True)` | `await foreach (var u in agent.RunStreamingAsync(x))` |
| Texto del fragmento | `chunk.text` | `update.Text` |
| Definir tools | función + `Annotated[..., Field(description=)]` | método + `[Description]` + `AIFunctionFactory.Create` |
| Evaluar expresiones | `eval(...)` acotado | `new DataTable().Compute(...)` |
| Salida estructurada | modelo Pydantic | clase con `[JsonPropertyName]` |
| Composición | listas en el constructor | patrón **builder** (`AsBuilder().Use(...).Build()`) |
| Configuración | `.env03` + `python-dotenv` | `appsettings03.json` + `Microsoft.Extensions.Configuration` |

---

## Paquetes NuGet

| Paquete | Versión | Para qué |
|---|---|---|
| `Microsoft.Agents.AI` | 1.13.0 | Núcleo del framework |
| `Microsoft.Agents.AI.OpenAI` | 1.13.0 | Integración con OpenAI/Azure OpenAI |
| `Azure.AI.OpenAI` | 2.9.0-beta.1 | SDK de Azure OpenAI |
| `Microsoft.Extensions.AI` | 10.8.0 | `AIFunctionFactory`, `IChatClient`, middleware |
| `Microsoft.Extensions.Configuration[.Json]` | 10.0.0 | Lectura de `appsettings03.json` |
| `OpenTelemetry` | 1.17.0 | Ejemplo 14 |
| `ModelContextProtocol` | 1.4.1 | Ejemplo 15 |
| `Microsoft.Extensions.Hosting` | 10.0.0 | Host del servidor MCP |

**Dos decisiones de versión que conviene conocer:**

- **`OpenTelemetry` 1.17.0 y no 1.14.0**: esa versión arrastra `OpenTelemetry.Api` con una
  vulnerabilidad conocida de gravedad moderada (`NU1902` / `GHSA-g94r-2vxg-569j`).
- **`Microsoft.Extensions.Configuration` 10.0.0 y no 9.0.18**: OpenTelemetry arrastra la 10.0.0 y
  NuGet trata la degradación como error (`NU1605`).

---

## Artefactos que generan los ejemplos

Se crean en el directorio de trabajo. Bórralos para reiniciar un ejemplo desde cero:

| Archivo | Lo genera |
|---|---|
| `session_history.json` | Ejemplo 11 |
| `ai_memory_profile.json` | Ejemplo 12 |
| `complete_telemetry_report.html` | Ejemplo 14 |

Están en el `.gitignore`.

---

## Créditos y licencia de uso

**Autor: Fernando Valdés Herrera**

Material desarrollado **con fines educativos**, como parte de una serie práctica sobre el
Microsoft Agent Framework. Su propósito es la enseñanza y el aprendizaje del desarrollo de agentes
de IA sobre Azure.

Para los ejemplos de aplicación en una institución de educación superior con ERP Banner, consulta
el `README.md` del proyecto de Python (`Part-2/`): los escenarios son idénticos, ya que ambos
proyectos implementan las mismas capacidades. Son **ilustrativos** y no constituyen una guía de
implementación ni una integración probada con Banner.

El Microsoft Agent Framework es un proyecto de Microsoft; este material es independiente y no está
afiliado ni respaldado por Microsoft ni por Ellucian (Banner).
