# 🤝 A2A & MCP — Agentes que hablan entre ellos y usan herramientas de verdad

> Cuarto bloque de la serie sobre **Microsoft Agent Framework (MFA)**.
> Aquí los agentes dejan de trabajar solos: se **reparten el trabajo entre ellos (A2A)** y **usan
> herramientas externas mediante un protocolo estándar (MCP)**.


```
                          👤 Usuario
                              │
                              ▼
                    ┌───────────────────┐
                    │   COORDINADOR     │   ← reparte el trabajo
                    └─────────┬─────────┘
                        A2A   │   A2A
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌───────────────┐   ┌───────────────┐
            │ INVESTIGACIÓN │   │   EJECUTOR    │   ← especialistas
            └───────┬───────┘   └───────┬───────┘
                MCP │                   │ MCP
                    ▼                   ▼
            🔌 Herramientas externas (clima, archivos, documentación…)
```

---

## 🎯 Qué se aprende en este bloque

| Concepto | En una frase | Por qué importa |
|---|---|---|
| **MFA** — Microsoft Agent Framework | La librería que convierte un modelo de lenguaje en un *agente*: instrucciones + herramientas + memoria | Es el andamiaje que te ahorra escribir el bucle de llamadas a herramientas a mano |
| **MCP** — Model Context Protocol | El "USB-C" de las herramientas: un estándar para que **cualquier** agente use **cualquier** herramienta | Escribes la herramienta una vez y la usa tu agente, Claude Desktop, VS Code… |
| **A2A** — Agent-to-Agent | Cómo un agente le delega trabajo a otro | Un equipo de especialistas se equivoca menos que un agente que lo sabe todo |
| **Aprobación humana** | El agente se detiene y pide permiso antes de ejecutar una herramienta | Es lo que hace que un agente sea desplegable en una empresa |

### Lo elemental, en 60 segundos

**Un agente** = un modelo de lenguaje + unas instrucciones + unas herramientas.
El modelo **no ejecuta nada**: *decide* qué herramienta llamar, y el framework la ejecuta por él.

**MCP** resuelve un problema real: antes, cada herramienta se programaba a medida para cada agente. Con MCP el servidor **publica** sus herramientas y el cliente las **descubre** al conectarse — nadie escribe la lista a mano.

**A2A** es lo mismo, pero entre agentes: en vez de un agente gigante, varios especialistas y un coordinador que reparte. Igual que un equipo de personas.

---

## 📦 Los cuatro proyectos

