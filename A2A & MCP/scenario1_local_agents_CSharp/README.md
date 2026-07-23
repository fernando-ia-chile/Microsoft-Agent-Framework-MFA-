# 🤖 Escenario 1 (C#) — Agentes locales con MCP y A2A

> Tres agentes de IA que se reparten el trabajo, hablan entre ellos y usan herramientas reales.
> Todo corriendo en tu máquina, con **Microsoft Agent Framework para .NET**, **MCP** y **A2A**.

```
        👤 "¿Qué tiempo hace en Tokio? Guárdalo en un archivo"
                              │
                              ▼
                    ┌───────────────────┐
                    │   COORDINADOR     │  ← decide quién hace qué
                    └─────────┬─────────┘
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌───────────────┐   ┌───────────────┐
            │ INVESTIGACIÓN │   │   EJECUTOR    │
            └───────┬───────┘   └───────┬───────┘
                    ▼                   ▼
            🌍 API del clima      📂 Sistema de archivos
```

> 💡 Este proyecto es el **gemelo en C#** del escenario en Python. Misma arquitectura,
> mismos conceptos, mismas herramientas — implementado con el ecosistema .NET.

---

## 🎯 ¿Qué vas a aprender aquí?

Este proyecto es un laboratorio didáctico. Al terminarlo entenderás **tres conceptos** que hoy son la base de cualquier sistema de agentes:

| Concepto | En una frase | Dónde lo ves |
|---|---|---|
| **MFA** (Microsoft Agent Framework) | La librería que convierte un modelo de lenguaje en un *agente* con instrucciones y herramientas | `AsAIAgent(...)` en los tres agentes |
| **MCP** (Model Context Protocol) | El "USB-C" de las herramientas: un estándar para que cualquier agente use cualquier herramienta | `McpServers/` |
| **A2A** (Agent-to-Agent) | Cómo un agente le delega trabajo a otro | `Agents/CoordinatorAgent.cs` |

### Lo elemental, en 60 segundos

**Un agente** = un modelo de lenguaje + unas instrucciones + unas herramientas.
El modelo no ejecuta nada: *decide* qué herramienta llamar, y el framework la ejecuta por él.

**MCP** resuelve un problema real: antes, cada herramienta se programaba a medida para cada agente. Con MCP escribes el servidor **una sola vez** y lo puede usar tu agente, Claude Desktop, VS Code o cualquier cliente compatible. El servidor **publica** sus herramientas y el cliente las **descubre** al conectarse — nadie escribe la lista a mano.

**A2A** es lo mismo pero entre agentes: en vez de un agente gigante que lo sabe todo, tienes varios especialistas y un coordinador que reparte. Igual que un equipo de personas.

### 🔑 La ventaja de C#: el contrato es del compilador

En este proyecto los tres agentes implementan el mismo interfaz:

```csharp
public interface IAgenteA2A : IAsyncDisposable
{
    string AgenteId { get; }
    Task<RespuestaA2A> ManejarMensajeAsync(MensajeA2A mensaje, CancellationToken ct = default);
}
```

Por eso el Coordinador puede delegar en cualquiera de ellos **sin conocer su implementación**. En Python esto era una convención (todos tenían un método con el mismo nombre); aquí el **compilador la hace obligatoria**. Si un agente no cumple el contrato, el proyecto no compila.

---

## 🏗️ Arquitectura

```
┌────────────────────────────────────────────────────────────┐
│                      Entorno local                         │
│                                                            │
│                       👤 Usuario                           │
│                           │                                │
│                           ▼                                │
│                 ┌───────────────────┐                      │
│                 │  Agente 2         │                      │
│                 │  COORDINADOR      │  (decide y delega)   │
│                 └─────────┬─────────┘                      │
│                           │ A2A                            │
│             ┌─────────────┴─────────────┐                  │
│             ▼                           ▼                  │
│    ┌─────────────────┐        ┌──────────────────┐         │
│    │   Agente 1      │        │   Agente 3       │         │
│    │   INVESTIGACIÓN │        │   EJECUTOR       │         │
│    └────────┬────────┘        └─────────┬────────┘         │
│             │ MCP (stdio)               │ MCP (stdio)      │
│             ▼                           ▼                  │
│    ┌─────────────────┐        ┌──────────────────┐         │
│    │ Servidor MCP    │        │ Servidor MCP     │         │
│    │ Clima           │        │ Archivos         │         │
│    │ (subproceso)    │        │ (subproceso)     │         │
│    └────────┬────────┘        └─────────┬────────┘         │
└─────────────┼───────────────────────────┼──────────────────┘
              ▼                           ▼
     🌍 API Open-Meteo            📂 agent_workspace/
```

