# ☁️ Escenario 2 — Agentes en Azure AI Foundry + MCP de Microsoft Learn

> Tres agentes de IA que se reparten el trabajo, se pasan mensajes entre ellos y consultan
> **la documentación oficial de Microsoft en tiempo real** — pidiéndote permiso antes de cada consulta.
> Todo con **Microsoft Agent Framework (MFA)**, **MCP** y **A2A**.

```
        👤 "¿Qué niveles de servicio admiten servidores MCP en API Management?"
                              │
                              ▼
                    ┌───────────────────┐
                    │   COORDINADOR     │  ← no sabe nada; tiene que delegar
                    └─────────┬─────────┘
                    ┌─────────┴─────────┐
                    ▼                   ▼
            ┌───────────────┐   ┌───────────────┐
            │ INVESTIGACIÓN │   │   EJECUTOR    │
            └───────┬───────┘   └───────┬───────┘
                    ▼                   ▼
        🔌 MCP Microsoft Learn      ✍️ Informe final
        (documentación real)         (formato y resumen)
```

---

## 🎯 ¿Qué vas a aprender aquí?

Este proyecto es un laboratorio didáctico. Al terminarlo entenderás **cuatro conceptos** que hoy son la base de cualquier sistema de agentes en producción:

| Concepto | En una frase | Dónde lo ves |
|---|---|---|
| **MFA** (Microsoft Agent Framework) | La librería que convierte un modelo de lenguaje en un *agente* con instrucciones, memoria y herramientas | `Agent(...)` en `FabricaDeAgentes` |
| **Azure AI Foundry** | Dónde vive el modelo: un servicio gestionado de Azure, con tu identidad corporativa y tu cuota | `FoundryChatClient(...)` |
| **MCP** (Model Context Protocol) | El "USB-C" de las herramientas: un estándar para que cualquier agente use cualquier herramienta, incluso remota | `MCPStreamableHTTPTool(...)` |
| **A2A** (Agent-to-Agent) | Cómo un agente le delega trabajo a otro | `RedA2A` y `MensajeA2A` |

### Lo elemental, en 60 segundos

**Un agente** = un modelo de lenguaje + unas instrucciones + unas herramientas.
El modelo no ejecuta nada: *decide* qué herramienta llamar, y el framework la ejecuta por él.

**MCP** resuelve un problema muy real: antes, cada herramienta se programaba a medida para cada agente. Con MCP, quien publica la herramienta la escribe **una sola vez** y la puede usar tu agente, Claude Desktop, VS Code o cualquier cliente compatible. Aquí no montamos ningún servidor: **consumimos uno público y remoto**, el de Microsoft Learn, que Microsoft mantiene por nosotros.

**A2A** es lo mismo, pero entre agentes: en vez de un agente gigante que lo sabe todo, tienes varios especialistas y un coordinador que reparte. Igual que un equipo de personas.

**La aprobación de herramientas** es la parte que casi nadie enseña y que en una empresa es innegociable: antes de que el agente ejecute una herramienta, **un humano decide si puede**. Aquí lo vas a ver funcionando, y son literalmente dos palabras de código.

---

## 🆚 ¿En qué se diferencia del Escenario 1?

Son el **mismo ejercicio resuelto de dos maneras**. Compararlos es la mitad del aprendizaje:

| | 🖥️ Escenario 1 — local | ☁️ Escenario 2 — este |
|---|---|---|
| ¿Dónde vive el modelo? | Azure OpenAI vía `OpenAIChatClient` | **Azure AI Foundry** vía `FoundryChatClient` |
| ¿Quién autentica? | Clave de API en el `.env` | **Tu identidad de Azure** (`az login`) — sin claves en disco |
| Servidores MCP | **Tuyos**, en local, como subprocesos (`MCPStdioTool`) | **De Microsoft**, remoto y público (`MCPStreamableHTTPTool`) |
| Transporte MCP | stdio (tuberías del sistema operativo) | HTTP en streaming |
| ¿Quién decide el orden de los pasos? | El **modelo** (el Coordinador tiene *function tools*) | El **guion** de la demo, paso a paso y con pausas |
| Aprobación de herramientas | No hay | ✅ **Sí**, `approval_mode="always_require"` |

