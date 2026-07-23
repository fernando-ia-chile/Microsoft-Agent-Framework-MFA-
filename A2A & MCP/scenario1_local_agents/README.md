# 🤖 Escenario 1 — Agentes locales con MCP y A2A

> Tres agentes de IA que se reparten el trabajo, hablan entre ellos y usan herramientas reales.
> Todo corriendo en tu máquina, con **Microsoft Agent Framework**, **MCP** y **A2A**.

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

---

## 🎯 ¿Qué vas a aprender aquí?

Este proyecto es un laboratorio didáctico. Al terminarlo entenderás **tres conceptos** que hoy son la base de cualquier sistema de agentes:

| Concepto | En una frase | Dónde lo ves |
|---|---|---|
| **MFA** (Microsoft Agent Framework) | La librería que convierte un modelo de lenguaje en un *agente* con instrucciones y herramientas | `Agent(...)` en los tres agentes |
| **MCP** (Model Context Protocol) | El "USB-C" de las herramientas: un estándar para que cualquier agente use cualquier herramienta | `mcp_servers/` |
| **A2A** (Agent-to-Agent) | Cómo un agente le delega trabajo a otro | `agents/agent2_coordinator.py` |

### Lo elemental, en 60 segundos

**Un agente** = un modelo de lenguaje + unas instrucciones + unas herramientas.
El modelo no ejecuta nada: *decide* qué herramienta llamar, y el framework la ejecuta por él.

**MCP** resuelve un problema real: antes, cada herramienta se programaba a medida para cada agente. Con MCP escribes el servidor **una sola vez** y lo puede usar tu agente, Claude Desktop, VS Code o cualquier cliente compatible. El servidor **publica** sus herramientas y el cliente las **descubre** al conectarse — nadie escribe la lista a mano.

**A2A** es lo mismo pero entre agentes: en vez de un agente gigante que lo sabe todo, tienes varios especialistas y un coordinador que reparte. Igual que un equipo de personas.

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

**Los tres agentes usan Azure OpenAI como cerebro.** Los servidores MCP son *subprocesos*: se lanzan solos y hablan con su agente por entrada/salida estándar (stdio). **No abren ningún puerto de red.**

---

## 🚀 Puesta en marcha

### Requisitos

- **Python 3.10 o superior** (probado en 3.14)
- Una cuenta de **Azure OpenAI** con un modelo desplegado
- No necesitas clave para el clima: la API de Open-Meteo es gratuita 🎉

### 1. Instalar

```powershell
cd scenario1_local_agents

# Crear el entorno virtual (si no existe)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Instalar las dependencias
pip install -r requirements.txt
```

### 2. Configurar credenciales

Crea un archivo `.env` en esta carpeta:

```bash
AZURE_OPENAI_ENDPOINT=https://TU-RECURSO.services.ai.azure.com
AZURE_OPENAI_API_KEY=tu-clave
AZURE_OPENAI_DEPLOYMENT_NAME=nombre-de-tu-deployment
AZURE_OPENAI_API_VERSION=preview
LOG_LEVEL=INFO
```

> ⚠️ **El error más común:** `AZURE_OPENAI_ENDPOINT` debe ser **solo la base**, sin `/openai/...` al final. El framework añade la ruta por su cuenta. Si la incluyes, obtendrás un `404`.

### 3. Ejecutar

```powershell
python run_scenario1.py
```

---

## 🧩 Ejecutar por piezas (recomendado para aprender)

`run_scenario1.py` lo lanza todo junto, pero **cada pieza funciona sola**. Esta progresión es la mejor forma de entender el sistema: empieza abajo y sube.

### Nivel 1 · Solo el servidor MCP 🔌

Un servidor MCP no es un programa interactivo: se queda esperando mensajes por stdin. Si lo lanzas directo, **parecerá que se cuelga — y es correcto**:

```powershell
python mcp_servers/weather_server.py     # Ctrl+C para salir
```

Lo interesante es **preguntarle qué sabe hacer**, que es justo lo que hace un agente al conectarse:

```powershell
python -c "import asyncio,sys; sys.stdout.reconfigure(encoding='utf-8'); sys.path.insert(0,'mcp_servers'); from weather_server import mcp; print([t.name for t in asyncio.run(mcp.list_tools())])"
```

```
['get_weather', 'get_forecast', 'get_alerts']
```

Y puedes llamar una herramienta directamente, **sin ningún modelo de por medio**:

```powershell
python -c "import asyncio,sys,logging; logging.disable(logging.INFO); sys.stdout.reconfigure(encoding='utf-8'); sys.path.insert(0,'mcp_servers'); from weather_server import get_weather; c=asyncio.run(get_weather('Santiago','Chile')); print(c.temperatura_c,'°C —',c.condicion)"
```

