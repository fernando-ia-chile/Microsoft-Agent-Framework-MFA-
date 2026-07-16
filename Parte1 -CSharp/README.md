# Microsoft Agent Framework — Ejemplos en C# (.NET 10)

> **Proyecto educativo.** Port a **C# / .NET 10** de los 8 ejemplos fundamentales del
> *Microsoft Agent Framework* (MFA). Es una única aplicación de consola con un **menú**
> que ejecuta cada ejemplo de forma independiente, pensada para **aprender paso a paso**
> cómo construir agentes de IA sobre Azure.

**Autor:** Fernando Valdés H.

---

## 🎓 Objetivos educativos

Al recorrer los 8 ejemplos, en orden, aprenderás a:

1. Conectarte a un **agente de Azure AI Foundry** y conversar con él.
2. Reutilizar un **agente ya publicado** (por nombre y versión).
3. Crear un **agente efímero** con **Azure OpenAI** directo.
4. Darle al agente **búsqueda sobre tus documentos** (File Search / vector store).
5. Extender al agente con una **herramienta** (function tool).
6. Combinar **varias herramientas** y dejar que el modelo elija.
7. Aplicar **human-in-the-loop**: exigir **aprobación humana** antes de una acción peligrosa.
8. Obtener **salida estructurada** (un objeto tipado) en lugar de texto libre.

Cada ejemplo es pequeño, autónomo y comentado, para que el concepto quede claro sin ruido.

---

## ✅ Estado del proyecto