> 💡 La diferencia del penúltimo punto es deliberada: en el escenario 1 se ve la magia (el modelo se organiza solo); en el escenario 2 se ve **la mecánica**, un mensaje cada vez, para que puedas mirarla con lupa.

---

## 🏗️ Arquitectura

```
┌──────────────────────────────────────────────────────────────────────┐
│                          TU MÁQUINA                                  │
│                                                                      │
│                            👤 Usuario                                │
│                                │                                     │
│                                ▼                                     │
│                     ┌──────────────────────┐                         │
│                     │   RED A2A (buzones)  │  enruta los mensajes    │
│                     └──────────┬───────────┘                         │
│              ┌─────────────────┼─────────────────┐                   │
│              ▼                 ▼                 ▼                   │
│      ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│      │ COORDINADOR  │  │ INVESTIGACIÓN│  │  EJECUTOR    │            │
│      │  sin tools   │  │  + MCP       │  │  sin tools   │            │
│      └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            │
│             └─────────────────┼─────────────────┘                    │
│                               │  (los tres comparten un ChatClient)  │
└───────────────────────────────┼──────────────────────────────────────┘
                                │
                ┌───────────────┴────────────────┐
                ▼                                ▼
    ┌────────────────────────┐      ┌───────────────────────────┐
    │  ☁️ AZURE AI FOUNDRY   │      │ 🔌 MCP de Microsoft Learn │
    │  el modelo que razona  │      │  learn.microsoft.com/api  │
    └────────────────────────┘      └───────────────────────────┘
```

**Los tres agentes comparten un único `FoundryChatClient`.** Es un detalle importante: el *ChatClient* es el **motor** (sabe hablar con Foundry) y el `Agent` es el **personaje** (nombre, instrucciones, herramientas, memoria). Un mismo motor mueve tres carrocerías distintas.

---

## 🚀 Puesta en marcha

### Requisitos

- Python 3.12 o superior (probado en 3.14).
- Una suscripción de Azure con un proyecto de **Azure AI Foundry** y un modelo desplegado.
- **Azure CLI** instalado y con sesión iniciada.

### 1. Instalar

```powershell
cd "scenario2_azure_foundry"
python -m venv .venv                 # solo la primera vez
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configurar

Crea (o edita) el archivo `.env` en esta carpeta:

```env
# El endpoint completo del PROYECTO de Foundry
AZURE_AI_PROJECT_ENDPOINT=https://<tu-recurso>.services.ai.azure.com/api/projects/<tu-proyecto>

# ...o, si lo prefieres, sus dos mitades y el programa lo compone solo:
AZURE_AI_FOUNDRY_ENDPOINT=https://<tu-recurso>.services.ai.azure.com
AZURE_AI_FOUNDRY_PROJECT=<tu-proyecto>

# ⚠️ Pese al nombre, aquí esto nombra al MODELO DE FOUNDRY, no a un deployment
#    de Azure OpenAI. El nombre se conserva por compatibilidad histórica.
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.4-mini
```

> 🔐 **No hay ninguna clave de API.** La autenticación es con tu identidad de Azure a través de `DefaultAzureCredential`. Eso significa una cosa muy práctica: si te vas de la empresa, tu acceso muere contigo — cosa que una clave copiada en un `.env` no hace.

### 3. Iniciar sesión y ejecutar

```powershell
az login
python interactive_maf_demo.py
```

La demo se detiene en cada paso y espera a que pulses **Enter**. Tómate tu tiempo: la gracia está en leer lo que pasa entre pausa y pausa.

> ⚠️ **Este escenario llama a modelos de verdad**: consume cuota y no es determinista. La misma pregunta puede dar respuestas distintas.

---

## 🎬 Anatomía de una ejecución

### FASE 1 — Nacen los agentes

```
[1/3] Creando el Agente de Investigación (con herramientas MCP)
✅ Agente de Investigación creado
   Modo de aprobación: always_require (te pedirá permiso por cada llamada)
   Herramientas descubiertas POR PROTOCOLO (no escritas a mano):
      • microsoft_docs_search
      • microsoft_code_sample_search
      • microsoft_docs_fetch