```
10.4 °C — cubierto
```

> 💡 **Lo que acabas de comprobar:** el servidor MCP es código Python normal y corriente. No necesita IA para funcionar. La IA solo decide *cuándo* llamarlo.

<details>
<summary>🔍 <b>Extra: inspeccionar el servidor con interfaz gráfica</b></summary>

El SDK de MCP incluye un *Inspector* web. Necesita un extra:

```powershell
pip install "mcp[cli]"
mcp dev mcp_servers/weather_server.py
```

Se abre un navegador donde puedes ver las herramientas, sus esquemas y probarlas a mano.
</details>

### Nivel 2 · Un agente solo 🤖

Cada agente tiene su propia demostración. Arranca su servidor MCP, hace una consulta y cierra:

```powershell
python agents/agent1_research.py    # Investigación → clima de Santiago
python agents/agent3_executor.py    # Ejecutor → escribe y lista archivos
```

> 💡 **Lo que acabas de comprobar:** el agente se conecta al servidor, **descubre** las herramientas por protocolo y el modelo elige cuál usar. Fíjate en la línea `✅ MCP conectado. Herramientas descubiertas: ...`

### Nivel 3 · Dos agentes hablando entre ellos 📡

```powershell
python agents/agent2_coordinator.py
```

El Coordinador recibe *"¿Qué clima hace en Tokio? Guárdalo en informe_tokio.txt"* y **decide él solo** que necesita dos agentes, en qué orden, y encadena el resultado del primero como entrada del segundo.

Verás las cajas del mensaje A2A:

```
   📨 ESTRUCTURA DEL MENSAJE A2A:
   ┌────────────────────────────────────────────────────────────┐
   │ Emisor:     coordinator-agent                              │
   │ Destino:    research-agent                                 │
   │ Tipo:       research_request                               │
   └────────────────────────────────────────────────────────────┘
```

### Nivel 4 · El sistema completo 🎬

```powershell
python run_scenario1.py
```

| Progresión | Qué añade |
|---|---|
| 1 · Servidor MCP | Herramientas, sin IA |
| 2 · Un agente | El modelo elige la herramienta |
| 3 · Coordinador | Un agente delega en otros |
| 4 · Todo | Interfaz interactiva y ciclo de vida |

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

Manda mensajes A2A **saltándose al Coordinador**. Sirve para ver el protocolo desnudo: qué mensaje entra, qué respuesta sale, sin ningún modelo decidiendo.

Compáralo con una pregunta normal y verás la diferencia entre **un guion escrito a mano** y **una orquestación decidida por el modelo**. Mismo transporte, misma estructura de mensaje: cambia quién decide.

---

## 🔬 Anatomía de una ejecución

Cuando escribes *"¿Qué tiempo hace en Tokio? Guárdalo en un archivo"*, ocurre esto:

```
run_scenario1          → 1 sola llamada, no decide nada
  └── COORDINADOR (LLM)      ¿investigar? ¿guardar? ¿en qué orden?
        ├── INVESTIGACIÓN (LLM)   ¿get_weather, get_forecast o get_alerts?
        │      └── MCP → weather_server → 🌍 Open-Meteo
        └── EJECUTOR (LLM)        ¿write_file, read_file, list_files...?
               └── MCP → file_operations_server → 📂 disco
```

**Son tres bucles de modelo anidados, no un guion secuencial.**

Y ese `Pasos: 2/2` que ves al final **no es un plan previo**: se cuenta *después*, según lo que el modelo haya decidido hacer.

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
| `consultar_stock(sku)` | Un agente de inventario que responde en lenguaje natural |
| `buscar_cliente(rut)` | Un asistente de CRM que cruza datos de varios sistemas |
| `consultar_bd(sql)` | Un analista que responde preguntas sobre tu base de datos |
| `estado_ticket(id)` | Un agente de soporte que consulta y actualiza incidencias |
| `leer_correos(filtro)` | Un clasificador que archiva y resume tu bandeja |

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
| **Piezas reemplazables** | Cambias el Ejecutor sin tocar los demás |
| **Permisos separados** | Solo el Ejecutor toca el disco; el Investigador no puede |
| **Depuración simple** | Sabes qué agente falló y lo pruebas por separado (Nivel 2) |

### 🎁 Bonus: usa tu servidor MCP en Claude Desktop

Esta es la gracia real de MCP: **el servidor que escribiste aquí funciona en otros clientes sin tocar una línea**. En la configuración de Claude Desktop:

