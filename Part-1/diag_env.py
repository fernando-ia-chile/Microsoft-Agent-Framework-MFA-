"""
Diagnóstico rápido para el 404 de la demo 03 (Azure OpenAI / Responses API).

Muestra:
  1) Qué variables tiene tu SESIÓN de PowerShell (antes de leer .env03).
  2) Qué valores quedan EFECTIVOS y la URL final que arma el framework.
  3) Prueba en vivo: lista los deployments del recurso y verifica que exista el tuyo.

Ejecuta:  python diag_env.py
"""

import os
import asyncio

KEYS = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "AZURE_OPENAI_API_VERSION")

print("=" * 70)
print("1) Variables en la SESIÓN (antes de leer .env03)")
print("=" * 70)
for k in KEYS:
    print(f"  {k} = {os.environ.get(k)!r}")

# Igual que las demos: leemos el archivo. Con override=True el archivo manda.
from dotenv import load_dotenv
load_dotenv(".env03", override=True)

endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
api_key = os.getenv("AZURE_OPENAI_API_KEY")

print("\n" + "=" * 70)
print("2) Valores EFECTIVOS que usará la demo (tras load_dotenv override=True)")
print("=" * 70)
print(f"  endpoint   = {endpoint!r}")
print(f"  deployment = {deployment!r}")
print(f"  base_url que arma el framework = {endpoint}/openai/v1/")
if "/openai/" in endpoint:
    print("  ⚠️  El endpoint NO debe incluir '/openai/...'. Debe ser solo la base del recurso.")

print("\n" + "=" * 70)
print("3) Prueba en vivo: listar deployments del recurso")
print("=" * 70)


async def main():
    from openai import AsyncAzureOpenAI

    client = AsyncAzureOpenAI(
        base_url=f"{endpoint}/openai/v1/",
        api_key=api_key,
        api_version="preview",
    )
    try:
        models = await client.models.list()
        names = sorted(m.id for m in models.data)
        print("  Deployments disponibles en el recurso:")
        for n in names:
            print(f"    - {n}")
        print(f"\n  ¿Existe tu deployment '{deployment}'? -> {deployment in names}")
        if deployment not in names:
            print("  👉 El nombre del deployment no coincide. Usa EXACTAMENTE el que aparezca arriba.")
    except Exception as e:
        print(f"  ❌ ERROR al conectar/listar: {type(e).__name__}: {str(e)[:300]}")
        print("  👉 Si es 404 aquí, el problema es el ENDPOINT o el recurso, no el deployment.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
