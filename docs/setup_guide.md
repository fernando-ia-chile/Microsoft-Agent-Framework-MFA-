# Guía de Configuración Local

Esta guía te llevará paso a paso desde cero hasta tener todos los ejemplos
ejecutándose en tu máquina.

---

## Requisitos previos

| Herramienta | Versión mínima | Comprobación |
|-------------|----------------|--------------|
| Python | 3.10 | `python --version` |
| pip | 23.0 | `pip --version` |
| Git | 2.40 | `git --version` |
| Cuenta OpenAI o Azure | — | [platform.openai.com](https://platform.openai.com) o [portal.azure.com](https://portal.azure.com) |

---

## Paso 1 – Clonar el repositorio

```bash
git clone https://github.com/fernando-ia-chile/Microsoft-Agent-Framework-MFA-.git
cd Microsoft-Agent-Framework-MFA-
```

---

## Paso 2 – Crear y activar un entorno virtual

Usar un entorno virtual evita conflictos entre versiones de paquetes.

```bash
# Crear
python -m venv .venv

# Activar (Linux / macOS)
source .venv/bin/activate

# Activar (Windows PowerShell)
.venv\Scripts\Activate.ps1
```

Deberías ver `(.venv)` al inicio de tu prompt.

---

## Paso 3 – Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Paso 4 – Configurar las variables de entorno

```bash
cp .env.example .env
```

Abre `.env` con tu editor y rellena las claves:

### Opción A: OpenAI público

```env
OPENAI_API_KEY=sk-...tu-clave-real...
OPENAI_MODEL=gpt-4o-mini
```

Obtén tu clave en: <https://platform.openai.com/api-keys>

### Opción B: Azure OpenAI

```env
AZURE_OPENAI_ENDPOINT=https://mi-recurso.openai.azure.com/
AZURE_OPENAI_API_KEY=...tu-clave-azure...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01
```

Para obtener estos valores:
1. Ve a tu recurso en [portal.azure.com](https://portal.azure.com).
2. Sección **Keys and Endpoint** → copia la clave y el endpoint.
3. En **Azure OpenAI Studio** → **Deployments** → anota el nombre de tu despliegue.

> **⚠️ IMPORTANTE**: El archivo `.env` está en `.gitignore`.
> **Nunca** hagas commit de claves reales.

---

## Paso 5 – Ejecutar los ejemplos en orden

```bash
# Sin API – funciona sin ninguna clave
python examples/01_basic_agent.py

# Requiere OPENAI_API_KEY
python examples/02_openai_agent.py

# Requiere variables de Azure OpenAI
python examples/03_azure_openai_agent.py

# Requiere OPENAI_API_KEY (o Azure)
python examples/04_multi_agent_workflow.py

# Requiere OPENAI_API_KEY (o Azure)
python examples/05_semantic_kernel_agent.py

# Sin API – funciona sin ninguna clave
python examples/06_best_practices.py
```

---

## Solución de problemas comunes

### `ModuleNotFoundError: No module named 'autogen'`

```bash
pip install pyautogen
```

### `AuthenticationError: Incorrect API key`

- Verifica que copiaste la clave completa (sin espacios extras).
- Asegúrate de que el archivo `.env` está en la raíz del proyecto.
- Ejecuta `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY', 'NO ENCONTRADA')[:10])"`.

### `RateLimitError` o `429 Too Many Requests`

- Espera unos segundos y vuelve a intentarlo.
- Reduce `max_tokens` o `max_consecutive_auto_reply` en el ejemplo.
- Considera usar `gpt-4o-mini` (más barato y con mayor cuota).

### Error en Azure: `DeploymentNotFound`

- Verifica que `AZURE_OPENAI_DEPLOYMENT` coincide exactamente con el nombre
  del despliegue en Azure OpenAI Studio (distingue mayúsculas/minúsculas).

---

## Verificar la instalación rápidamente

```python
# Ejecuta esto en la terminal para comprobar todas las dependencias:
python -c "
import autogen, semantic_kernel, openai, dotenv
print('✓ AutoGen:', autogen.__version__)
print('✓ Semantic Kernel:', semantic_kernel.__version__)
print('✓ OpenAI SDK:', openai.__version__)
print('✓ python-dotenv OK')
"
```