```json
{
  "mcpServers": {
    "clima": {
      "command": "C:\\ruta\\a\\scenario1_local_agents\\.venv\\Scripts\\python.exe",
      "args": ["C:\\ruta\\a\\scenario1_local_agents\\mcp_servers\\weather_server.py"]
    }
  }
}
```

Escribes la herramienta una vez, la usas en todas partes. Eso es el estándar.

---

## 📁 Estructura del proyecto

```
scenario1_local_agents/
├── agents/
│   ├── agent1_research.py       🔍 Investigación — consume el MCP de clima
│   ├── agent2_coordinator.py    🧠 Coordinador — orquesta y delega por A2A
│   └── agent3_executor.py       ⚙️  Ejecutor — consume el MCP de archivos
├── mcp_servers/
│   ├── weather_server.py        🌍 3 herramientas (clima, pronóstico, avisos)
│   └── file_operations_server.py 📂 5 herramientas (leer, escribir, listar…)
├── agent_workspace/             📦 Salida de los agentes (se crea sola)
├── run_scenario1.py             🎬 Orquestador + interfaz interactiva
├── requirements.txt             📌 Dependencias con versiones fijas
└── .env                         🔑 Credenciales (NO subir a git)
```

> 📖 **El código está comentado paso a paso.** Cada archivo abre con un mapa del flujo de ejecución (`[1]`, `[2]`, `[3]`…) y los comentarios están clasificados: `⚙️ MFA`, `🔌 MCP`, `📡 A2A`, `🔧 Infra`. Puedes seguir la ejecución leyendo los números en orden.

---

## 🧯 Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `404` al llamar al modelo | `AZURE_OPENAI_ENDPOINT` incluye `/openai/...` | Deja **solo la base** de la URL |
| `UnicodeEncodeError` con emojis | La consola de Windows usa cp1252 | Ya resuelto en el código (`reconfigure(encoding="utf-8")`) |
| `McpError: Connection closed` | Algún `print()` del servidor escribe en **stdout** | En stdio, **stdout es el canal del protocolo**: los mensajes van a `stderr` |
| El servidor "se cuelga" al ejecutarlo | Es lo normal: espera mensajes por stdin | Úsalo desde un agente, o inspecciónalo (Nivel 1) |
| `ModuleNotFoundError: agent_framework` | El entorno virtual no está activo | `.\.venv\Scripts\Activate.ps1` |
| Responde en inglés | Faltan instrucciones de idioma | Las `instructions` deben pedir el español **explícitamente** |

> ⚠️ **No instales el meta-paquete `agent-framework`**: arrastra una versión incompatible. Instala los subpaquetes concretos que están en `requirements.txt`.

---

## 📖 Glosario rápido

| Término | Qué es |
|---|---|
| **Agente** | Modelo + instrucciones + herramientas |
| **Herramienta (tool)** | Función que el modelo puede pedir que se ejecute |
| **stdio** | Transporte MCP por entrada/salida estándar; el servidor es un subproceso |
| **Descubrimiento** | El cliente pregunta al servidor qué herramientas tiene, en vez de tenerlas escritas |
| **Salida estructurada** | La herramienta devuelve un objeto con esquema, no texto suelto |
| **Anotaciones** | Pistas sobre la herramienta: si solo lee, si destruye datos, si sale a internet |
| **Delegación A2A** | Un agente pide trabajo a otro mediante un mensaje con formato acordado |

---

## 🧰 Tecnologías

| Componente | Versión |
|---|---|
| `agent-framework-core` | 1.12.0 |
| `agent-framework-openai` | 1.10.2 |
| `agent-framework-a2a` | 1.0.0b260721 |
| `mcp` | 1.28.1 |
| `httpx` · `rich` · `pydantic` | 0.28.1 · 15.0.0 · 2.13.4 |

Datos meteorológicos: [Open-Meteo](https://open-meteo.com/) · Modelos: Azure OpenAI

---

## 🎓 Ejercicios propuestos

1. **Fácil** — Añade una herramienta `get_humidity_history` al servidor de clima y comprueba que el agente la descubre sola.
2. **Medio** — Crea un cuarto agente (por ejemplo, "Analista") y dale al Coordinador una herramienta para delegarle trabajo.
3. **Medio** — Marca `delete_file` con aprobación humana obligatoria en el agente y observa cómo se pide confirmación.
4. **Avanzado** — Sustituye el servidor de clima por uno que consulte una API de tu trabajo. Comprueba que **no hay que tocar el agente**.
5. **Avanzado** — Registra `weather_server.py` en Claude Desktop y úsalo desde ahí.

---

<div align="center">

### ✍️ Autoría

**Fernando Valdés H.**
*Magíster en Ingeniería en Informática*

---

*Material didáctico sobre Microsoft Agent Framework, MCP y A2A.*

</div>
