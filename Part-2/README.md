# Microsoft Agent Framework — Parte 2: Capacidades transversales

**Autor: Fernando Valdés Herrera**
*Material con fines educativos.*

Segunda entrega de una serie práctica de 3 partes sobre el **Microsoft Agent Framework (MFA)**
en Python sobre Azure. Si la Parte 1 cubre los fundamentos (crear agentes, herramientas,
salida estructurada), esta Parte 2 cubre las **capacidades transversales**: las que no se ven
en una demo simple pero son las que hacen falta para llevar un agente a producción.

Las cinco demos son programas de terminal **autónomos e interactivos**. No hay librería
compartida ni suite de pruebas: cada archivo se ejecuta, se conversa con él y se observa lo
que imprime. La interfaz de consola (banderas `===`, emojis, prefijos como `[TIMING]` o
`[IA APRENDIÓ]`) es deliberada: hace visible el mecanismo interno que normalmente queda oculto.

> **Nota sobre la versión.** El código original de este tutorial se escribió para una API beta
> de 2025 que ya no existe. Todo fue **migrado a la línea estable `agent-framework-core` 1.11.0**
> y probado end-to-end. Cada demo incluye abajo su tabla de equivalencias viejo → nuevo, que es
> útil si tienes material antiguo que actualizar.

---

## Contenido

| Demo | Archivo | Tema |
|---|---|---|
| 11 | `new_11_threading_auto.py` | Sesiones y persistencia de conversaciones |
| 12 | `new_12_long_term_memory_AI.py` | Memoria de largo plazo con extracción por IA |
| 13 | `new_13_middleware_complete.py` | Middleware: los 3 tipos trabajando juntos |
| 14 | `new_14_observability_COMPLETE.py` | Observabilidad con OpenTelemetry |
| 15 | `new_15_mcp_interactive.py` + `mcp_calculator_server.py` | Model Context Protocol (MCP) |

---

## Puesta en marcha

### 1. Entorno