`dotnet build` → **0 Errores, 0 Advertencias**. El menú arranca correctamente.
La **prueba end-to-end** (hablar realmente con el modelo) requiere tus credenciales de Azure
(ver [Configuración](#-configuración)).

## 📦 Requisitos

- **.NET SDK 10** (probado con `10.0.201`)
- **Azure OpenAI** (API key) y/o un **proyecto de Azure AI Foundry** con un modelo desplegado
- **Azure CLI** (`az login`) para los ejemplos de Foundry (01, 02, 04)

Instala/compila:

```powershell
dotnet build
```

### Dependencias (fijadas en `MFA.CSharp.csproj`)

| Paquete | Versión | Rol |
|---------|:-------:|-----|
| `Microsoft.Agents.AI` | 1.13.0 | Núcleo (`AIAgent`, `AgentSession`) |
| `Microsoft.Agents.AI.OpenAI` | 1.13.0 | Adaptador OpenAI/Azure OpenAI (`AsAIAgent`) |
| `Microsoft.Agents.AI.Foundry` | 1.13.0-preview | Integración con Azure AI Foundry |
| `Azure.AI.OpenAI` | 2.9.0-beta.1 | `AzureOpenAIClient` |
| `Azure.AI.Projects` | 2.1.0-beta.4 | `AIProjectClient` (Foundry) |
| `Azure.Identity` | 1.13.2 | `AzureCliCredential` |
| `Microsoft.Extensions.AI` | 10.8.0 | `AIFunctionFactory`, `ChatResponseFormat`, aprobación |
| `Microsoft.Extensions.Configuration[.Json]` | 9.0.18 | Lectura de `appsettings0N.json` |

> Los paquetes del Agent Framework están en **preview/beta**; por eso se fijan versiones
> exactas (reproducibilidad) y se silencian los avisos de API experimental (`MEAI001`, etc.).

## 🗂️ Estructura del proyecto

```
MFA-CSharp/
├─ MFA.CSharp.csproj
├─ Program.cs                     # Menú principal (elige y ejecuta cada ejemplo)
├─ appsettings01.json             # Config Foundry (demos 01, 04)
├─ appsettings02.json             # Config Foundry (demo 02)
├─ appsettings03.json             # Config Azure OpenAI (demos 03, 05, 06, 07, 08)
├─ Infrastructure/
│  ├─ AppConfig.cs                # Carga de configuración por demo
│  ├─ ConsoleChat.cs              # Bucle de chat con streaming reutilizable
│  └─ FoundryConnect.cs           # Conexión a agentes de Foundry
└─ Examples/
   └─ Example01..08.cs            # Un archivo por ejemplo (autónomo y comentado)
```

## 🔧 Configuración

Rellena los `appsettings0N.json` (vienen con placeholders `<...>`):

```jsonc
// appsettings03.json — Azure OpenAI directo (demos 03, 05, 06, 07, 08)
{
  "AzureOpenAI": {
    "Endpoint": "https://<recurso>.services.ai.azure.com",   // ⚠️ SOLO la base, sin /openai/...
    "ChatDeploymentName": "gpt-5.4-mini",                     // nombre del DEPLOYMENT, no del modelo
    "ApiKey": "<tu-api-key>"
  }
}
```

```jsonc
// appsettings01.json — Foundry (demos 01, 04). appsettings02.json añade "AgentName".
{
  "AzureAI": {
    "ProjectEndpoint": "https://<recurso>.services.ai.azure.com/api/projects/<proyecto>",
    "ModelDeploymentName": "gpt-5.4-mini",
    "VectorStoreId": "<id-del-vector-store>"
  }
}
```

## ▶️ Ejecutar

```powershell
dotnet run            # abre el menú interactivo
dotnet run -- 3       # ejecuta directamente el ejemplo 3
```

Dentro de cada ejemplo, escribe `quit` (o `q`) para volver al menú.

---

## 📚 Los 8 ejemplos: objetivo y concepto

| # | Ejemplo | Qué aprendes | Concepto/API clave del MFA (.NET) |
|:-:|---------|--------------|-----------------------------------|
| 01 | Agente en Foundry | Conectar y chatear con un agente de Foundry | `AIProjectClient.AsAIAgent(AgentReference)` |
| 02 | Agente existente | Reutilizar un agente por nombre + versión | `AgentReference(name, version)` |
| 03 | Chat directo Azure OpenAI | Agente efímero con Azure OpenAI | `GetChatClient(dep).AsAIAgent(instructions, name)` |
| 04 | File Search | Responder “grounded” en tus documentos | Agente de Foundry con vector store |
| 05 | Function tool | Extender el agente con código propio | `AIFunctionFactory.Create(Metodo)` |
| 06 | Múltiples tools | Que el modelo elija la herramienta | varias tools en `tools:` |
| 07 | Human-in-the-loop | Pedir aprobación antes de actuar | `ApprovalRequiredAIFunction` + `ToolApprovalRequestContent` |
| 08 | Salida estructurada | Devolver un objeto tipado | `ChatResponseFormat.ForJsonSchema<T>()` |

**Convenciones comunes:** respuestas en *streaming* con `RunStreamingAsync` + `AgentSession`;
las herramientas son métodos anotados con `[Description]`; el bucle de chat vive en
`Infrastructure/ConsoleChat.cs`.

---

## ⚠️ Consideraciones importantes (léelas antes de ejecutar)

1. **Foundry en .NET ≠ Foundry en Python.**
   En Python, la demo 01 **crea/publica** el agente (`to_prompt_agent` + `create_version`).
   En .NET (1.13-preview) el framework se **conecta** a un agente **ya publicado** vía
   `AgentReference(nombre, versión)`. La **creación/versionado** se hace en el **portal de
   Foundry** o con `AgentAdministrationClient`. Por eso los ejemplos 01/02/04 asumen que el
   agente ya existe en tu proyecto de Foundry.

2. **Endpoint de Azure OpenAI = solo la base.**
   Usa `https://<recurso>.services.ai.azure.com` **sin** `/openai/...`. El SDK agrega la ruta.
   Incluir la ruta completa produce un **404 Resource not found**.

3. **Nombre del deployment, no del modelo.**
   `ChatDeploymentName`/`ModelDeploymentName` es el nombre del **deployment** que ves en el
   portal, que puede diferir del nombre de la familia del modelo.

4. **Credenciales y seguridad.**
   - Azure OpenAI (03/05/06/07/08): usa **API key** en `appsettings03.json`.
   - Foundry (01/02/04): usa **`az login`** (`AzureCliCredential`), sin API key.
   - **No** subas claves reales al repositorio. El `.gitignore` ya excluye `bin/`, `obj/` y
     `demo_files/`; considera además no versionar `appsettings*.json` con secretos reales.

5. **Paquetes en preview.** La API puede cambiar entre versiones; por eso se fijan versiones
   exactas. Si actualizas, revisa los nombres de tipos/métodos.

---

## 🧩 Notas técnicas de la migración a .NET (para quien lea el código)

- `ChatClient.AsAIAgent` vive en el namespace **`OpenAI.Chat`** (requiere `using OpenAI.Chat;`).
- `ChatMessage`, `ChatRole` y `ChatResponseFormat` existen en **`Microsoft.Extensions.AI`** y en
  **`OpenAI.Chat`**; se desambiguan con alias `using`.
- `AzureCliCredential` aparece duplicado entre ensamblados → se resuelve con **`extern alias`**.
- El request de aprobación es **`ToolApprovalRequestContent`** y el detalle de la llamada está
  en `.ToolCall` (cast a `FunctionCallContent`).
- No hay `eval` en C#: la calculadora usa `DataTable.Compute`; la hora usa `TimeZoneInfo`.

---

## 🔁 Equivalencias Python → C# (resumen)

| Python (agent_framework) | C# (Microsoft.Agents.AI) |
|--------------------------|--------------------------|
| `Agent(client, instructions=, name=)` | `client.AsAIAgent(instructions:, name:)` |
| `agent.run(x, stream=True)` + `chunk.text` | `agent.RunStreamingAsync(x, session)` + `update.Text` |
| tools = funciones con `Annotated[...]` | `AIFunctionFactory.Create(Metodo)` con `[Description]` |
| `@tool(approval_mode="always_require")` | `new ApprovalRequiredAIFunction(fn)` |
| `options={"response_format": Modelo}` | `ChatResponseFormat.ForJsonSchema<T>()` |
| `FoundryChatClient` / `FoundryAgent` | `AIProjectClient.AsAIAgent(AgentReference)` |

---

**Autor:** Fernando Valdés H. · Proyecto educativo sobre el *Microsoft Agent Framework* (.NET).