**Los tres agentes usan Azure OpenAI como cerebro.** Los servidores MCP son *proyectos ejecutables independientes*: el agente los lanza como **subprocesos** y habla con ellos por entrada/salida estándar (stdio). **No abren ningún puerto de red.**

---

## 🚀 Puesta en marcha

### Requisitos

- **.NET SDK 10.0 o superior** (`dotnet --version`)
- Una cuenta de **Azure OpenAI** con un modelo desplegado
- No necesitas clave para el clima: la API de Open-Meteo es gratuita 🎉

### 1. Compilar

```powershell
cd scenario1_local_agents_CSharp
dotnet build
```

> ⚠️ **Compila la solución completa antes de ejecutar.** El agente lanza los servidores MCP como procesos aparte, así que necesita que sus DLL existan. El `.csproj` del Host ya fuerza esa dependencia con `ReferenceOutputAssembly="false"`: se compilan, pero no se referencian sus tipos.

### 2. Configurar credenciales

Crea `Scenario1.Host/appsettings.Development.json` (está en `.gitignore`, tus claves nunca se suben):

```json
{
  "AZURE_OPENAI_ENDPOINT": "https://TU-RECURSO.services.ai.azure.com",
  "AZURE_OPENAI_API_KEY": "tu-clave",
  "AZURE_OPENAI_DEPLOYMENT_NAME": "nombre-de-tu-deployment",
  "AZURE_OPENAI_API_VERSION": "preview",
  "LOG_LEVEL": "Warning"
}
```

**Son las mismas variables que el `.env` del proyecto Python**, en formato JSON. El orden de prioridad es:

```
appsettings.json  <  appsettings.Development.json  <  variables de entorno
   (ejemplo)              (tus claves)                    (CI/despliegue)
```

> ⚠️ **El error más común:** `AZURE_OPENAI_ENDPOINT` debe ser **solo la base**, sin `/openai/...` al final. La librería añade la ruta por su cuenta. Si la incluyes, obtendrás un `404`.

### 3. Ejecutar

```powershell
dotnet run --project Scenario1.Host
```

---

## 🧩 Ejecutar por piezas (recomendado para aprender)

El Host lo lanza todo junto, pero **cada pieza es un proyecto independiente**. Esta progresión es la mejor forma de entender el sistema: empieza abajo y sube.

### Nivel 1 · Solo el servidor MCP 🔌

Un servidor MCP no es un programa interactivo: se queda esperando mensajes por stdin. Si lo lanzas directo, **parecerá que se cuelga — y es correcto**:

```powershell
dotnet run --project McpServers/Scenario1.WeatherServer     # Ctrl+C para salir
```

Verás sus mensajes de arranque (que van a **stderr**, nunca a stdout) y luego silencio: está esperando protocolo.

Lo interesante es **preguntarle qué sabe hacer**, que es justo lo que hace un agente al conectarse. Con el *Inspector* oficial de MCP:

```powershell
npx @modelcontextprotocol/inspector dotnet run --project McpServers/Scenario1.WeatherServer
```

Se abre un navegador donde puedes ver las herramientas, sus esquemas, sus anotaciones y **probarlas a mano, sin ninguna IA de por medio**.

> 💡 **Lo que acabas de comprobar:** el servidor MCP es código C# normal y corriente. No necesita IA para funcionar. La IA solo decide *cuándo* llamarlo.

### Nivel 2 · Los agentes conectados a MCP 🤖

```powershell
dotnet run --project Scenario1.Host
```

Al arrancar verás el descubrimiento por protocolo:

```
🔌 Abriendo las sesiones MCP de los agentes...
   🔌 Conectando por MCP (stdio) con Scenario1.WeatherServer.dll...
   ✅ MCP conectado. Herramientas descubiertas: get_forecast, get_weather, get_alerts
   🔌 Conectando por MCP (stdio) con Scenario1.FileOperationsServer.dll...
   ✅ MCP conectado. Herramientas descubiertas: list_files, delete_file, write_file, file_info, read_file
```

Esa lista **no está escrita en el código del agente**: llega por el protocolo.

### Nivel 3 · A2A sin ningún LLM decidiendo 📡

Dentro del programa, escribe:

```
a2a-directo
```

Manda mensajes A2A **saltándose al Coordinador**: mensaje directo al Investigador, encadenado a mano al Ejecutor, y ping a los tres. Verás el protocolo desnudo.

### Nivel 4 · El sistema completo 🎬