```powershell
cd Part-2
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Credenciales

Crea un archivo `.env03` en esta carpeta:

```ini
AZURE_OPENAI_ENDPOINT=https://<tu-recurso>.services.ai.azure.com
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<nombre-de-tu-deployment>
AZURE_OPENAI_API_KEY=<tu-api-key>
AZURE_OPENAI_API_VERSION=preview
```

⚠️ **El error más común de toda la serie.** `AZURE_OPENAI_ENDPOINT` debe ser **solo la base**,
sin `/openai/v1/...`. El framework agrega esa ruta por su cuenta; si la incluyes, la URL sale
duplicada y obtienes un **404 Resource not found**. Para diagnosticar, imprime `client.base_url`.

🔒 **No subas el `.env03` a git.** Contiene una clave real. Agrega `.env*` a tu `.gitignore`.

### 3. Ejecutar

```powershell
python new_11_threading_auto.py     # o la demo que quieras
```

Escribe `quit`, `exit` o `q` para salir. **Ejecuta siempre desde la carpeta `Part-2`**: los
scripts cargan `.env03` por nombre relativo.

---

## Demo 11 — Sesiones y persistencia

**Qué enseña.** Que el estado de una conversación se puede guardar en disco y restaurar, y que
el agente sigue recordando todo. Tras cada mensaje se hace el ciclo completo: serializar →
guardar a JSON → leer del JSON → deserializar → seguir conversando con lo restaurado.

### Cambios de API

| Viejo (API beta) | Nuevo (core 1.11.0) |
|---|---|
| `AzureOpenAIChatClient(endpoint=, deployment_name=)` | `OpenAIChatClient(azure_endpoint=, model=)` |
| `client.create_agent(...)` | `Agent(client, instructions=, name=)` |
| `AgentThread` (concepto "thread") | `AgentSession` (todo el vocabulario pasó a **sesión**) |
| `agent.get_new_thread()` | `agent.create_session()` |
| `agent.run_stream(x, thread=t)` | `agent.run(x, stream=True, session=s)` |
| `await thread.serialize()` | `session.to_dict()` — **ahora síncrono** |
| `await agent.deserialize_thread(d)` | `AgentSession.from_dict(d)` — **estático y síncrono** |
| `ChatMessage` (privado, `agent_framework._types`) | `Message` (público) |

**La gran simplificación:** el código viejo tenía que convertir a mano cada `ChatMessage` porque
`serialize()` devolvía objetos que `json.dump` no sabía escribir. Ya no: `session.to_dict()`
entrega tipos primitivos y se serializa directo.

### Pruébalo

```
Tú: Me llamo Fernando y trabajo en admisiones
Tú: quit
```
Vuelve a ejecutar el script. Ahora:
```
Tú: ¿Cómo me llamo y en qué área trabajo?
```
El agente responde correctamente: la conversación sobrevivió al cierre del programa.

> 💡 **Dónde vive el historial:** en `session.state["in_memory"]["messages"]`, gestionado por el
> `InMemoryHistoryProvider`. Cada provider guarda lo suyo bajo su propio `source_id`, no en la
> raíz del estado.

### En una institución educativa con Banner

Un asistente de matrícula que atiende a un estudiante el lunes y **retoma la misma conversación
el jueves** sin pedirle que repita su situación. El estudiante pregunta por un ramo con tope de
horario, se va a consultar con su jefe de carrera y vuelve días después: el agente aún tiene el
contexto. Serializando la sesión a la base de datos junto al ID de Banner del estudiante, cada
persona retoma exactamente donde quedó, y el equipo de soporte puede reconstruir la conversación
si hay un reclamo.

---

## Demo 12 — Memoria de largo plazo con IA

**Qué enseña.** Que hay **dos capas de memoria** distintas:

- **Corto plazo** — el historial de la sesión; se pierde al abrir una nueva.
- **Largo plazo** — un perfil del usuario que persiste en disco y sobrevive a sesiones nuevas
  y a reinicios.

Y que el perfil no se llena con reglas rígidas: es la propia IA la que decide qué vale la pena
recordar de cada mensaje.

### Cambios de API

| Viejo (API beta) | Nuevo (core 1.11.0) |
|---|---|
| `ContextProvider.invoking(messages)` → devuelve `Context` | `before_run(*, agent, session, context, state)` → **no devuelve nada** |
| `ContextProvider.invoked(req_msgs, resp_msgs)` | `after_run(*, agent, session, context, state)` |
| `return Context(instructions=...)` | `context.extend_instructions(source_id, texto)` — se **muta** el contexto |
| `ContextProvider()` sin argumentos | `super().__init__(source_id="...")` — **obligatorio** |
| leer `request_messages` del parámetro | `context.input_messages` |
| `AsyncAzureOpenAI(...)` + `.chat.completions.create()` | `OpenAIChatClient.get_response(...)` — **todo dentro de MFA** |
| `ai_response.index("{")` + `json.loads(...)` | `options={"response_format": ModeloPydantic}` → `response.value` |

**Dos mejoras de la migración:** la demo pasó de **dos clientes a uno** (se eliminó el SDK crudo
de OpenAI) y desapareció el parseo frágil de JSON buscando llaves en el texto, reemplazado por
salida estructurada validada con Pydantic.

### Pruébalo

```
Tú: Hola, me llamo Fernando, soy arquitecto de software y programo en C#
Tú: new          ← abre una sesión limpia
Tú: ¿Cómo me llamo y a qué me dedico?
```

El agente responde bien **aunque la conversación anterior se descartó**: el perfil se guardó en
`ai_memory_profile.json`. Escribe `profile` para ver qué aprendió. Borra ese archivo para
empezar de cero.

> 💡 Se descartó a propósito el `MemoryContextProvider` nativo: es **experimental** y demasiado
> pesado (exige `MemoryStore`, archivos por tema, consolidación programada). Reemplazaría justo
> lo que la demo quiere enseñar.

### En una institución educativa con Banner

Un asistente que **no vuelve a preguntar lo obvio**. Aprende que el estudiante cursa Ingeniería
Civil, va en quinto semestre, tiene beca y jornada vespertina — datos que puede consolidar desde
Banner o desde la propia conversación. En la siguiente consulta, sobre cualquier tema, ya
personaliza: no le ofrece cursos de mañana ni le explica beneficios que no le corresponden.

Aplicado a un mesón de atención virtual, esto reduce el trabajo repetitivo de identificar al
estudiante en cada interacción, que es donde se pierde la mayor parte del tiempo.

---

## Demo 13 — Middleware: los 3 tipos juntos

**Qué enseña.** Dónde se engancha cada tipo de middleware en el ciclo de vida de una petición.
Cuatro piezas, tres tipos:

| Middleware | Tipo | Qué hace |
|---|---|---|
| Timing | agent | Mide cuánto tarda el run completo |
| Seguridad | agent | Bloquea peticiones con contenido sensible |
| Logger | function | Registra cada llamada a una herramienta |
| Tokens | chat | Informa el consumo real de tokens |

### Cambios de API

| Viejo (API beta) | Nuevo (core 1.11.0) |
|---|---|
| `AgentRunContext` | `AgentContext` |
| `async def mw(context, next)` | `async def mw(context, call_next)` |
| `await next(context)` | `await call_next()` — **ya no recibe el contexto** |
| `context.terminate = True` | `raise MiddlewareTermination(mensaje)` — **bandera → excepción** |
| `len(texto) // 4` (estimación de tokens) | `response.usage_details` — **valores reales del proveedor** |
| `context.result.choices[0].message.content` | `context.stream_result_hooks` + `response` |