```

👀 **Fíjate en esas tres herramientas.** Nadie las escribió en el código. Aparecieron en el *handshake* del protocolo MCP: el servidor las **publica** y el cliente las **descubre**. Si Microsoft añade una cuarta mañana, aparecerá sola.

♻️ **Y fíjate en lo que NO pasa:** no se crea nada en tu proyecto de Azure. Los agentes son **efímeros**, viven en memoria. (La versión antigua de este ejercicio registraba tres agentes permanentes en Foundry **en cada ejecución** y no los borraba nunca.)

### FASE 2 — Los siete pasos del flujo A2A

```
▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
📨 MENSAJE A2A
▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
  De:        Agente Coordinador
  Para:      Agente de Investigación
  Tipo:      solicitud_investigacion
  Contenido: Investiga en Microsoft Learn qué niveles de servicio de Azure…
▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
```

Esa caja es el corazón didáctico del ejercicio: hace **visible** algo que normalmente ocurre en silencio. Emisor, destinatario, tipo y carga útil son exactamente los cuatro campos que necesita cualquier protocolo agente-a-agente.

| Paso | Quién → Quién | Qué ocurre |
|---|---|---|
| 1 | 👤 Usuario → 🧭 Coordinador | El Coordinador convierte tu pregunta en un **encargo concreto** |
| 2 | 🧭 Coordinador → 🔍 Investigación | Delega, porque él no tiene documentación |
| 3 | 🔍 Investigación → 🔌 Microsoft Learn | **Te pide permiso** y consulta la documentación real |
| 4 | 🔍 Investigación → 🧭 Coordinador | Devuelve los hallazgos con sus fuentes |
| 5 | 🧭 Coordinador → ✍️ Ejecutor | Le pasa el material en bruto |
| 6 | ✍️ Ejecutor → 🧭 Coordinador | Devuelve un informe estructurado |
| 7 | 🧭 Coordinador → 👤 Usuario | Redacta la respuesta final |

### El momento estrella: la aprobación

```
  ┌──────────────────────────────────────────────────────────────────┐
  │ 🔐 SOLICITUD DE APROBACIÓN DE HERRAMIENTA MCP
  │ ─────────────────────────────────────────────────────────────────
  │ Herramienta: microsoft_docs_search
  │ Argumentos:  {'query': 'Azure API Management MCP server tiers'}
  └──────────────────────────────────────────────────────────────────┘
  ¿Autorizas esta llamada? [S/n]:
