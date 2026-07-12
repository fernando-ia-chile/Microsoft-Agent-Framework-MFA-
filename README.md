# Microsoft Agent Framework – Ejemplos Educativos

Colección de ejemplos **paso a paso en Python** para aprender a construir
agentes de IA con [Microsoft AutoGen](https://github.com/microsoft/autogen)
y [Semantic Kernel](https://github.com/microsoft/semantic-kernel), conectados
a OpenAI y Azure OpenAI.

> **Objetivo**: que cualquier estudiante pueda ejecutar estos ejemplos
> localmente, sin experiencia previa en agentes de IA.

---

## 📁 Estructura del repositorio

```
Microsoft-Agent-Framework-MFA-/
├── examples/
│   ├── 01_basic_agent.py            ← Agente básico (sin API, corre ya)
│   ├── 02_openai_agent.py           ← Agente conectado a OpenAI
│   ├── 03_azure_openai_agent.py     ← Agente conectado a Azure OpenAI
│   ├── 04_multi_agent_workflow.py   ← Flujo multi-agente (GroupChat)
│   ├── 05_semantic_kernel_agent.py  ← Agente con Semantic Kernel + plugins
│   └── 06_best_practices.py        ← Seguridad, config y reproducibilidad
├── docs/
│   ├── setup_guide.md               ← Instalación paso a paso
│   └── concepts.md                  ← Glosario y conceptos clave
├── .env.example                     ← Plantilla de variables de entorno
├── requirements.txt                 ← Dependencias Python
└── .gitignore
```

---

## 🚀 Inicio rápido

### 1. Clona el repositorio

```bash
git clone https://github.com/fernando-ia-chile/Microsoft-Agent-Framework-MFA-.git
cd Microsoft-Agent-Framework-MFA-
```

### 2. Crea un entorno virtual e instala dependencias

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configura tus credenciales

```bash
cp .env.example .env
# Edita .env con tu OPENAI_API_KEY o variables de Azure OpenAI
```

### 4. Ejecuta el primer ejemplo (¡sin necesitar API!)

```bash
python examples/01_basic_agent.py
```

---

## 📚 Descripción de los ejemplos

| # | Archivo | Descripción | Requiere API |
|---|---------|-------------|:---:|
| 01 | `01_basic_agent.py` | Estructura de un agente AutoGen sin llamadas reales | ❌ |
| 02 | `02_openai_agent.py` | Conectar un agente al servicio público de OpenAI | ✅ OpenAI |
| 03 | `03_azure_openai_agent.py` | Conectar un agente a Azure OpenAI Service | ✅ Azure |
| 04 | `04_multi_agent_workflow.py` | GroupChat: revisión de código con 3 agentes especializados | ✅ OpenAI/Azure |
| 05 | `05_semantic_kernel_agent.py` | Agente educativo con plugins de Semantic Kernel | ✅ OpenAI/Azure |
| 06 | `06_best_practices.py` | Patrones de seguridad, reintentos y reproducibilidad | ❌ |

---

## 🔑 Variables de entorno

Copia `.env.example` a `.env` y rellena los valores que necesites:

```env
# OpenAI (ejemplos 02, 04, 05)
OPENAI_API_KEY=sk-...tu-clave...
OPENAI_MODEL=gpt-4o-mini

# Azure OpenAI (ejemplos 03, 04, 05)
AZURE_OPENAI_ENDPOINT=https://<recurso>.openai.azure.com/
AZURE_OPENAI_API_KEY=...tu-clave-azure...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01
```

> ⚠️ **Nunca** hagas commit del archivo `.env`.  
> El `.gitignore` ya lo excluye; solo se versiona `.env.example`.

---

## ✅ Mejores prácticas implementadas

Los ejemplos demuestran las siguientes prácticas recomendadas:

1. **Credenciales en `.env`** — nunca hardcodeadas en el código.
2. **Validación fail-fast** — errores de configuración visibles al inicio.
3. **Reintentos con backoff** — manejo robusto de errores de red/API.
4. **`temperature=0`** — respuestas deterministas y reproducibles.
5. **`max_tokens` y `timeout` explícitos** — control de costos y latencia.
6. **Logging estructurado** — trazabilidad en todos los ejemplos.
7. **Entornos separados** — `development` / `staging` / `production`.
8. **Rate limiting consciente** — para no exceder cuotas de la API.

---

## 📖 Documentación adicional

- [Guía de configuración paso a paso](docs/setup_guide.md)
- [Conceptos clave y glosario](docs/concepts.md)
- [AutoGen — documentación oficial](https://microsoft.github.io/autogen/)
- [Semantic Kernel — documentación oficial](https://learn.microsoft.com/en-us/semantic-kernel/overview/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)

---

## 🛠️ Solución de problemas

Ver [docs/setup_guide.md](docs/setup_guide.md#solución-de-problemas-comunes).

---

## 📄 Licencia

MIT — libre para uso educativo y comercial.