**Sobrevivieron sin cambios:** `agent_middleware`, `chat_middleware`, `function_middleware`,
`ChatContext`, `FunctionInvocationContext`, `context.function.name`, `context.arguments`.

### Pruébalo

```
Tú: ¿qué hora es y cuánto es 15 * 8?     ← dispara Timing + Logger (2 tools) + Tokens
Tú: ¿cuál es mi password?                 ← Seguridad BLOQUEA la petición
Tú: busca usuarios y dame el clima de París   ← los 4 middleware a la vez
```

Salida típica:
```
⏱️  [TIMING] Inicio 12:21:01
🤖 [LLAMADA IA] Tokens de entrada : 224  ·  salida : 49  ·  totales : 273
🔧 [FUNCIÓN] Llamando a la tool: calculate
🔧 [FUNCIÓN] Argumentos: {'expresion': '15 * 8'}
⏱️  [TIMING] Completado en 4.43 s
```

> ⚠️ **Trampa al medir tiempo en streaming.** Un `try/finally` alrededor de `call_next()` reporta
> **0.00 s**, porque esa llamada retorna cuando el stream queda *listo para consumirse*, no cuando
> terminó. Para el tiempo real hay que registrar un hook en `context.stream_result_hooks`.

### En una institución educativa con Banner

Es la pieza de **gobernanza**, y probablemente la más relevante en una institución:

- **Seguridad:** un único punto que impide que el agente procese consultas con datos sensibles
  (RUT completo, notas de terceros, información de salud), sin tener que auditar demo por demo.
  Un solo middleware protege a todos los agentes del campus.
- **Logger:** deja registro de cada consulta a Banner que hizo el agente, con qué parámetros y
  qué devolvió. Trazabilidad para auditoría interna.
- **Tokens:** costo real por consulta, lo que permite **imputar gasto por unidad** — cuánto
  consume Admisión, cuánto Registro Curricular, cuánto Finanzas.

---

## Demo 14 — Observabilidad con OpenTelemetry

**Qué enseña.** Todo lo que el framework emite como telemetría: conversación completa, respuestas
del modelo, argumentos y resultados de cada herramienta, tokens, modelo usado, IDs de traza y
tiempos. Se captura con un exportador propio y al salir genera un **reporte HTML navegable**.

### Cambios de API

