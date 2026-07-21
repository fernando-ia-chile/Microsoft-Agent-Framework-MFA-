# Microsoft Agent Framework — Parte 3 en C# · Workflows (.NET 10)

> Serie práctica de aprendizaje del **Microsoft Agent Framework (MFA)** sobre Azure.
> Esta **Parte 3 en C#** replica los 6 ejemplos de la versión Python (`Part-3/`), usando el
> paquete **`Microsoft.Agents.AI.Workflows` 1.13.0** sobre **.NET 10**, en un **único proyecto**.

**Autor:** Fernando Valdés Herrera
**Naturaleza:** material **con fines educativos**

---

## 📑 Tabla de contenidos

- [Descripción](#-descripción)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Requisitos e instalación](#-requisitos-e-instalación)
- [Configuración (appsettings03.json)](#-configuración-appsettings03json)
- [Cómo ejecutar](#-cómo-ejecutar)
- [Correspondencia Python ↔ C#](#-correspondencia-python--c)
- [Tabla comparativa de API: Python 1.11.0 ↔ .NET 1.13.0](#-tabla-comparativa-de-api-python-1110--net-1130)
- [Las aristas de C#: 8 diferencias que hay que conocer](#-las-aristas-de-c-8-diferencias-que-hay-que-conocer)
- [Los 6 ejemplos](#-los-6-ejemplos)
- [Aplicación en una institución de educación superior con ERP Banner](#-aplicación-en-una-institución-de-educación-superior-con-erp-banner)
- [Estado de verificación](#-estado-de-verificación)
- [Datos de prueba](#-datos-de-prueba)
- [Roadmap / pendientes](#-roadmap--pendientes)
- [Autoría](#-autoría)

---

## 🎯 Descripción

Un `Workflow` es un **grafo dirigido de ejecutores** que se orquestan entre sí. Los seis
ejemplos son variaciones del *mismo* proceso de negocio —generar una factura— y lo que cambia
entre ellos es la **topología del grafo**:

```
16 SECUENCIAL    A ─► B ─► C ─► D

17 CONCURRENTE   A ─┬─► B ─┐
                    ├─► C ─┼─► E ─► F
                    └─► D ─┘

18 RAMIFICADO    A ─┬─(caso 1)─► B ─┐
                    ├─(caso 2)─► C ─┼─► E
                    └─(defecto)─► D ─┘

19 HITL          A ─► [puerto] ─► B ─► [puerto] ─► C
                        ⏸              ⏸

20 VISUALIZA     (dibuja y analiza los grafos, no los ejecuta)

21 AGENTES       A ─► 🤖 ─► 🤖 ─► 🤖 ─► 🤖
```

Igual que en la versión de Python, **la lógica de negocio vive fuera de los ejecutores**:

```
Infrastructure/InvoiceUtils.cs   →  QUÉ se hace (leer, calcular, renderizar)
Examples/ExampleNN_*.cs          →  CÓMO se orquesta (topología del grafo)
```

---

## 📁 Estructura del proyecto

```
Parte3 -CSharp/
├── MFA.CSharp.Part3.csproj        Un solo proyecto para los 6 ejemplos
├── MFA.CSharp.Part3.slnx
├── Program.cs                     Menú interactivo (o `dotnet run -- 18`)
├── appsettings03.json             Configuración (equivale al .env03 de Python)
├── data/
│   └── invoices.csv               11 facturas — idéntico al de Python
├── Infrastructure/
│   ├── InvoiceUtils.cs            Lógica de negocio compartida
│   ├── AppConfig.cs               Carga de appsettings03.json
│   └── AzureAgentFactory.cs       Cliente y agentes (solo ejemplo 21)
└── Examples/
    ├── Example16_SequentialWorkflow.cs
    ├── Example17_ConcurrentWorkflow.cs
    ├── Example18_BranchingWorkflow.cs
    ├── Example19_InteractiveCheckpointing.cs
    ├── Example20_VisualizationWorkflow.cs
    └── Example21_AgentsInWorkflow.cs
```

---

## 📦 Requisitos e instalación

- **.NET SDK 10.0** o superior (probado con 10.0.302)
- Sistema operativo: probado en Windows 11 con PowerShell
- Solo para el ejemplo 21: un recurso de **Azure OpenAI** con un modelo desplegado

```powershell
cd "Parte3 -CSharp"
dotnet restore
dotnet build
```

### Paquetes NuGet

| Paquete | Versión | Para qué |
|---|---|---|
| `Microsoft.Agents.AI.Workflows` | `1.13.0` | **Motor de workflows** — el paquete central de esta parte |
| `Microsoft.Agents.AI.Workflows.Generators` | `1.13.0` | Generador del patrón `[MessageHandler]` (solo compilación) |
| `Microsoft.Agents.AI` | `1.13.0` | `AIAgent`, `ChatClientAgent` — ejemplo 21 |
| `Microsoft.Agents.AI.OpenAI` | `1.13.0` | Integración con OpenAI / Azure OpenAI |
| `Azure.AI.OpenAI` | `2.9.0-beta.1` | SDK de Azure OpenAI |
| `Microsoft.Extensions.AI` | `10.8.0` | `IChatClient`, `ChatOptions` |
| `Microsoft.Extensions.Configuration[.Json]` | `10.0.0` | Lectura de `appsettings03.json` |
| `Azure.Identity` | `1.17.0` | Credenciales de Azure |

> 💡 **A diferencia de Python, aquí no hay "trampa de dependencias".** En Python hay que evitar
> el meta-paquete `agent-framework` porque arrastra una versión incompatible; en NuGet los
> paquetes de MFA comparten versión (`1.13.0`) y se resuelven sin conflicto.

---

## 🔑 Configuración (appsettings03.json)

Equivale al `.env03` de Python. **Los ejemplos 16 a 20 no usan ningún LLM**: funcionan sin
tocar este archivo. Solo el **ejemplo 21** necesita credenciales reales.

```jsonc
{
  "AzureOpenAI": {                 // ← solo el ejemplo 21
    "Endpoint": "https://<recurso>.services.ai.azure.com",
    "ChatDeploymentName": "gpt-5.4-mini",
    "ApiKey": ""
  },
  "AzureAI": {                     // reservado (equivalente Foundry de Python)
    "ProjectEndpoint": "https://<recurso>.services.ai.azure.com/api/projects/<proyecto>",
    "ModelDeploymentName": "gpt-5.4-mini"
  },
  "Invoice": {                     // reglas de negocio (todas con valor por defecto)
    "TaxRate": 0.10,
    "HighValueThreshold": 5000.00,
    "HighValueDiscount": 0.05,
    "PreferredDiscount": 0.03,
    "CompanyName": "TechServices Inc.",
    "CompanyAddress": "123 Business St, Tech City, TC 12345"
  }
}
```

> ⚠️ **`Endpoint` debe ser SOLO la base**, sin `/openai/...`. El SDK añade su propia ruta; si
> incluye la completa obtendrá un **404**. Es el mismo tropiezo documentado en las Partes 1 y 2.

> 🔒 **Seguridad:** `.gitignore` excluye `appsettings*.local.json`. **No suba claves reales** al
> repositorio y regenere cualquiera que haya sido expuesta.

---

## ▶️ Cómo ejecutar

```powershell
# Menú interactivo con los 6 ejemplos
dotnet run

# O directamente uno concreto
dotnet run -- 16      # secuencial
dotnet run -- 19      # human-in-the-loop
```

Los artefactos (`output/`, `logs/`, `archive/`, `checkpoints/`, `visualizations/`) se generan
**junto al ejecutable**, en `bin/Debug/net10.0/`. Es consecuencia de resolver las rutas con
`AppContext.BaseDirectory`, que hace que los ejemplos funcionen igual con `dotnet run` que con
el binario publicado.

---

## 🔗 Correspondencia Python ↔ C#

Cada archivo tiene su gemelo. Los nombres siguen la convención de C# (PascalCase), como en la
Parte 2 del proyecto:

| Python (`Part-3/`) | C# (`Parte3 -CSharp/`) |
|---|---|
| `invoice_utils.py` | `Infrastructure/InvoiceUtils.cs` |
| `new_16_sequential_workflow.py` | `Examples/Example16_SequentialWorkflow.cs` |
| `new_17_concurrent_workflow.py` | `Examples/Example17_ConcurrentWorkflow.cs` |
| `new_18_branching_workflow.py` | `Examples/Example18_BranchingWorkflow.cs` |
| `new_19_interactive_checkpointing.py` | `Examples/Example19_InteractiveCheckpointing.cs` |
| `new_20_visualization_workflow.py` | `Examples/Example20_VisualizationWorkflow.cs` |
| `new_21_agents_in_workflow.py` | `Examples/Example21_AgentsInWorkflow.cs` |
| `.env03` | `appsettings03.json` |
| `requirements.txt` | `MFA.CSharp.Part3.csproj` |
| *(6 scripts sueltos)* | `Program.cs` (menú único) |

---

## 🔄 Tabla comparativa de API: Python 1.11.0 ↔ .NET 1.13.0

### Construcción del grafo

| Concepto | Python (`agent-framework-core`) | C# (`Microsoft.Agents.AI.Workflows`) |
|---|---|---|
| Constructor | `WorkflowBuilder(start_executor=x)` | `new WorkflowBuilder(x)` |
| Arista simple | `.add_edge(a, b)` | `.AddEdge(a, b)` |
| Cadena | `.add_chain([...])` | `.AddChain(...)` |
| Fan-out | `.add_fan_out_edges(s, [t1, t2])` | `.AddFanOutEdge(s, [t1, t2])` |
| Fan-in | `.add_fan_in_edges([s1, s2], t)` | `.AddFanInBarrierEdge([s1, s2], t)` |
| Switch | `.add_switch_case_edge_group(s, [Case(...), Default(...)])` | `.AddSwitch(s, sw => sw.AddCase<T>(pred, [t]).WithDefault([t]))` |
| Salida | `output_from=[x]` (constructor) | `.WithOutputFrom(x)` (fluida) |
| Nombre | `name="..."` (constructor) | `.WithName("...")` (fluida) |
| Construir | `.build()` | `.Build()` |

### Ejecutores

| Concepto | Python | C# |
|---|---|---|
| Definición | `class X(Executor)` + `@handler` | `partial class X : Executor` + `[MessageHandler]` |
| Función simple | `@executor(id="x")` | *(no existe: siempre clase)* |
| Enviar | `await ctx.send_message(m)` | `await context.SendMessageAsync(m, ct)` |
| Producir salida | `await ctx.yield_output(o)` | `await context.YieldOutputAsync(o, ct)` |
| **Declarar contrato** | `WorkflowContext[TSend]` / `[Never, TYield]` | `[MessageHandler(Send = [typeof(T)], Yield = [typeof(T)])]` |
| Estado en checkpoint | `ctx.set_state(k, v)` — **síncrono** | `await context.QueueStateUpdateAsync(k, v)` — **asíncrono** |

### Ejecución y eventos

| Concepto | Python | C# |
|---|---|---|
| Ejecutar en streaming | `workflow.run(msg, stream=True)` | `await InProcessExecution.RunStreamingAsync(wf, msg)` |
| Iterar eventos | `async for e in ...` | `await foreach (var e in run.WatchStreamAsync())` |
| **Discriminar evento** | `e.type == "output"` (cadena) | `e is WorkflowOutputEvent o` (**tipo**) |
| Evento de salida | `WorkflowEvent` con `.type` | `WorkflowOutputEvent` (clase propia) |
| Evento de fallo | `e.type == "failed"` | `e is ExecutorFailedEvent` |

### Human-in-the-loop

| Concepto | Python | C# |
|---|---|---|
| Mecanismo | `await ctx.request_info(datos, TipoResp)` **dentro** del ejecutor | `RequestPort.Create<TReq, TResp>(id)` — **nodo del grafo** |
| Cableado | *(implícito)* | `.AddEdge(exec, puerto)` y `.AddEdge(puerto, exec)` |
| Recibir respuesta | `@response_handler` en el mismo ejecutor | Handler de `TResp` en **otro** ejecutor |
| Responder | `run(responses={id: v})` — **segunda llamada** | `await run.SendResponseAsync(...)` — **sin salir del stream** |
| Evento | `e.type == "request_info"` | `e is RequestInfoEvent` |

### Checkpointing

| Concepto | Python | C# |
|---|---|---|
| Almacén | `FileCheckpointStorage(path)` | `new FileSystemJsonCheckpointStore(new DirectoryInfo(path))` |
| Activación | `WorkflowBuilder(checkpoint_storage=...)` | `RunStreamingAsync(wf, msg, checkpointManager)` |
| Gestor | *(implícito)* | `CheckpointManager.CreateJson(store)` |
| Serialización | **pickle** + lista blanca de tipos | **System.Text.Json** (sin lista blanca) |
| Listar | `list_checkpoints(workflow_name=...)` | `store.RetrieveIndexAsync(sessionId)` |

### Visualización y agentes

| Concepto | Python | C# |
|---|---|---|
| Mermaid | `WorkflowViz(wf).to_mermaid()` | `WorkflowVisualizer.ToMermaidString(wf)` — **estático** |
| DOT | `WorkflowViz(wf).to_digraph()` | `WorkflowVisualizer.ToDotString(wf)` — **estático** |
| Imagen | `viz.save_svg(...)` | *(no disponible: exporte el `.dot` con Graphviz)* |
| Introspección | `wf.get_executors_list()`, `wf.input_types` | `wf.ReflectExecutors()`, `wf.ReflectEdges()`, `wf.ReflectPorts()` |
| Agente | `Agent(client, instructions=...)` | `new ChatClientAgent(client, new ChatClientAgentOptions {...})` |
| Invocar | `await agent.run(prompt)` → `.text` | `await agent.RunAsync(prompt)` → `.Text` |

---

## ⚠️ Las aristas de C#: 8 diferencias que hay que conocer

Estas son las trampas reales encontradas al portar el proyecto. Ninguna aparece en la
documentación de forma evidente.

### 1. El patrón antiguo de ejecutor está **obsoleto**

`ReflectingExecutor<T>` + `IMessageHandler<T>` compilan, pero el compilador avisa:

```
warning CS0618: 'ReflectingExecutor<T>' está obsoleto: 'Use [MessageHandler] attribute
on methods in a partial class deriving from Executor. This type will be removed in a
future version.'
```

Este proyecto usa el patrón **vigente**, con **0 advertencias**:

```csharp
internal sealed partial class MiPaso(string id) : Executor(id)
{
    [MessageHandler(Send = [typeof(MiMensaje)])]
    public async ValueTask HandleAsync(Entrada msg, IWorkflowContext context,
                                       CancellationToken ct = default) { ... }
}
```

### 2. La clase **contenedora** también debe ser `partial`

El generador emite las clases anidadas como parciales. Si la clase que las contiene no lo es:

```
error CS0260: Falta el modificador parcial en la declaración de tipo
```

Por eso todos los ejemplos son `internal static partial class ExampleNN_...`.

### 3. Hay que **declarar** lo que el ejecutor envía y produce

`Send` y `Yield` no son decorativos. Si un ejecutor llama a `YieldOutputAsync` sin declarar
`Yield`, **compila pero falla en ejecución**:

```
Cannot output object of type String. Expecting one of [].
```

Es el equivalente al `WorkflowContext[Never, str]` de Python, pero verificado en runtime.

### 4. 🔴 El fan-in **NO agrega los mensajes** (la diferencia más importante)

| | Python | C# |
|---|---|---|
| Qué recibe el destino | **UNA lista** con todos los mensajes | **CADA mensaje por separado** |
| Firma del handler | `async def merge(self, results: list[...], ctx)` | un `[MessageHandler]` **por tipo** |
| ¿Hace falta estado? | **No** | **Sí**: acumular hasta tenerlos todos |

`AddFanInBarrierEdge` **sí sincroniza** (espera a todos), pero luego entrega los mensajes uno
a uno con su tipo original. Consecuencia práctica: en C# el fusionador vuelve a necesitar
campos de instancia, mientras que en Python se pudieron eliminar. Véalo en
[`Example17`](Examples/Example17_ConcurrentWorkflow.cs).

### 5. 🔴 El human-in-the-loop es un **nodo del grafo**, no una llamada

En Python se pide información *dentro* del ejecutor y la respuesta vuelve al mismo sitio. En
C# el `RequestPort` es un nodo que se cablea con aristas:

```csharp
.AddEdge(preparador, puertoImpuesto)      // preguntar
.AddEdge(puertoImpuesto, aplicaImpuesto)  // recibir la respuesta (¡otro ejecutor!)
```

Y **no hace falta reanudar**: se responde con `run.SendResponseAsync(...)` sin salir del mismo
`await foreach`. En Python hay que hacer una segunda llamada con `run(responses=...)`.

### 6. Los eventos se discriminan **por tipo**, no por cadena

```csharp
if (evt is WorkflowOutputEvent salida)  { ... }   // C#: el compilador valida
```
```python
if event.type == "output":                        # Python: cadena, sin validación
```

Curiosamente, `WorkflowOutputEvent` **existe en .NET** aunque fue **eliminado** de Python
1.11.0 — el mismo nombre, historia opuesta.

### 7. `decimal` en vez de `float` para el dinero

Python usa `float` (binario, con error de redondeo). C# ofrece `decimal`, de base 10 y pensado
para importes. Este proyecto usa `decimal` en todo el cálculo: es lo correcto en un dominio
financiero, y el resultado coincide al céntimo con la versión de Python.

### 8. Cultura invariante obligatoria

En una máquina con configuración regional española, `decimal.Parse("150.00")` interpreta el
punto como separador de miles. Todo el parseo y formateo de `InvoiceUtils` usa
`CultureInfo.InvariantCulture` para que el CSV se lea igual en cualquier equipo.

> 💡 **Ventaja neta de C#:** el `dict[str, float]` sin tipar de Python (`totals['tax']`) aquí es
> un `record InvoiceTotals` con propiedades. Un error de nombre se detecta al compilar, no en
> producción. Lo mismo con el `enum TipoDecision` del ejemplo 18, que en Python son cadenas.

---

## 📚 Los 6 ejemplos

### ▸ 16 · Workflow secuencial

Cadena lineal de 5 pasos. Enseña el ejecutor básico y el contrato de la arista.

```csharp
Workflow workflow = new WorkflowBuilder(cargar)
    .AddEdge(cargar, leer)
    .AddEdge(leer, calcular)
    .AddEdge(calcular, renderizar)
    .AddEdge(renderizar, guardar)
    .WithOutputFrom(guardar)
    .Build();

StreamingRun run = await InProcessExecution.RunStreamingAsync(workflow, "start");
await foreach (WorkflowEvent evt in run.WatchStreamAsync())
    if (evt is WorkflowOutputEvent salida) Console.WriteLine(salida.Data);
```

### ▸ 17 · Workflow concurrente (fan-out / fan-in)

Tres tareas en paralelo + barrera de sincronización. **Mide el paralelismo real:**

```
[FUSION] Fan-in completo: llegaron los 4 mensajes
   [TIEMPO] Bloque paralelo: 0,84s (en secuencia habria tardado 1,40s -> ahorro 0,56s)
```

### ▸ 18 · Workflow con ramificación

`AddSwitch` con casos evaluados en orden y una rama por defecto:

```csharp
.AddSwitch(cargador, sw => sw
    .AddCase<DecisionFactura>(EsNecesarioArchivar, [archivador])
    .AddCase<DecisionFactura>(EsAltoValor,        [altoValor])
    .AddCase<DecisionFactura>(EsPreferente,       [preferente])
    .WithDefault([estandar]))
```

> 💡 Procese **la misma factura dos veces** para ver la rama de archivado: la primera la crea,
> la segunda la archiva y **vuelve a decidir**. El menú marca `[YA EXISTE -> se archivará]`.

### ▸ 19 · Human-in-the-loop + checkpointing

El workflow se detiene de verdad y espera una decisión humana. **La respuesta cambia el total:**

| Impuesto | Descuento | Total final |
|:---:|:---:|---:|
| ✅ | ✅ | **$6072.00** |
| ❌ | ❌ | **$6000.00** |
| ✅ | ❌ | **$6552.00** |

### ▸ 20 · Visualización

Genera `.mmd` (Mermaid) y `.dot` (Graphviz) de los tres patrones, y analiza el grafo por
introspección — sin ejecutarlo:

```
Ejecutores en el workflow (5):
  1. calculadora_totales      (intermedio)
  2. dispatcher               (punto de entrada)
  3. fusionador               (intermedio)
  4. preparador_cliente       (intermedio)
  5. renderizador             (punto de salida)
```

### ▸ 21 · Agentes de IA en el workflow

Cuatro agentes especializados (analista → decisor → comunicador → resumidor) compartiendo un
único `IChatClient`. **Es el único que necesita credenciales.**

---

## 🏫 Aplicación en una institución de educación superior con ERP Banner

> *Ellucian Banner* organiza la operación académica en módulos —**Banner Student**,
> **Banner Finance**, **Banner Financial Aid**, **Banner HR**— sobre una base de datos común.
> Estos workflows **no reemplazan a Banner**: se sitúan **alrededor** de él, orquestando pasos
> que hoy suelen resolverse con procesos manuales o scripts sueltos.

| Patrón (ejemplo) | Proceso institucional | Módulo Banner |
|---|---|---|
| **Secuencial** (16) | Matrícula: prerrequisitos → cupo → registro → cargo → comprobante | Student + Finance |
| **Concurrente** (17) | Admisión: expediente + ayuda financiera + deuda, en paralelo | Student + Financial Aid |
| **Ramificado** (18) | Enrutado de solicitudes por tipo de estudiante o plazo | Student |
| **HITL + checkpoint** (19) | Excepciones con firma: sobrecupo, condonación, prerrequisito | Student + Finance |
| **Visualización** (20) | Documentar procesos para auditoría y acreditación | Transversal |
| **Agentes** (21) | Triaje y redacción asistida, **con decisión humana** | Financial Aid |

### ¿Por qué C# y no Python, en este contexto?

Muchas instituciones con Banner ya tienen equipos y servidores **.NET** para sus integraciones.
Frente a Python, esta versión aporta:

- **Tipado estático:** un cambio en la estructura de datos rompe la compilación, no la
  ejecución en producción a mitad de un periodo de matrícula.
- **`decimal` nativo:** cálculo financiero sin error de coma flotante — relevante cuando se
  emiten cargos reales a estudiantes.
- **Un solo binario desplegable:** `dotnet publish` produce un artefacto autocontenido, más
  fácil de gobernar en un entorno con control de cambios estricto.
- **Integración natural** con servicios de Windows, IIS y el ecosistema Microsoft que ya
  rodea a muchas instalaciones de Banner.

> ⚠️ **Advertencia de alcance.** Este material es **un laboratorio educativo**, no una
> integración con Banner. No incluye conectores, ni acceso a su base de datos, ni cumplimiento
> normativo (FERPA / protección de datos, retención, auditoría). Cualquier uso real exige
> análisis de seguridad, control de accesos y validación con las áreas funcionales y de TI.

---

## ✅ Estado de verificación

| # | Ejemplo | Compila | Probado end-to-end | Resultado |
|:-:|---|:---:|:---:|---|
| 16 | Secuencial | ✅ | ✅ | Total **$6,072.00** (idéntico a Python) |
| 17 | Concurrente | ✅ | ✅ | Paralelismo **0,84 s** vs 1,40 s secuenciales |
| 18 | Ramificación | ✅ | ✅ | **4 ramas** probadas, incluido el re-enrutado tras archivar |
| 19 | HITL + checkpoints | ✅ | ✅ | 4 casos: **$6072 / $6000 / $6552 / $3630** · 7 checkpoints |
| 20 | Visualización | ✅ | ✅ | 6 archivos generados (3 `.mmd` + 3 `.dot`) |
| 21 | Agentes de IA | ✅ | ⚠️ **No probado con modelo real** | Verificado solo el aviso por falta de credenciales |

**Compilación limpia: 0 errores, 0 advertencias.**

> ⚠️ **Sobre el ejemplo 21:** las credenciales fueron retiradas de la configuración antes de
> poder ejecutarlo contra Azure. Su equivalente en Python **sí** se verificó end-to-end
> (decisiones PRIORIDAD y ESTANDAR según la factura). Al añadir sus credenciales en
> `appsettings03.json`, este ejemplo debería comportarse igual; **queda pendiente de
> confirmación**.

Los totales de los ejemplos 16, 17 y 19 **coinciden al céntimo** con la versión de Python, lo
que valida que el port del cálculo de negocio es correcto.

---

## 📊 Datos de prueba

[`data/invoices.csv`](data/invoices.csv) es **idéntico al de Python**: 11 facturas que cubren
todas las combinaciones de reglas.

| Escenario | Facturas | Para qué sirve |
|---|---|---|
| Alto valor **+** preferente | INV-001, 003, 006 | Ambos descuentos acumulados |
| Alto valor **sin** ser preferente | INV-010 | Solo descuento por volumen |
| Preferente **por debajo** del umbral | INV-009 | Única que llega a la rama preferente |
| Ni alto valor ni preferente | INV-002, 004, 005, 007, 008 | Rama por defecto |
| **Exactamente** en el umbral ($5000) | INV-011 | 🎯 Caso de borde: valida `>=` frente a `>` |

---

## 🗺️ Roadmap / pendientes

- [ ] **Probar el ejemplo 21 contra un modelo real** y confirmar que las decisiones del agente
      varían según la factura, como en la versión de Python.
- [ ] (Opcional) Variante del ejemplo 21 con **Azure AI Foundry**, para igualar exactamente el
      enfoque de Python (allí usa `FoundryChatClient` + `az login`).
- [ ] (Opcional) Pruebas unitarias de `InvoiceUtils.cs` — es lógica pura, fácil de testear con
      xUnit, y no existe equivalente en la versión de Python.
- [ ] (Opcional) Reanudación desde un checkpoint concreto con
      `InProcessExecution.ResumeStreamingAsync(...)`, que la versión de Python no demuestra.
- [ ] (Opcional) Exportar los diagramas a imagen instalando Graphviz (`dot -Tpng`).

---

## ✍️ Autoría

**Fernando Valdés Herrera**

Proyecto **con fines educativos**: réplica en **C# / .NET 10** de la Parte 3 (Workflows) de la
serie sobre el *Microsoft Agent Framework*, originalmente desarrollada en Python. Documenta en
cada paso las equivalencias y las diferencias reales entre ambas plataformas.

Versión original en Python, con su bitácora de migración: [`../Part-3/`](../Part-3/)

*Microsoft, Azure y Microsoft Agent Framework son marcas de Microsoft Corporation. Ellucian y
Banner son marcas de Ellucian Company L.P. Este material no está afiliado ni respaldado por
dichas empresas.*