El mismo bloque se resuelve **dos veces** (local y nube) y en **dos lenguajes** (Python y C#). Los cuatro proyectos son independientes: no comparten código ni configuración.

| Proyecto | Lenguaje | Qué demuestra |
|---|---|---|
| [`scenario1_local_agents/`](scenario1_local_agents/) | Python 3.14 | 3 agentes locales + **2 servidores MCP propios** (clima y archivos) por stdio. El **modelo decide** el orden de los pasos |
| [`scenario1_local_agents_CSharp/`](scenario1_local_agents_CSharp/) | C# / .NET 10 | Lo mismo, con `Microsoft.Agents.AI`. El contrato A2A pasa de convención a **interfaz** |
| [`scenario2_azure_foundry/`](scenario2_azure_foundry/) | Python 3.14 | 3 agentes sobre **Azure AI Foundry** + el **MCP remoto de Microsoft Learn**, con **aprobación humana** de cada llamada |
| [`scenario2_azure_foundry_CSharp/`](scenario2_azure_foundry_CSharp/) | C# / .NET 10 | Lo mismo, con `Microsoft.Agents.AI.Foundry` |

> 📖 **Cada proyecto tiene su propio README**, con la explicación completa, la puesta en marcha, el glosario y sus ejercicios. Este archivo es solo el mapa general.

---

## 🆚 Escenario 1 vs Escenario 2

No es "uno básico y otro avanzado": son **dos formas de resolver lo mismo**, y compararlas es la mitad del aprendizaje.

| | 🖥️ Escenario 1 — local | ☁️ Escenario 2 — nube |
|---|---|---|
| ¿Dónde vive el modelo? | Azure OpenAI | **Azure AI Foundry** |
| ¿Quién autentica? | Clave de API en el `.env` | **Tu identidad de Azure** (`az login`) — sin claves en disco |
| Servidores MCP | **Tuyos**, en local, como subprocesos | **De Microsoft**, remoto y público |
| Transporte MCP | stdio (tuberías del sistema operativo) | HTTP en streaming |
| Herramientas | 8 propias (3 de clima + 5 de archivos) | 3 descubiertas de Microsoft Learn |
| ¿Quién decide el orden de los pasos? | El **modelo**, con herramientas de delegación | El **guion**, paso a paso y con pausas |
| Aprobación de herramientas | No hay | ✅ **Sí**, obligatoria en cada llamada |
| ¿Escribe en tu disco? | Sí (`agent_workspace/`) | No |
| Coste | Cuota de Azure OpenAI | Cuota de Azure AI Foundry |

> 💡 **Por qué esa diferencia deliberada en "quién decide":** en el escenario 1 ves la magia — el modelo se organiza solo y encadena a los agentes. En el escenario 2 ves **la mecánica**, un mensaje cada vez, para poder mirarla con lupa. Los dos enfoques son válidos en producción; conviene entender los dos.

---

## 🧭 Ruta de aprendizaje recomendada

```
  1️⃣  Escenario 1 · Nivel 1     Arranca SOLO un servidor MCP y mira sus herramientas
        ↓                        (sin agentes, sin modelo, sin gastar un token)
  2️⃣  Escenario 1 · Nivel 2     Un agente solo, hablando con ese servidor
        ↓
  3️⃣  Escenario 1 · Nivel 3     Dos agentes hablando entre ellos (A2A)
        ↓
  4️⃣  Escenario 1 · Nivel 4     El sistema completo, con el modelo orquestando
        ↓
  5️⃣  Escenario 2               Lo mismo en la nube: identidad corporativa,
        ↓                        MCP remoto y aprobación humana
  6️⃣  El gemelo en C#           El mismo ejercicio con tipos e interfaces
```

Los niveles 1–4 están detallados en el [README del escenario 1](scenario1_local_agents/README.md).

**Si vienes de Python y quieres el equivalente en C#** (o al revés), los READMEs de los proyectos C# traen una **tabla de equivalencias** librería a librería y API a API.

---

## 🚀 Puesta en marcha

### Requisitos comunes

- Cuenta de Azure con un modelo desplegado.
- **Python 3.12+** (probado en 3.14) para los proyectos Python.
- **.NET 10 SDK** para los proyectos C#.
- **Azure CLI** (`az login`) para el escenario 2.

### Escenario 1 — Python

```powershell
cd "scenario1_local_agents"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_scenario1.py
```

Arranca directamente en modo interactivo. Comandos: `ciudades`, `demo`, `a2a`, `a2a-directo`, `arquitectura`, `ayuda`, `salir`.

> ⚠️ Ejecútalo **desde su carpeta**: el espacio de trabajo de archivos y las rutas de los servidores MCP se resuelven desde ahí.
> ✅ **No hace falta arrancar los servidores MCP a mano**: el orquestador los lanza como subprocesos y gestiona su ciclo de vida.

### Escenario 2 — Python

```powershell
cd "scenario2_azure_foundry"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
az login
python interactive_maf_demo.py
```

### Escenario 1 y 2 — C#

```powershell
cd "scenario1_local_agents_CSharp"     # o scenario2_azure_foundry_CSharp
dotnet build
az login                                # solo el escenario 2
dotnet run --project Scenario1.Host     # o --project Scenario2.Host
```

---

## 🔐 Configuración y credenciales

Cada proyecto se configura por separado. **Nunca** se versionan valores reales:

| Proyecto | Archivo de configuración | Plantilla pública |
|---|---|---|
| `scenario1_local_agents` | `.env` (ignorado por git) | — (las variables están más abajo) |
| `scenario2_azure_foundry` | `.env` (ignorado por git) | [`.env.example`](scenario2_azure_foundry/.env.example) |
| Proyectos C# | `appsettings.Development.json` (ignorado por git) | `appsettings.json` con placeholders `<…>` |

Las **variables de entorno del sistema mandan** sobre los archivos, en los cuatro proyectos.

**Escenario 1** necesita `AZURE_OPENAI_ENDPOINT` (solo la base, sin `/openai/...`), `AZURE_OPENAI_API_KEY` y `AZURE_OPENAI_DEPLOYMENT_NAME`.

**Escenario 2** necesita `AZURE_AI_PROJECT_ENDPOINT` (o `AZURE_AI_FOUNDRY_ENDPOINT` + `AZURE_AI_FOUNDRY_PROJECT`) y `AZURE_OPENAI_DEPLOYMENT_NAME` — que aquí nombra el **modelo de Foundry**, no un deployment de Azure OpenAI. **No lleva clave de API**: autentica con tu identidad mediante `DefaultAzureCredential`.

> ⚠️ Los agentes del escenario 2 son **efímeros**: viven en memoria y **no** quedan registrados en tu proyecto de Azure AI Foundry, así que no se acumulan copias con cada ejecución.

---

## 💼 ¿Y esto para qué sirve en el mundo real?

El esqueleto que montan los cuatro proyectos —**coordinador + especialistas + herramientas por MCP + aprobación humana**— es el patrón que se usa en producción. Cambia el servidor MCP y cambias de dominio, sin tocar la arquitectura:

| Cambia esto… | …y tienes |
|---|---|
| MCP de clima → MCP de tu **ERP** | Un analista que consulta cifras reales en vez de inventarlas |
| MCP de archivos → MCP de **SharePoint / S3** | Un agente que genera informes donde de verdad los lee la gente |
| MCP de Microsoft Learn → MCP de tu **base de conocimiento interna** | Un asistente que responde con las políticas *de tu empresa* |
| Añadir herramientas de **escritura** (crear, borrar, enviar) | Aquí la aprobación deja de ser un detalle didáctico y pasa a ser tu red de seguridad |

**Por qué varios agentes y no uno solo:** instrucciones más cortas (menos errores), permisos por rol (solo el Investigador toca la documentación), piezas sustituibles (puedes abaratar el modelo del Ejecutor sin tocar el resto) y trazabilidad (cada mensaje A2A es un registro auditable de quién pidió qué a quién).

---

## 📁 Estructura del bloque

```
A2A & MCP/
├── README.md                          ← este archivo (mapa general)
│
├── scenario1_local_agents/            🐍 Python · local
│   ├── agents/                        3 agentes
│   ├── mcp_servers/                   2 servidores MCP propios
│   ├── run_scenario1.py               orquestador + interfaz interactiva
│   └── README.md
│
├── scenario1_local_agents_CSharp/     #️⃣ C# · local
│   ├── Scenario1.Host/                agentes + orquestador
│   ├── McpServers/                    2 servidores MCP (proyectos ejecutables)
│   └── README.md
│
├── scenario2_azure_foundry/           🐍 Python · Azure AI Foundry
│   ├── interactive_maf_demo.py        todo el ejercicio, en 9 capas comentadas
│   └── README.md
│
└── scenario2_azure_foundry_CSharp/    #️⃣ C# · Azure AI Foundry
    ├── Scenario2.Host/                las mismas 9 capas, un archivo por capa
    └── README.md
```

---

## 🧰 Tecnologías

| Pieza | Python | C# / .NET |
|---|---|---|
| Núcleo del framework | `agent-framework-core` | `Microsoft.Agents.AI` |
| Azure OpenAI (escenario 1) | `agent-framework-openai` | `Microsoft.Agents.AI.OpenAI` + `Azure.AI.OpenAI` |
| Azure AI Foundry (escenario 2) | `agent-framework-foundry` | `Microsoft.Agents.AI.Foundry` |
| Protocolo MCP | `mcp` | `ModelContextProtocol` |
| Identidad de Azure | `azure-identity` | `Azure.Identity` |
| Configuración | `python-dotenv` | `Microsoft.Extensions.Configuration` |

Las versiones exactas, siempre **fijadas**, están en el `requirements.txt` / `.csproj` de cada proyecto.

---

## 📖 Conceptos, en una tarjeta cada uno

**Agente** — Modelo de lenguaje + instrucciones + herramientas + memoria. El modelo decide; el framework ejecuta.

**ChatClient / cliente del proyecto** — El "motor": sabe hablar con el proveedor del modelo, y nada más. No tiene personalidad. Varios agentes pueden compartirlo.

**Sesión (o hilo)** — El historial de conversación de un agente. Es lo que le hace recordar los turnos anteriores.

**Herramienta MCP** — Una función que el servidor publica y el modelo puede decidir llamar. El cliente la **descubre** al conectarse; nadie escribe su firma a mano.

**Transporte MCP** — El cable: `stdio` (proceso local) o `HTTP en streaming` (servidor remoto). El protocolo es el mismo en los dos casos.

**Mensaje A2A** — El "sobre" que un agente envía a otro: emisor, destinatario, tipo y carga útil. Los cuatro campos que necesita cualquier protocolo agente-a-agente.

**Aprobación de herramientas** — El framework detiene la ejecución y devuelve una solicitud; hasta que un humano no responde, la herramienta no se ejecuta.

**Agente efímero** — Vive en memoria durante la ejecución y no queda registrado en ningún servicio.

---

## 📚 Recursos

- [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) — documentación oficial
- [Model Context Protocol](https://modelcontextprotocol.io/) — la especificación
- [Servidor MCP de Microsoft Learn](https://github.com/microsoftdocs/mcp) — el que usa el escenario 2
- [SDK de MCP para Python](https://github.com/modelcontextprotocol/python-sdk) · [para C#](https://github.com/modelcontextprotocol/csharp-sdk)
- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry/) — el servicio del escenario 2

---

### ✍️ Autoría

Material didáctico del bloque **A2A & MCP**, cuarto de la serie sobre Microsoft Agent Framework,
junto a `Part-1/` (fundamentos), `Part-2/` (transversales) y `Part-3/` (workflows).

Fernando Valdés H.