| Viejo (API beta) | Nuevo (core 1.11.0) |
|---|---|
| `setup_observability(...)` | `configure_otel_providers(...)` |
| `Resource.create({...})` | *(lo crea el framework)* |
| `TracerProvider(resource=...)` | *(lo crea el framework)* |
| `add_span_processor(BatchSpanProcessor(c))` | `configure_otel_providers(exporters=[c])` |
| `trace.set_tracer_provider(tp)` | *(lo hace el framework)* |
| `tracer_provider.force_flush()` | `trace.get_tracer_provider().force_flush()` |

**La gran simplificación:** el montaje de OpenTelemetry pasó de **5 pasos manuales a 1 llamada**:

```python
configure_otel_providers(exporters=[collector], enable_sensitive_data=True)
```

`enable_sensitive_data=True` es lo que hace que los spans incluyan el **contenido** de los
mensajes. Sin eso, el reporte queda sin conversaciones — pero en producción hay que pensarlo dos
veces, porque esos textos terminan en tu backend de observabilidad.

### Pruébalo

```
Tú: ¿qué clima hace en Tokio y cuánto es 50*50?
Tú: quit
```

Se abre `complete_telemetry_report.html` en el navegador. Una consulta con dos herramientas
genera **5 operaciones**: 1 `invoke_agent` + 2 `chat` + 2 `execute_tool`.

> 💡 Los atributos siguen las **convenciones semánticas GenAI de OpenTelemetry** (`gen_ai.*`), así
> que el reporte sirve para cualquier proveedor, no solo Azure OpenAI. El HTML es autocontenido:
> no requiere conexión para abrirse.

### En una institución educativa con Banner

Cuando un estudiante reclama *"el asistente me dijo que sí tenía cupo"*, la traza muestra
exactamente qué consultó el agente a Banner, con qué parámetros, qué devolvió el sistema y qué
respondió el modelo. Deja de ser la palabra del estudiante contra la del sistema.

En operación diaria sirve para detectar cuellos de botella (qué consulta a Banner tarda 8
segundos en el peak de matrícula) y para medir consumo por período académico. La misma telemetría
se puede enviar a Azure Monitor cambiando una línea, e integrarse con el monitoreo que la
institución ya tenga.

---

## Demo 15 — Model Context Protocol (MCP)

**Qué enseña.** Que un agente puede usar herramientas que **no están en su código**, sino que
vienen de un servidor externo que descubre en tiempo de ejecución. MCP es un estándar: el mismo
servidor lo podría consumir Claude Desktop, VS Code u otro agente.

Esta demo incluye **las dos mitades**: el cliente (`new_15_mcp_interactive.py`) y el servidor
(`mcp_calculator_server.py`, con 8 herramientas construidas con `FastMCP`).

### Cambios de API

| Viejo (API beta) | Nuevo (core 1.11.0) |
|---|---|
| `AzureOpenAIChatClient(...)` | `OpenAIChatClient(azure_endpoint=, model=)` |
| `client.create_agent(...)` | `Agent(client, instructions=, name=)` |
| `await agent.run(x)` + `print(result)` | `agent.run(x, stream=True, session=s)` + `chunk.text` |
| *(sin sesión)* | `agent.create_session()` — permite encadenar preguntas |
| `command="venv\Scripts\uvx.exe"` | `command=sys.executable` — ruta rota → intérprete del venv |
| **`MCPStdioTool`** | **`MCPStdioTool`** — ✅ sin cambios |

### Pruébalo

**Ejecuta solo el cliente.** El servidor lo lanza él como proceso hijo:

```powershell
python new_15_mcp_interactive.py
```

Verás el descubrimiento en tiempo de ejecución:
```
🔧 Tools descubiertas (8): sumar, restar, multiplicar, dividir,
                            potencia, raiz_cuadrada, seno_grados, coseno_grados
```

Luego:
```
Tú: suma 10 y 5
Tú: ahora divide ese resultado por 3        ← la sesión recuerda el 15
Tú: calcula la raíz cuadrada de -4          ← dispara el error del servidor
```

La última prueba es la interesante: ese mensaje de error solo existe en *tu* servidor, así que
demuestra que la llamada pasó de verdad por `mcp_calculator_server.py` y no la resolvió el modelo
de memoria.