Escribe una pregunta normal y el Coordinador decidirá **él solo** a quién delegar y en qué orden:

```
¿Qué tiempo hace en Tokio, Japón? Guárdalo en informe_tokio.txt
```

| Progresión | Qué añade |
|---|---|
| 1 · Servidor MCP | Herramientas, sin IA |
| 2 · Agentes + MCP | El modelo elige la herramienta |
| 3 · `a2a-directo` | El protocolo A2A sin LLM |
| 4 · Flujo completo | Un agente delega en otros |

---

## 🎮 Comandos del modo interactivo

| Comando | Qué hace | ¿Gasta tokens? |
|---|---|---|
| *(tu pregunta)* | Ejecuta el flujo multiagente completo | ✅ Sí |
| `demo` | Tres ejemplos automáticos encadenados | ✅ Sí |
| `a2a-directo` | **Mensajes A2A sin Coordinador**, sin ningún LLM decidiendo | ✅ Sí |
| `a2a` | Explica el protocolo y la estructura del mensaje | ❌ No |
| `ciudades` | Ciudades de ejemplo por región | ❌ No |
| `arquitectura` | Vuelve a mostrar el diagrama | ❌ No |
| `ayuda` | Ayuda de uso | ❌ No |
| `salir` | Termina y cierra las sesiones MCP | — |

### ⭐ El comando estrella: `a2a-directo`

Compáralo con una pregunta normal y verás la diferencia entre **un guion escrito a mano** y **una orquestación decidida por el modelo**. Mismo transporte, misma estructura de mensaje: cambia quién decide.

---

## 🔬 Anatomía de una ejecución

Cuando escribes *"¿Qué tiempo hace en Tokio? Guárdalo en un archivo"*, ocurre esto:

```
Program.cs             → 1 sola llamada, no decide nada
  └── COORDINADOR (LLM)      ¿investigar? ¿guardar? ¿en qué orden?
        ├── INVESTIGACIÓN (LLM)   ¿get_weather, get_forecast o get_alerts?
        │      └── MCP → WeatherServer → 🌍 Open-Meteo
        └── EJECUTOR (LLM)        ¿write_file, read_file, list_files...?
               └── MCP → FileOperationsServer → 📂 disco
```

**Son tres bucles de modelo anidados, no un guion secuencial.**

Y ese `Pasos: 2/2` que ves al final **no es un plan previo**: la lista `_pasos` empieza vacía y se rellena *dentro* de las herramientas, según lo que el modelo haya decidido hacer.

- Preguntas solo el clima → `1/1`
- Clima + guardar → `2/2`
- Escribes "hola" → `0/0` y responde directamente

Nadie programó esos tres casos. 🎩

---

## 💼 ¿Y esto para qué sirve en el mundo real?

El clima y los archivos son solo la excusa. **El patrón es lo que vale.** Cambia las herramientas y tienes otra cosa:

### Sustituye el servidor MCP y cambia de dominio

| Si cambias `get_weather` por… | Obtienes |
|---|---|
| `ConsultarStock(sku)` | Un agente de inventario que responde en lenguaje natural |
| `BuscarCliente(rut)` | Un asistente de CRM que cruza datos de varios sistemas |
| `ConsultarBd(sql)` | Un analista que responde preguntas sobre tu base de datos |
| `EstadoTicket(id)` | Un agente de soporte que consulta y actualiza incidencias |
| `LeerCorreos(filtro)` | Un clasificador que archiva y resume tu bandeja |

El servidor de archivos ya te sirve tal cual para **generar informes**.

### Casos concretos que puedes montar con lo que ya está aquí

- 📊 **Informe diario automático**: agente que consulta tus indicadores, los redacta y los guarda cada mañana.
- 🧾 **Procesador de documentos**: uno lee y extrae datos, otro valida, otro archiva. El patrón de tres agentes tal cual.
- 🔍 **Investigador interno**: busca en la documentación de tu empresa y redacta un resumen con fuentes.
- 📨 **Triaje de solicitudes**: el Coordinador clasifica y deriva al especialista adecuado — exactamente lo que hace aquí.
- 🏭 **Monitor con alertas**: `get_alerts` ya demuestra el patrón de umbrales; cámbialo por tus sensores o tus SLA.

### El patrón "coordinador + especialistas"

Es la razón de fondo para usar varios agentes en vez de uno solo:

