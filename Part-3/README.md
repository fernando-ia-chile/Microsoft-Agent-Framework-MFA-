# Microsoft Agent Framework — Parte 3 · Workflows (modernizado a core 1.11.0)

> Serie práctica de aprendizaje del **Microsoft Agent Framework (MFA)** sobre Azure.
> Esta **Parte 3** cubre los **Workflows**: grafos de ejecutores, en 6 demos interactivas de terminal, **migradas desde la API beta original (2025) a la API estable actual (core `1.11.0`)**.

**Autor:** Fernando Valdés Herrera
**Naturaleza:** material **con fines educativos**

---

## 📑 Tabla de contenidos

- [Descripción](#-descripción)
- [Estado de la migración](#-estado-de-la-migración)
- [Requisitos e instalación](#-requisitos-e-instalación)
- [Configuración (.env03)](#-configuración-env03)
- [Cómo ejecutar](#-cómo-ejecutar)
- [Tabla comparativa maestra (API beta → API 1.11.0)](#-tabla-comparativa-maestra-api-beta--api-1110)
- [Las 6 demos: detalle, ejemplo y aplicación real](#-las-6-demos-detalle-ejemplo-y-aplicación-real)
- [Aplicación en una institución de educación superior con ERP Banner](#-aplicación-en-una-institución-de-educación-superior-con-erp-banner)
- [Componentes deprecados / eliminados (reporte MFA)](#-componentes-deprecados--eliminados-reporte-mfa)
- [Notas técnicas y gotchas](#-notas-técnicas-y-gotchas)
- [Datos de prueba](#-datos-de-prueba)
- [Roadmap / pendientes](#-roadmap--pendientes)
- [Autoría](#-autoría)

---

## 🎯 Descripción

Las Partes 1 y 2 trabajan con **agentes sueltos**. Esta Parte 3 introduce el `Workflow`: un **grafo dirigido de ejecutores** que se orquestan entre sí.

A diferencia de las partes anteriores, aquí **sí existe una librería compartida** ([`invoice_utils.py`](invoice_utils.py)) y **un único dominio**: la generación de facturas. Las seis demos son variaciones del *mismo* proceso de negocio — lo que cambia es la **topología del grafo**. Esa es precisamente la enseñanza: *el mismo trabajo, cableado de seis formas distintas*.

```
16 SECUENCIAL    A ─► B ─► C ─► D

17 CONCURRENTE   A ─┬─► B ─┐
                    ├─► C ─┼─► E ─► F
                    └─► D ─┘

18 RAMIFICADO    A ─┬─(caso 1)─► B ─┐
                    ├─(caso 2)─► C ─┼─► E
                    └─(defecto)─► D ─┘

19 HITL          A ─► B ─► C ─► D
                      ⏸     ⏸        (pausa real, espera humana)

20 VISUALIZA     (dibuja y analiza los grafos, no los ejecuta)

21 AGENTES       A ─► 🤖 ─► 🤖 ─► 🤖 ─► 🤖
```

### El porqué de la modernización

El código del tutorial original fue escrito para una **API beta de 2025** (`WorkflowOutputEvent`, `set_start_executor`, `run_stream`, `ChatAgent`, `AzureAIAgentClient`) que **ya no existe**. El entorno actual usa la línea estable **core `1.11.0`**, que renombró, movió o eliminó esas piezas.

De las 6 demos, **5 no llegaban ni a importarse** y la restante fallaba al construir el grafo. Este proyecto **moderniza cada demo manteniendo su objetivo pedagógico**, usando siempre métodos vigentes dentro de MFA.

---

## ✅ Estado de la migración

| # | Demo | Estado | Patrón / concepto |
|:-:|------|:------:|-------------------|
| 16 | `new_16_sequential_workflow.py` | ✅ | Cadena lineal · `@executor` |
| 17 | `new_17_concurrent_workflow.py` | ✅ | Fan-out / fan-in · concurrencia real |
| 18 | `new_18_branching_workflow.py` | ✅ | Switch-case · `Case` / `Default` |
| 19 | `new_19_interactive_checkpointing.py` | ✅ | Human-in-the-loop · checkpoints |
| 20 | `new_20_visualization_workflow.py` | ✅ | `WorkflowViz` · Mermaid / DOT |
| 21 | `new_21_agents_in_workflow.py` | ✅ | Agentes de IA como ejecutores |

**Las 6 demos de Parte 3 están migradas a core `1.11.0` y probadas end-to-end.**
La demo 21 se verificó contra **Azure AI Foundry real** (requiere `az login`).

---

## 📦 Requisitos e instalación

- **Python 3.14** (probado en 3.14.2)
- Sistema operativo: probado en Windows 11 con PowerShell
- Solo para la demo 21: **Azure CLI** y una suscripción con Azure AI Foundry

```powershell
# Desde el directorio Part-3
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### ⚠️ Trampa de dependencias (importante)

**NO instale el meta-paquete `agent-framework`.** Arrastra `agent-framework-azure-ai==1.0.0rc6`, **incompatible** con core `1.11.0`. Instale siempre los subpaquetes concretos, como hace [`requirements.txt`](requirements.txt):

| Paquete | Versión | Para qué |
|---|---|---|
| `agent-framework-core` | `1.11.0` | Todo el motor de workflows. **Única dependencia de las demos 16–20** |
| `agent-framework-foundry` | `1.10.1` | `FoundryChatClient` — **solo demo 21** |
| `agent-framework-openai` | `1.10.1` | Alternativa a Foundry para la demo 21 |
| `azure-identity` | `>=1.25.0` | `AzureCliCredential` — solo demo 21 |
| `python-dotenv` | `>=1.0.0` | Carga de `.env03` |
| `typing-extensions` | `>=4.16.0` | `Never` en `WorkflowContext[Never, T]` |

> **No hacen falta:** `requests`, `azure-ai-projects` (lo arrastra foundry) ni `graphviz` (ver [demo 20](#-20--visualización-de-workflows)).

---

## 🔑 Configuración (.env03)

Las demos **16 a 20 no usan ningún LLM**: son cálculo local puro y funcionan **sin credenciales válidas**. Solo la **demo 21** necesita conexión real.

```ini
# --- Solo necesarias para la DEMO 21 (Azure AI Foundry) ---
AZURE_AI_PROJECT_ENDPOINT=https://<su-recurso>.services.ai.azure.com/api/projects/<proyecto>
AZURE_AI_MODEL_DEPLOYMENT_NAME=<nombre-del-deployment>

# --- Alternativa Azure OpenAI directo (no usada hoy por ninguna demo) ---
AZURE_OPENAI_ENDPOINT=https://<su-recurso>.services.ai.azure.com
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<nombre-del-deployment>
AZURE_OPENAI_API_KEY=<su-clave>
AZURE_OPENAI_API_VERSION=preview
```

Variables **opcionales** del dominio de negocio (todas tienen valor por defecto, así que las demos funcionan sin definirlas):

| Variable | Defecto | Significado |
|---|:---:|---|
| `INVOICE_TAX_RATE` | `0.10` | Tasa de impuesto |
| `INVOICE_HIGH_VALUE_THRESHOLD` | `5000.00` | Umbral de "alto valor" |
| `INVOICE_HIGH_VALUE_DISCOUNT` | `0.05` | Descuento por volumen |
| `INVOICE_PREFERRED_DISCOUNT` | `0.03` | Descuento por fidelidad |
| `INVOICE_COMPANY_NAME` | `TechServices Inc.` | Encabezado del documento |
| `INVOICE_COMPANY_ADDRESS` | `123 Business St…` | Encabezado del documento |

> 🔒 **Seguridad:** este repositorio versiona los `.env`. **No suba claves reales**; añada un `.gitignore` para `.env*` y **regenere cualquier clave que haya sido expuesta**.

---

## ▶️ Cómo ejecutar

```powershell
.\.venv\Scripts\Activate.ps1          # Part-3 tiene su propio venv
python new_16_sequential_workflow.py  # cualquier demo
```

**Ejecute siempre desde el directorio `Part-3`**: el nombre del `.env` está codificado en los scripts.

Para la demo 21, además:

```powershell
az login
python new_21_agents_in_workflow.py
```

> 💡 **Windows:** si redirige la salida a un archivo o a otro proceso, los emojis pueden romper con `UnicodeEncodeError` (consola en cp1252). Solución: `$env:PYTHONIOENCODING="utf-8"`. En terminal normal no ocurre.

---

## 🔄 Tabla comparativa maestra (API beta → API 1.11.0)

### Construcción y ejecución del workflow

| API beta (2025) | API 1.11.0 | Nota |
|---|---|---|
| `WorkflowBuilder().set_start_executor(x)` | `WorkflowBuilder(start_executor=x)` | 🔴 El **método** ya no existe: pasa a argumento del constructor |
| `.with_checkpointing(storage)` | `WorkflowBuilder(..., checkpoint_storage=storage)` | 🔴 También pasa al constructor |
| *(no existía)* | `WorkflowBuilder(..., output_from=[...])` | 🟡 Sin él salta `DeprecationWarning`; será **obligatorio** |
| *(no existía)* | `WorkflowBuilder(..., name="...")` | 🟡 Necesario para listar checkpoints |
| `workflow.run_stream(msg)` | `workflow.run(msg, stream=True)` | 🔴 `run_stream` eliminado |
| `await workflow.run(msg)` | igual → devuelve `WorkflowRunResult` | 🟢 Usar `.get_outputs()` |

### Eventos

| API beta (2025) | API 1.11.0 | Nota |
|---|---|---|
| `WorkflowOutputEvent` | `WorkflowEvent` + `event.type == "output"` | 🔴 **Causa del fallo de 5 de las 6 demos** |
| `WorkflowStatusEvent` | `WorkflowEvent` + `event.type == "status"` | 🔴 Eliminado |
| `isinstance(event, XEvent)` | `event.type == "..."` | Discriminador por cadena |

Tipos de evento disponibles: `started`, `status`, `output`, `intermediate`, `request_info`, `warning`, `error`, `failed`, `superstep_started/completed`, `executor_invoked/completed/failed/bypassed`.
⚠️ El tipo `"data"` está **deprecado** (alias de `"intermediate"`).

### Human-in-the-loop y estado

| API beta (2025) | API 1.11.0 | Nota |
|---|---|---|
| `RequestInfoExecutor` / `RequestInfoMessage` | `await ctx.request_info(datos, TipoRespuesta)` | 🔴 Eliminados; ya no son nodos del grafo |
| *(no existía)* | `@response_handler` | 🟢 Recibe la respuesta en el **mismo** ejecutor |
| *(no existía)* | `run(responses={request_id: valor}, stream=True)` | 🟢 Reanudación |
| `await ctx.set_state({...})` | `ctx.set_state(clave, valor)` | 🔴 **Es SÍNCRONO** (sin `await`) y ya no acepta dict |
| `ctx.set_shared_state` / `get_shared_state` | **eliminados** | 🔴 El estado compartido viaja en el mensaje |
| `list_checkpoints()` | `list_checkpoints(workflow_name=...)` | 🔴 Parámetro ahora obligatorio |

### Agentes

| API beta (2025) | API 1.11.0 | Nota |
|---|---|---|
| `ChatAgent` | `Agent` | 🔴 Renombrado |
| `agent_framework.azure.AzureAIAgentClient` | `agent_framework.foundry.FoundryChatClient` | 🔴 Cambia de módulo y de paquete |
| `AIProjectClient` + `agents.create_agent(...)` | `Agent(client, name=…, instructions=…)` | 🟢 Agentes efímeros, sin gestión de ciclo de vida |
| `agent.run_stream(x)` | `agent.run(x, stream=True)` | 🔴 Eliminado |

### Lo que **sobrevive sin cambios** 🟢

`WorkflowBuilder` (clase) · `WorkflowContext` · `Executor` · `@handler` · `@executor` · `Case` · `Default` · `WorkflowViz` · `FileCheckpointStorage` · `WorkflowRunState` · `add_edge` · `add_chain` · `add_fan_out_edges` · `add_fan_in_edges` · `add_switch_case_edge_group` · `ctx.send_message()` · `ctx.yield_output()`

---

## 📚 Las 6 demos: detalle, ejemplo y aplicación real

### ▸ 16 · Workflow secuencial

**Concepto:** cadena lineal de 5 pasos. Cada uno alimenta al siguiente.
**Enseña:** `@executor`, el **contrato de tipos** de la arista, y los *supersteps*.

```python
# El TIPO es el contrato de la arista:
@executor(id="load_config")
async def load_configuration(señal: str, ctx: WorkflowContext[InvoiceConfig]) -> None:
    await ctx.send_message(InvoiceConfig())      # ENVÍA un InvoiceConfig

@executor(id="save_invoice")
async def save_invoice_step(datos: tuple, ctx: WorkflowContext[Never, str]) -> None:
    await ctx.yield_output("¡Completado!")       # TERMINAL: no envía, PRODUCE

workflow = (
    WorkflowBuilder(start_executor=load_configuration, output_from=[save_invoice_step])
    .add_edge(load_configuration, read_invoice_data)
    .build()
)
async for event in workflow.run("start", stream=True):
    if event.type == "output":
        print(event.data)
```

> 🏫 **En una institución educativa:** el **proceso de matrícula** es exactamente esto. Validar prerrequisitos → verificar cupo → registrar asignaturas → generar cargo económico → emitir comprobante. Cada paso depende del anterior y no tiene sentido paralelizarlo.

---

### ▸ 17 · Workflow concurrente (fan-out / fan-in)

**Concepto:** un ejecutor difunde el mismo mensaje a tres tareas que corren **a la vez**, y un cuarto espera a todas.
**Enseña:** `add_fan_out_edges`, `add_fan_in_edges` y **sincronización automática**.

```python
workflow = (
    WorkflowBuilder(start_executor=dispatcher, output_from=[renderer])
    .add_fan_out_edges(dispatcher, [totals_calc, client_prep, credit_checker])
    .add_fan_in_edges([dispatcher, totals_calc, client_prep, credit_checker], merger)
    .add_edge(merger, renderer)
    .build()
)

class ResultsMerger(Executor):
    @handler                              # ⚠️ recibe una LISTA, ya sincronizada
    async def merge(self, results: list[...], ctx: WorkflowContext[MergedResult]):
        for r in results:                 # el ORDEN no está garantizado:
            if isinstance(r, TotalsResult):   ...   # clasificar por TIPO
```

La demo **mide el paralelismo real**:
```
[FUSION] Fan-in completo: 4 mensajes recibidos juntos
   [TIEMPO] Bloque paralelo: 0.87s (en secuencia habria tardado 1.40s -> ahorro 0.53s)
```

> 🏫 **En una institución educativa:** al procesar una **solicitud de admisión**, consultar simultáneamente el expediente académico, la situación de ayuda financiera y la existencia de deudas pendientes. Son tres consultas independientes: hacerlas en serie triplica el tiempo de respuesta al postulante.

---

### ▸ 18 · Workflow con ramificación

**Concepto:** el camino depende de los datos. Equivalente a un `switch`/`case` dentro del grafo.
**Enseña:** `Case` / `Default`, evaluación **en orden**, y encadenamiento de decisiones.

```python
def es_alto_valor(decision: InvoiceDecision) -> bool:   # ⚠️ UN SOLO argumento
    return decision.decision_type == "high_value"

workflow = (
    WorkflowBuilder(start_executor=loader, output_from=[finalizer])
    .add_switch_case_edge_group(loader, [
        Case(condition=es_necesario_archivar, target=archive_handler),
        Case(condition=es_alto_valor,        target=high_value_handler),
        Case(condition=es_preferente,        target=preferred_handler),
        Default(target=standard_handler),          # red de seguridad
    ])
    .add_edge(high_value_handler, finalizer)       # convergencia
    .build()
)
```

> 💡 **Pruebe la rama de archivado:** procese **la misma factura dos veces**. La primera la crea; la segunda detecta que ya existe, la archiva con marca de tiempo y **vuelve a decidir**. El menú marca `[YA EXISTE -> se archivará]`.

> 🏫 **En una institución educativa:** el **enrutado de solicitudes estudiantiles**. Una solicitud de retiro de asignatura sigue un camino distinto según sea estudiante de pregrado, posgrado o becado; y si el plazo ya venció, primero pasa por una vía de excepción. La rama `Default` garantiza que ninguna solicitud se quede sin tramitar.

---

### ▸ 19 · Human-in-the-loop + checkpointing

**Concepto:** el workflow **se detiene de verdad**, devuelve el control, espera una respuesta humana y **reanuda** donde estaba.
**Enseña:** `ctx.request_info()`, `@response_handler`, reanudación por `request_id` y checkpoints en disco.

```python
class TaxConfirmation(Executor):
    @handler
    async def pedir(self, state: InvoiceState, ctx: WorkflowContext) -> None:
        await ctx.request_info(              # ⏸ DETIENE el workflow
            TaxConfirmationRequest(...), bool    # tipo de respuesta esperado
        )

    @response_handler                         # se empareja por TIPOS
    async def aplicar(self, original_request: TaxConfirmationRequest,
                      response: bool, ctx: WorkflowContext[InvoiceState]) -> None:
        state.tax_confirmed = response        # la respuesta MANDA

# Ciclo pausa → respuesta → reanudación
async for ev in workflow.run(factura, stream=True):
    if ev.type == "request_info":
        pendientes[ev.request_id] = ev.data
# ...preguntar al humano...
async for ev in workflow.run(responses=respuestas, stream=True):   # ⚠️ sin `message`
    ...
```

**La respuesta del usuario cambia el resultado** — compruébelo:

| Impuesto | Descuento | Total final |
|:---:|:---:|---:|
| ✅ | ✅ | **$6072.00** |
| ❌ | ❌ | **$6000.00** |
| ✅ | ❌ | **$6552.00** |

> 🏫 **En una institución educativa:** **aprobaciones que requieren firma humana**. Una solicitud de sobrecupo de créditos, una condonación de deuda o una excepción de prerrequisito no pueden automatizarse por completo: el sistema prepara el expediente, se detiene, espera la decisión del director de carrera y continúa. Los **checkpoints** permiten que el trámite sobreviva a un reinicio del servidor sin perder lo avanzado — clave en procesos de matrícula que duran días.

---

### ▸ 20 · Visualización de workflows

**Concepto:** dibujar y **analizar** grafos sin ejecutarlos.
**Enseña:** `WorkflowViz` e **introspección** del objeto `Workflow`.

**Visor:** de archivos de *.mmd
- https://mermaidviewer.com/

```python
viz = WorkflowViz(workflow)
Path("wf.mmd").write_text(viz.to_mermaid())   # Mermaid (Markdown, GitHub)
Path("wf.dot").write_text(viz.to_digraph())   # DOT (Graphviz)
viz.save_svg("wf.svg")                        # imagen (requiere Graphviz)

# Análisis REAL, interrogando al grafo:
workflow.get_executors_list()        # todos los ejecutores
workflow.get_start_executor()        # punto de entrada
workflow.get_output_executors()      # puntos de salida
workflow.input_types, workflow.output_types
```

Salida del análisis:
```
Ejecutores en el workflow (5):
  1. dispatcher             (punto de entrada)
  2. totals_calculator      (intermedio)
  3. client_preparer        (intermedio)
  4. merger                 (intermedio)
  5. renderer               (punto de salida)
```

> 💡 `to_mermaid()` y `to_digraph()` generan **texto** y no necesitan Graphviz. Graphviz solo hace falta para `save_png()` / `save_svg()` / `save_pdf()`. Pegue el `.mmd` en <https://mermaid.live> para verlo al instante.

> 🏫 **En una institución educativa:** **documentación para auditoría y acreditación**. Los procesos administrativos deben poder explicarse ante pares evaluadores. Generar el diagrama *desde el código* garantiza que el manual de procedimientos refleje lo que el sistema hace de verdad, y no lo que hacía hace tres años.

---

### ▸ 21 · Agentes de IA dentro del workflow

**Concepto:** cuatro ejecutores delegan su trabajo en un **agente de IA** especializado.
**Enseña:** que **un agente es un ejecutor más**; la topología del grafo no cambia.

```python
# UN cliente compartido; lo que distingue a los agentes son sus instrucciones
async with AzureCliCredential() as credential:
    client = FoundryChatClient(           # ⚠️ NO es context manager
        project_endpoint=PROJECT_ENDPOINT,
        model=MODEL_DEPLOYMENT,
        credential=credential,
    )
    agente = Agent(client, name="Analista", instructions=INSTRUCCIONES_ANALISTA)
    resultado = await agente.run(prompt)
    texto = resultado.text
```

La decisión del agente **cambia según los datos**:

| Factura | Decisión del agente |
|---|---|
| INV-001 ($6000, preferente, alto valor) | **PRIORIDAD** |
| INV-005 ($3300, estándar) | **ESTANDAR** |

> ⚠️ **Esta demo es diferente:** es la única que llama a un modelo real. Requiere `az login`, tarda bastante más (4 llamadas al modelo), **consume cuota** y sus respuestas **no son deterministas**.

> 🏫 **En una institución educativa:** **triaje de solicitudes de ayuda financiera o de casos estudiantiles**. Un agente analiza el expediente y sugiere un nivel de prioridad; otro propone la resolución; un tercero redacta la comunicación al estudiante en lenguaje claro; un cuarto elabora el resumen ejecutivo para el comité. **La decisión final sigue siendo humana** (combínelo con el patrón de la demo 19): la IA prepara y redacta, no resuelve sola.

---

## 🏫 Aplicación en una institución de educación superior con ERP Banner

> **Contexto.** *Ellucian Banner* es uno de los ERP más extendidos en educación superior. Organiza la operación en módulos —**Banner Student**, **Banner Finance**, **Banner Financial Aid**, **Banner Human Resources**, **Banner Advancement**— sobre una base de datos institucional compartida.
>
> Estos workflows **no reemplazan a Banner**: se sitúan **alrededor** de él, orquestando pasos que hoy suelen resolverse con procesos manuales, hojas de cálculo o scripts sueltos. Banner sigue siendo el **sistema de registro**; el workflow coordina, decide y comunica.

### Mapa de patrones → procesos institucionales

| Patrón (demo) | Proceso institucional | Módulo Banner implicado |
|---|---|---|
| **Secuencial** (16) | Matrícula: validar prerrequisitos → verificar cupo → registrar → generar cargo → emitir comprobante | Student + Finance |
| **Concurrente** (17) | Admisión: consultar en paralelo expediente, ayuda financiera y deuda pendiente | Student + Financial Aid + Finance |
| **Ramificado** (18) | Enrutado de solicitudes según tipo de estudiante, modalidad o plazo | Student |
| **HITL + checkpoint** (19) | Excepciones que exigen firma: sobrecupo, condonación, prerrequisito | Student + Finance |
| **Visualización** (20) | Documentar procesos para auditoría interna y acreditación | Transversal |
| **Agentes** (21) | Triaje y redacción asistida en casos estudiantiles y ayuda financiera | Financial Aid + Student |

### Un escenario completo: solicitud de reintegro académico

Combinando los seis patrones, un trámite real se vería así:

1. **Secuencial** — el estudiante inicia la solicitud; se recuperan sus datos y su situación académica.
2. **Concurrente** — se consultan **a la vez** su historial de notas, su estado financiero y sus sanciones previas. Tres consultas independientes, un solo tiempo de espera.
3. **Ramificado** — según la causa del retiro (académica, médica, económica) la solicitud toma una vía distinta, y `Default` recoge los casos atípicos para que ninguno se pierda.
4. **Agentes** — un agente redacta un resumen del caso para el comité, en lenguaje claro y sin jerga administrativa.
5. **HITL + checkpoint** — el comité **aprueba o rechaza**. El proceso puede durar semanas: los checkpoints permiten retomarlo exactamente donde quedó, aunque el servidor se reinicie.
6. **Visualización** — el diagrama del proceso se adjunta al expediente de acreditación, generado desde el código.

### Por qué encaja bien con Banner

- **Banner es transaccional; el workflow es procesal.** Banner registra el estado final; el workflow gobierna *cómo se llega* a él, con trazabilidad de cada paso.
- **La lógica de negocio queda fuera de la base de datos.** En estas demos vive en [`invoice_utils.py`](invoice_utils.py); en producción sería su capa de reglas institucionales — versionable, testeable y auditable, en vez de repartida en procedimientos almacenados.
- **El human-in-the-loop es la norma, no la excepción.** En el ámbito académico casi ningún trámite relevante se automatiza al 100 %: siempre hay una firma, un comité o una autoridad. El patrón de la demo 19 modela eso de forma explícita.
- **La IA asiste, no decide.** Los agentes de la demo 21 analizan, priorizan y redactan; la resolución la firma una persona.

> ⚠️ **Advertencia de alcance.** Este material es **un laboratorio educativo**, no una integración con Banner. No incluye conectores, ni acceso a su base de datos, ni cumplimiento normativo (FERPA / protección de datos, retención, auditoría). Cualquier uso real exige análisis de seguridad, control de accesos y validación con las áreas funcionales y de TI de la institución.

---

## 🧭 Componentes deprecados / eliminados (reporte MFA)

| Componente | Situación en 1.11.0 | Reemplazo vigente |
|---|---|---|
| `WorkflowOutputEvent`, `WorkflowStatusEvent` | 🔴 Eliminados | `WorkflowEvent` + `.type` |
| `RequestInfoExecutor`, `RequestInfoMessage` | 🔴 Eliminados | `ctx.request_info()` + `@response_handler` |
| `WorkflowBuilder.set_start_executor()` | 🔴 Eliminado | `WorkflowBuilder(start_executor=…)` |
| `WorkflowBuilder.with_checkpointing()` | 🔴 Eliminado | `WorkflowBuilder(checkpoint_storage=…)` |
| `Workflow.run_stream()` | 🔴 Eliminado | `run(..., stream=True)` |
| `ctx.set_shared_state()` / `get_shared_state()` | 🔴 Eliminados | Estado en el propio mensaje |
| `ChatAgent` | 🔴 Eliminado | `Agent` |
| `agent_framework.azure.AzureAIAgentClient` | 🔴 Eliminado | `FoundryChatClient` |
| Tipo de evento `"data"` | 🟡 **Deprecado** | Tipo `"intermediate"` |
| Omitir `output_from` en el builder | 🟡 **Deprecado** | Declararlo explícitamente |
| `MemoryContextProvider`, `FoundryEvals` | 🟡 Experimentales | *(no usados aquí)* |

> 📕 **La referencia de API de Learn está desfasada.** `learn.microsoft.com/python/api/agent-framework-core/...workflowbuilder` sigue documentando `set_start_executor`, `with_checkpointing` y `run_stream`, **que no existen en el paquete instalado**. La documentación **conceptual** (`/agent-framework/workflows/...`) sí coincide con 1.11.0. Ante la duda: **inspeccione el paquete del venv**.

---

## ⚠️ Notas técnicas y gotchas

Recopilación de los tropiezos reales encontrados durante la migración:

1. **El fan-in cambia el tipo del destino.** `add_fan_in_edges` **agrega** los mensajes: el destino recibe `list[T]`, no `T`. Si no lo declara así, `build()` falla con un `TypeCompatibilityError` cuyo mensaje parece decir que ambos tipos son idénticos.

2. **La lista del fan-in es heterogénea y su orden NO está garantizado.** Clasifique por `isinstance`, **nunca por índice**.

3. **Las condiciones de `Case` reciben UN solo argumento.** Con dos (`msg, ctx`) el framework registra `Error evaluating condition` y **manda todo por `Default` sin lanzar excepción**: un fallo silencioso.

4. **`ctx.set_state(clave, valor)` es SÍNCRONO.** Sin `await`, y ya no acepta un diccionario completo.

5. **`FoundryChatClient` NO es context manager.** Un `async with` sobre él falla con `missed __aexit__`. `AzureCliCredential` **sí** lo es.

6. **🔒 Checkpoints y pickle — trampa de seguridad.** `FileCheckpointStorage` serializa con *pickle* y al **leer** solo admite una lista blanca de tipos. Con tipos propios, los checkpoints **se escriben pero no se pueden leer**:
   ```
   Checkpoint deserialization blocked for type '__main__:InvoiceState'
   ```
   Se comprobó en la práctica: **6 archivos en disco y `list_checkpoints()` devolvía 1**. Solución:
   ```python
   FileCheckpointStorage(storage_path=..., allowed_checkpoint_types=[
       f"{__name__}:InvoiceState", f"{__name__}:TaxConfirmationRequest",
   ])
   ```

7. **Cree un workflow nuevo por cada ejecución independiente.** Una instancia de `Workflow` **conserva su estado** entre llamadas a `run()`.

8. **Los agentes responden en inglés si no se les pide lo contrario.** Las instrucciones de la demo 21 exigen explícitamente *"Responde SIEMPRE en español"*.

---

## 📊 Datos de prueba

[`data/invoices.csv`](data/invoices.csv) contiene **11 facturas** diseñadas para cubrir todas las combinaciones de reglas de negocio:

| Escenario | Facturas | Para qué sirve |
|---|---|---|
| Alto valor **+** preferente | INV-001, 003, 006 | Ambos descuentos acumulados |
| Alto valor **sin** ser preferente | **INV-010** | Solo descuento por volumen |
| Preferente **por debajo** del umbral | **INV-009** | Única que llega a la rama `PREFERRED` |
| Ni alto valor ni preferente | INV-002, 004, 005, 007, 008 | Rama `Default` |
| **Exactamente** en el umbral ($5000) | **INV-011** | 🎯 Caso de borde: valida `>=` frente a `>` |

> Los dos últimos casos se añadieron durante la migración: sin ellos, la rama `PREFERRED` de la demo 18 era **inalcanzable** y el límite del umbral quedaba sin comprobar.

### Artefactos generados

Ninguno está versionado; **borrarlos reinicia las demos**.

| Carpeta / archivo | Generado por |
|---|---|
| `output/` | 16, 17, 18, 19, 21 |
| `logs/invoice_workflow.log` | todas menos la 20 |
| `archive/` | 18 |
| `checkpoints_simple/` | 19 |
| `visualizations/` | 20 |

---

## 🗺️ Roadmap / pendientes

- [ ] Añadir `.gitignore` para `.env*`, `.venv/` y los artefactos generados.
- [ ] **Regenerar la clave de Azure OpenAI** presente en `.env03`.
- [ ] Traducir al español la salida de las demos de **Parte 1** y **Parte 2** (Parte 3 ya está).
- [ ] (Opcional) Instalar Graphviz para generar imágenes en la demo 20.
- [ ] (Opcional) Variante de la demo 21 con Azure OpenAI directo, para poder ejecutarla sin `az login`.
- [ ] (Opcional) Pruebas automatizadas de `invoice_utils.py` (es lógica pura, fácil de testear).

---

## ✍️ Autoría

**Fernando Valdés Herrera**

Proyecto **con fines educativos**: modernización del *Microsoft Agent Framework* (Parte 3 — Workflows). El código de las demos se basa en el tutorial original de la serie y fue actualizado a la API estable **core `1.11.0`**, documentando en cada paso las equivalencias entre la API beta y la vigente.

Bitácora detallada de la migración, decisión a decisión: [`Memory.md`](Memory.md).
Guía técnica para trabajar sobre este código: [`CLAUDE.md`](CLAUDE.md).

*Microsoft, Azure y Microsoft Agent Framework son marcas de Microsoft Corporation. Ellucian y Banner son marcas de Ellucian Company L.P. Este material no está afiliado ni respaldado por dichas empresas.*