> ⚠️ **Dos detalles del servidor.** Un servidor MCP por stdio **nunca debe usar `print()`** a
> salida estándar: ese canal es el del protocolo JSON-RPC. Y `FastMCP` registra cada petición por
> defecto, con mensajes que se cuelan en medio de la respuesta del agente; por eso se construye
> con `log_level="WARNING"`.

### En una institución educativa con Banner

Aquí está el mayor potencial práctico. En vez de escribir un conector a Banner dentro de cada
agente, se construye **un servidor MCP institucional** que expone las operaciones autorizadas:
consultar malla curricular, verificar prerrequisitos, revisar estado de beca, consultar cupos.

Ese servidor se escribe y se audita **una sola vez** — con sus permisos, su registro y sus
límites — y luego lo consumen el asistente de matrícula, el bot de la mesa de ayuda, el panel del
jefe de carrera y cualquier herramienta futura. Si mañana cambia la lógica de prerrequisitos, se
corrige en el servidor y todos los agentes quedan actualizados.

Además, al ser MCP un estándar abierto, ese mismo servidor funciona con clientes que la
institución no controla, sin reescribir nada.

---

## Equivalencias generales (heredadas de la Parte 1)

| API vieja | API 1.11.0 |
|---|---|
| `from agent_framework.azure import AzureOpenAIChatClient` | `from agent_framework.openai import OpenAIChatClient` |
| `ChatAgent` | `Agent` |
| `AzureAIAgentClient` | `FoundryChatClient` + `FoundryAgent` (`agent_framework.foundry`) |
| `agent.run_stream(x)` | `agent.run(x, stream=True)` |
| `response_format=Modelo` | `options={"response_format": Modelo}` → se lee `response.value` |
| `HostedFileSearchTool` | `FoundryChatClient.get_file_search_tool(vector_store_ids=[...])` |

⚠️ **`client.create_agent(...)` ya no existe.** Usa `Agent(client, instructions=..., name=...)`.

---

## Trampas de dependencias

**No instales el meta-paquete `agent-framework`.** Arrastra `agent-framework-azure-ai==1.0.0rc6`,
incompatible con core 1.11.0. Instala los subpaquetes concretos y pinneados, como hace el
`requirements.txt` de esta carpeta.

**`agent-framework-core` declara muy poco:** solo `opentelemetry-api`, `pydantic`,
`python-dotenv` y `typing-extensions`. Todo lo demás hay que declararlo explícitamente aunque
parezca que "ya funciona" — puede estar instalado de rebote por otra dependencia. Dos casos
reales de este proyecto:

| Paquete | Lo necesita | Por qué no venía |
|---|---|---|
| `opentelemetry-sdk` | Demo 14 | core solo declara `opentelemetry-**api**` |
| `mcp` | Demo 15 | core no lo declara en absoluto |

Ambas demos funcionaban por accidente en un entorno con otros paquetes instalados, y habrían
fallado con `ImportError` en un venv limpio.

---

## Archivos que generan las demos

Se crean en el directorio de trabajo. Bórralos para reiniciar una demo desde cero:

| Archivo | Lo genera |
|---|---|
| `session_history.json` | Demo 11 |
| `ai_memory_profile.json` | Demo 12 |
| `complete_telemetry_report.html` | Demo 14 |

---

## Créditos y licencia de uso

**Autor: Fernando Valdés Herrera**

Material desarrollado **con fines educativos**, como parte de una serie práctica de 3 partes
sobre el Microsoft Agent Framework. Su propósito es la enseñanza y el aprendizaje del desarrollo
de agentes de IA sobre Azure.

Los ejemplos aplicados a instituciones de educación superior con ERP Banner son **ilustrativos**:
buscan mostrar dónde encaja cada capacidad en un contexto real, no constituyen una guía de
implementación ni una integración probada con Banner. Cualquier despliegue sobre datos reales de
estudiantes debe pasar por las revisiones de seguridad, privacidad y cumplimiento normativo que
corresponda a cada institución.

El Microsoft Agent Framework es un proyecto de Microsoft; este material es independiente y no
está afiliado ni respaldado por Microsoft ni por Ellucian (Banner).