| Ventaja | Por qué |
|---|---|
| **Instrucciones cortas** | Un agente con 40 herramientas se confunde; tres con 5 cada uno, no |
| **Piezas reemplazables** | Cambias el Ejecutor sin tocar los demás — el interfaz lo garantiza |
| **Permisos separados** | Solo el Ejecutor toca el disco; el Investigador no puede |
| **Depuración simple** | Sabes qué agente falló y lo pruebas por separado |

### 🎁 Bonus: usa tu servidor MCP en Claude Desktop

Esta es la gracia real de MCP: **el servidor que escribiste aquí funciona en otros clientes sin tocar una línea**. En la configuración de Claude Desktop:

```json
{
  "mcpServers": {
    "clima": {
      "command": "dotnet",
      "args": [
        "C:\\ruta\\a\\scenario1_local_agents_CSharp\\McpServers\\Scenario1.WeatherServer\\bin\\Debug\\net10.0\\Scenario1.WeatherServer.dll"
      ]
    }
  }
}
```

Escribes la herramienta una vez, la usas en todas partes. Eso es el estándar.

---

## 📁 Estructura del proyecto

```
scenario1_local_agents_CSharp/
├── Scenario1.slnx                     🧩 Solución (formato nuevo de .NET 10)
├── Scenario1.Host/                    🎬 Programa principal
│   ├── Program.cs                        Punto de entrada + interfaz interactiva
│   ├── Orquestador.cs                    Ciclo de vida MCP y flujo completo
│   ├── Configuracion.cs                  Carga de appsettings y rutas
│   ├── appsettings.json                  🔑 Variables (mismas que el .env de Python)
│   ├── A2A/
│   │   └── MensajeA2A.cs                 📡 Contrato: mensaje, respuesta e IAgenteA2A
│   └── Agents/
│       ├── AgenteConMcp.cs               Base común: conexión MCP + agente MFA
│       ├── ResearchAgent.cs              🔍 Investigación — MCP de clima
│       ├── CoordinatorAgent.cs           🧠 Coordinador — delega por A2A
│       └── ExecutorAgent.cs              ⚙️  Ejecutor — MCP de archivos
├── McpServers/
│   ├── Scenario1.WeatherServer/       🌍 3 herramientas (clima, pronóstico, avisos)
│   └── Scenario1.FileOperationsServer/📂 5 herramientas (leer, escribir, listar…)
└── agent_workspace/                   📦 Salida de los agentes (se crea sola)
```

> 📖 **El código está comentado paso a paso.** Cada archivo abre con un mapa del flujo de ejecución (`[1]`, `[2]`, `[3]`…) y los comentarios están clasificados: `⚙️ MFA`, `🔌 MCP`, `📡 A2A`, `🔒 Seg.`, `🔧 Infra`. Puedes seguir la ejecución leyendo los números en orden.

---

## 🧰 Equivalencias Python ↔ C#

Si vienes del proyecto gemelo en Python, este es el mapa:

| Python | C# / .NET |
|---|---|
| `agent-framework-core` | `Microsoft.Agents.AI` |
| `agent-framework-openai` | `Microsoft.Agents.AI.OpenAI` + `Azure.AI.OpenAI` |
| `mcp` (SDK Python) | `ModelContextProtocol` |
| `python-dotenv` + `.env` | `Microsoft.Extensions.Configuration` + `appsettings.json` |
| `httpx` | `HttpClient` (viene en el runtime) |
| `pydantic.BaseModel` | `record` + `[Description]` |
| `OpenAIChatClient(...)` | `new AzureOpenAIClient(...).GetChatClient(...)` |
| `Agent(client, instructions, tools=[...])` | `chatClient.AsAIAgent(instructions, name, tools: [...])` |
| `agent.run(x, stream=True)` | `agent.RunStreamingAsync(x)` |
| `MCPStdioTool(command=..., args=[...])` | `new StdioClientTransport(new StdioClientTransportOptions {...})` |
| `await tool.connect()` | `await McpClient.CreateAsync(transporte)` |
| `tool.functions` | `await cliente.ListToolsAsync()` |
| `@mcp.tool(annotations=ToolAnnotations(...))` | `[McpServerTool(ReadOnly=…, Destructive=…)]` |
| `FastMCP(nombre, instructions=…)` | `AddMcpServer(o => o.ServerInstructions = …)` |
| `mcp.run(transport="stdio")` | `.WithStdioServerTransport()` |
| Convención `handle_message` | **Interfaz `IAgenteA2A`** (obligatorio, lo verifica el compilador) |

> ℹ️ **Nota sobre A2A:** en Python existe el paquete `agent-framework-a2a` (en beta) para el protocolo A2A remoto sobre HTTP. **No hay equivalente publicado en NuGet todavía.** Igual que en el proyecto Python, aquí la delegación entre agentes se implementa con herramientas que hablan un contrato de mensajes propio — que es exactamente lo que hace visible el mecanismo en clase.