```

El agente **se ha parado**. Ha decidido qué herramienta quiere usar y con qué argumentos, pero no puede ejecutarla hasta que tú digas que sí. Prueba a responder `n` y verás cómo se las arregla sin ese dato.

Todo eso lo produce **una sola línea**:

```python
MCPStreamableHTTPTool(name="microsoft_learn", url=..., approval_mode="always_require")
```

---

## 💼 ¿Y esto para qué sirve en el mundo real?

Este esqueleto —**coordinador + especialistas + herramientas remotas + aprobación humana**— es exactamente el patrón que se usa en producción. Cambia el servidor MCP y cambias de dominio, sin tocar la arquitectura:

| Cambia esto… | …y tienes |
|---|---|
| MCP de Microsoft Learn → MCP de tu **base de conocimiento interna** | Un asistente que responde con las políticas *de tu empresa*, no con lo que el modelo recuerde |
| …→ MCP sobre **Jira / ServiceNow** | Un agente de soporte que consulta tickets reales y propone soluciones |
| …→ MCP sobre tu **ERP o tu data warehouse** | Un analista que consulta cifras reales en vez de inventarlas |
| …→ MCP con herramientas de **escritura** (crear, borrar, enviar) | Aquí la aprobación deja de ser un detalle didáctico y pasa a ser tu red de seguridad |

### Casos concretos que puedes montar con lo que ya está aquí

- 📚 **Mesa de ayuda documental**: un canal de Teams pregunta, el agente responde citando la documentación oficial, con enlace.
- 🎓 **Tutor técnico**: el Coordinador detecta el nivel del alumno y el Ejecutor adapta el informe (principiante / experto).
- 🔍 **Vigilancia tecnológica**: cada lunes, el Coordinador pregunta por las novedades de tres servicios y el Ejecutor emite un boletín.
- 🛡️ **Agente con "cinturón de seguridad"**: cambia la `AprobacionInteractiva` por una que consulte una lista blanca, o que escale a un supervisor. No hay que tocar ni un agente.

### El patrón "coordinador + especialistas"

¿Por qué no un solo agente que lo haga todo? Por las mismas razones por las que una empresa no es una sola persona:

- **Instrucciones más cortas y precisas** → menos errores. Un agente con quince responsabilidades las cumple todas a medias.
- **Permisos por rol**: solo el Investigador toca la documentación. El Ejecutor no puede llamar a ninguna herramienta ni queriendo.
- **Sustituibles**: puedes cambiar el modelo del Ejecutor por uno más barato sin tocar los otros dos.
- **Trazabilidad**: cada mensaje A2A es un registro auditable de quién pidió qué a quién.

---

## 📁 Estructura del proyecto

```
scenario2_azure_foundry/
├── interactive_maf_demo.py      ← todo el ejercicio, en 9 capas comentadas
├── requirements.txt             ← dependencias pinneadas y verificadas
├── .env                         ← tu configuración (NO lo subas a git)
├── agents_info_interactive.json ← ficha que genera la demo al ejecutarse
└── README.md                    ← este archivo
```

### Las 9 capas del archivo

El programa está escrito como un ejemplo de diseño limpio: cada capa tiene **una sola responsabilidad** y se puede leer por separado.

| Capa | Clase(s) | Responsabilidad única |
|---|---|---|
| 1 · Configuración | `Configuracion` | Leer y **validar** el `.env`. Nadie más llama a `os.getenv()` |
| 2 · Presentación | `Consola` | Todo lo que se imprime. Los agentes **no** llaman a `print()` |
| 3 · Contrato A2A | `MensajeA2A`, `RespuestaA2A`, `TipoMensaje` | La forma del "sobre" que viaja entre agentes |
| 4 · Aprobación | `PoliticaDeAprobacion` + 2 implementaciones | Decidir si una herramienta puede ejecutarse |
| 5 · Agentes | `AgenteA2A` (base) + los 3 concretos | Cada especialista y su comportamiento |
| 6 · Red | `RedA2A` | Enrutar mensajes entre buzones |
| 7 · Fábrica | `FabricaDeAgentes` | Saber **cómo** se construye cada agente |
| 8 · Guion | `DemostracionA2A` | Contar la historia de los 7 pasos |
| 9 · Principal | `main()` | Montar la red, enseñarla y desmontarla |

### 🏛️ Los principios SOLID, en este código y sin teoría

| Principio | Dónde está | Por qué te importa a ti |
|---|---|---|
| **S** — Responsabilidad única | Las 9 capas de arriba | Cuando algo falla, sabes en qué clase mirar |
| **O** — Abierto/cerrado | `RedA2A.registrar()` | Añadir un cuarto agente es **una línea**, no un `if` nuevo |
| **L** — Sustitución de Liskov | `AgenteA2A.atender()` | La red entrega mensajes sin saber a quién: los tres agentes son intercambiables |
| **I** — Segregación de interfaces | `tipos_admitidos` | Cada agente publica **solo** lo que sabe atender, y rechaza el resto con un error claro |
| **D** — Inversión de dependencias | `Consola` y `PoliticaDeAprobacion` inyectadas | Cambiar la terminal por una web, o la aprobación manual por una lista blanca, **no toca ningún agente** |

> 💡 Prueba a hacerlo: escribe una clase `AprobacionPorListaBlanca` con un método `decidir()` y pásasela al agente. No hay que modificar nada más. Eso es la "D" de SOLID en la práctica.

---

## 🧯 Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `❌ Configuración: Falta AZURE_AI_PROJECT_ENDPOINT…` | El `.env` está incompleto o se ejecuta desde otra carpeta | Revisa el `.env`; la ruta es absoluta, pero el archivo debe estar **junto al script** |
| `DefaultAzureCredential failed to retrieve a token` | No hay sesión de Azure | `az login` |
| `(PermissionDenied)` o 403 | Tu usuario no tiene rol en el proyecto de Foundry | Pide el rol **Azure AI User** (o superior) sobre el recurso |
| `Deployment not found` | El modelo del `.env` no existe en ese proyecto | Comprueba el nombre exacto en el portal de Foundry |
| `UnicodeEncodeError` con los emojis | Consola de Windows en cp1252 | Ya está resuelto: el script fuerza UTF-8 al arrancar |
| La demo avanza sola sin esperarte | No hay terminal interactiva (salida redirigida) | Ejecútalo directamente en la consola, sin tuberías |

---

## 📖 Glosario rápido

| Término | Qué es |
|---|---|
| **Agente** | Modelo de lenguaje + instrucciones + herramientas + memoria |
| **ChatClient** | El "motor": sabe hablar con el proveedor del modelo. No tiene personalidad |
| **Sesión** | El hilo de conversación de un agente. Es lo que le hace recordar los turnos anteriores |
| **Agente efímero** | Vive en memoria durante la ejecución. No queda registrado en el servicio |
| **MCP** | Protocolo estándar para publicar y descubrir herramientas |
| **Herramienta MCP** | Una función que el servidor publica y el modelo puede decidir llamar |
| **`approval_mode`** | Ajuste de la herramienta que exige el visto bueno de un humano antes de ejecutarla |
| **A2A** | Comunicación entre agentes: uno delega trabajo en otro |
| **Streaming** | Recibir la respuesta por trozos según se genera, en vez de esperar al final |
| **`DefaultAzureCredential`** | Busca tu identidad de Azure allí donde esté (CLI, variables, identidad gestionada) |

---

## 🧰 Tecnologías

| Pieza | Versión | Para qué |
|---|---|---|
| `agent-framework-core` | 1.12.1 | `Agent` y las herramientas MCP (sí: MCP vive en el core) |
| `agent-framework-foundry` | 1.10.3 | `FoundryChatClient`, el motor sobre Azure AI Foundry |
| `mcp` | 1.28.1 | SDK del Model Context Protocol |
| `azure-identity` | 1.25.3 | `DefaultAzureCredential` |
| `python-dotenv` | 1.2.2 | Carga del `.env` |

---

## 🎓 Ejercicios propuestos

1. **Di que no.** Responde `n` a la primera aprobación y observa cómo reacciona el agente. ¿Reconoce que le falta información o improvisa?
2. **Cambia la pregunta.** Prueba con algo que la documentación NO cubra. ¿El agente lo admite o se lo inventa? (Sus instrucciones le piden admitirlo.)
3. **Un cuarto agente.** Crea un `AgenteTraductor` que herede de `AgenteA2A`, regístralo en la red y añade un paso 8 que traduzca la respuesta final al inglés.
4. **Otra política.** Escribe `AprobacionPorListaBlanca` que apruebe `microsoft_docs_search` sin preguntar y exija confirmación para el resto.
5. **Cambia de motor.** Sustituye `FoundryChatClient` por `OpenAIChatClient` (el del escenario 1). Deberían bastarte unas pocas líneas en la fábrica: ese es el premio de haber separado el motor del personaje.
6. **Quítale las herramientas al Investigador** y vuelve a lanzar la demo. Compara la respuesta con la anterior: es la mejor demostración de para qué sirve MCP.

---

### ✍️ Autoría

Material didáctico del bloque **A2A & MCP** de la serie sobre Microsoft Agent Framework.
Fernando Valdés H.