---

## 🧯 Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `No se encontró el servidor MCP` | Faltan los DLL de los servidores | `dotnet build` en la raíz de la solución |
| `404` al llamar al modelo | `AZURE_OPENAI_ENDPOINT` incluye `/openai/...` | Deja **solo la base** de la URL |
| Emojis rotos en consola | Windows usa cp1252 | Ya resuelto (`Console.OutputEncoding = UTF8`) |
| El cliente MCP corta la conexión | Algo escribió en **stdout** del servidor | En stdio, **stdout es el canal del protocolo**: todo log va a `stderr` |
| El servidor "se cuelga" al ejecutarlo | Es lo normal: espera mensajes por stdin | Úsalo desde el Host, o inspecciónalo (Nivel 1) |
| Responde en inglés | Faltan instrucciones de idioma | Las instrucciones deben pedir el español **explícitamente** |

### 🚨 La trampa número uno de MCP

En transporte stdio, **stdout ES el canal JSON-RPC**. Un simple `Console.WriteLine` en el servidor rompe el protocolo. Por eso en ambos servidores verás:

```csharp
builder.Logging.AddConsole(opciones =>
{
    opciones.LogToStandardErrorThreshold = LogLevel.Trace;  // TODO el log a stderr
});

Console.Error.WriteLine("🌤️  Servidor MCP de Clima iniciando...");  // nunca Console.WriteLine
```

---

## 📖 Glosario rápido

| Término | Qué es |
|---|---|
| **Agente** | Modelo + instrucciones + herramientas |
| **Herramienta (tool)** | Función que el modelo puede pedir que se ejecute |
| **stdio** | Transporte MCP por entrada/salida estándar; el servidor es un subproceso |
| **Descubrimiento** | El cliente pregunta al servidor qué herramientas tiene, en vez de tenerlas escritas |
| **Salida estructurada** | La herramienta devuelve un objeto con esquema, no texto suelto (`UseStructuredContent`) |
| **Anotaciones** | Pistas sobre la herramienta: `ReadOnly`, `Destructive`, `Idempotent`, `OpenWorld` |
| **Delegación A2A** | Un agente pide trabajo a otro mediante un mensaje con formato acordado |

### 🎯 Dos detalles con miga

**`Destructive = true`** en `delete_file` es la pista que permite exigir **aprobación humana** antes de ejecutar la herramienta. Conecta directamente con el patrón *human-in-the-loop*.

**`OpenWorld`** contrasta los dos servidores, y ese contraste es didáctico:
- Archivos → `false`: espacio local y aislado.
- Clima → `true`: consulta Open-Meteo, puede fallar por red, y su resultado cambia con el tiempo aunque los argumentos sean idénticos.

---

## 🧪 Tecnologías

| Componente | Versión |
|---|---|
| .NET SDK | 10.0 |
| `Microsoft.Agents.AI` | 1.15.0 |
| `Microsoft.Agents.AI.OpenAI` | 1.15.0 |
| `Azure.AI.OpenAI` | 2.1.0 |
| `ModelContextProtocol` | 1.4.1 |
| `Microsoft.Extensions.Configuration` | 10.0.10 |

Datos meteorológicos: [Open-Meteo](https://open-meteo.com/) · Modelos: Azure OpenAI

---

## 🎓 Ejercicios propuestos

1. **Fácil** — Añade una herramienta `GetHumidityHistoryAsync` al servidor de clima y comprueba que el agente la descubre sola, sin tocar el código del agente.
2. **Medio** — Crea un cuarto agente que implemente `IAgenteA2A` y dale al Coordinador una herramienta para delegarle trabajo.
3. **Medio** — Marca `delete_file` como herramienta que requiere confirmación y observa el flujo de aprobación.
4. **Avanzado** — Sustituye el servidor de clima por uno que consulte una API de tu trabajo. Comprueba que **no hay que tocar el agente**.
5. **Avanzado** — Registra `Scenario1.WeatherServer` en Claude Desktop y úsalo desde ahí.
6. **Comparativo** — Abre el proyecto Python al lado y sigue el mismo flujo en ambos. ¿Qué gana cada lenguaje?

---

<div align="center">

### ✍️ Autoría

**Fernando Valdés H.**
*Magíster en Ingeniería en Informática*

---

*Material didáctico sobre Microsoft Agent Framework, MCP y A2A — versión C# / .NET.*

</div>
