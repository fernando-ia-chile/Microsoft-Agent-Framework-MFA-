"""
Ejemplo 06 – Mejores prácticas: seguridad, configuración y reproducibilidad
============================================================================
Este módulo NO llama a ninguna API externa.  Está diseñado para ser leído
y ejecutado como referencia de patrones recomendados cuando construyes
agentes en producción o en un entorno educativo.

Temas cubiertos
---------------
1.  Gestión segura de credenciales (nunca en el código fuente).
2.  Validación de configuración al inicio ("fail fast").
3.  Reintentos con backoff exponencial para llamadas a la API.
4.  Reproducibilidad: semilla aleatoria y temperatura=0.
5.  Límites de seguridad en los agentes (timeouts, max_tokens).
6.  Logging estructurado.
7.  Separación de entornos (dev / staging / prod).
8.  Rate limiting consciente.

Cómo ejecutar (sin costo)
--------------------------
    python examples/06_best_practices.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

# ── 6. Logging estructurado ───────────────────────────────────────────────────
# Best practice: configura el logging una sola vez en el punto de entrada.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("agente_framework")


# ── 1 & 2. Gestión segura de credenciales y validación ───────────────────────

@dataclass
class ConfiguracionAgente:
    """
    Centraliza toda la configuración del agente en un dataclass.

    Por qué usar un dataclass en lugar de leer os.getenv() disperso:
    * Un único lugar para validar que todas las variables estén presentes.
    * Facilita las pruebas unitarias (se puede instanciar con valores ficticios).
    * Hace explícitas las dependencias del agente.
    """

    # Campos obligatorios sin valor por defecto
    api_key: str
    model: str

    # Campos opcionales (para Azure)
    azure_endpoint: Optional[str] = None
    azure_deployment: Optional[str] = None
    azure_api_version: str = "2024-02-01"

    # Parámetros del modelo (best practices de reproducibilidad)
    temperature: float = 0.0       # 0 → determinista
    max_tokens: int = 512
    timeout: int = 60              # segundos

    # Listas de modelos permitidos (evita usar modelos caros por error)
    modelos_permitidos: List[str] = field(
        default_factory=lambda: [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-35-turbo",
            "gpt-4",
        ]
    )

    def __post_init__(self) -> None:
        """Valida la configuración en el momento de la construcción (fail fast)."""
        self._validar_api_key()
        self._validar_modelo()
        self._validar_azure()

    def _validar_api_key(self) -> None:
        if not self.api_key or self.api_key.startswith("sk-..."):
            raise ValueError(
                "api_key no válida. Asegúrate de haber rellenado .env con "
                "tu clave real (nunca hardcodees claves en el código)."
            )

    def _validar_modelo(self) -> None:
        if self.model not in self.modelos_permitidos:
            raise ValueError(
                f"Modelo '{self.model}' no está en la lista de modelos permitidos: "
                f"{self.modelos_permitidos}. Actualiza modelos_permitidos si lo necesitas."
            )

    def _validar_azure(self) -> None:
        # Si se proporciona el endpoint de Azure, el deployment es obligatorio.
        if self.azure_endpoint and not self.azure_deployment:
            raise ValueError(
                "AZURE_OPENAI_DEPLOYMENT es obligatorio cuando se usa Azure OpenAI."
            )

    @classmethod
    def desde_entorno(cls) -> "ConfiguracionAgente":
        """
        Construye ConfiguracionAgente leyendo las variables de entorno.
        Llama a load_dotenv() antes de usar este método.
        """
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )

    def to_llm_config(self) -> Dict[str, Any]:
        """Genera el dict llm_config que espera AutoGen."""
        config_entry: Dict[str, Any] = {
            "model": self.azure_deployment or self.model,
            "api_key": self.api_key,
        }
        if self.azure_endpoint:
            config_entry.update(
                {
                    "base_url": self.azure_endpoint,
                    "api_type": "azure",
                    "api_version": self.azure_api_version,
                }
            )
        return {
            "config_list": [config_entry],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }


# ── 3. Reintentos con backoff exponencial ────────────────────────────────────

def con_reintentos(
    max_intentos: int = 3,
    espera_inicial: float = 1.0,
    backoff: float = 2.0,
    excepciones: tuple = (Exception,),
) -> Callable:
    """
    Decorador de reintentos con backoff exponencial.

    Parámetros
    ----------
    max_intentos   : número máximo de intentos (incluido el primero).
    espera_inicial : segundos a esperar antes del segundo intento.
    backoff        : multiplicador de la espera en cada intento.
    excepciones    : tipos de excepción que disparan el reintento.

    Ejemplo de uso
    --------------
    @con_reintentos(max_intentos=3, excepciones=(TimeoutError, ConnectionError))
    def llamar_api():
        ...
    """
    def decorador(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            espera = espera_inicial
            for intento in range(1, max_intentos + 1):
                try:
                    return func(*args, **kwargs)
                except excepciones as exc:
                    if intento == max_intentos:
                        logger.error(
                            "Función '%s' falló tras %d intentos: %s",
                            func.__name__,
                            max_intentos,
                            exc,
                        )
                        raise
                    logger.warning(
                        "Intento %d/%d falló (%s). Reintentando en %.1fs…",
                        intento,
                        max_intentos,
                        exc,
                        espera,
                    )
                    time.sleep(espera)
                    espera *= backoff
        return wrapper
    return decorador


# ── 7. Separación de entornos ─────────────────────────────────────────────────

class EntornoEjecucion:
    """Detecta el entorno de ejecución y ajusta el comportamiento."""

    ENTORNOS_VALIDOS = {"development", "staging", "production"}

    def __init__(self) -> None:
        self.nombre = os.getenv("APP_ENV", "development").lower()
        if self.nombre not in self.ENTORNOS_VALIDOS:
            raise ValueError(
                f"APP_ENV='{self.nombre}' no es válido. "
                f"Usa uno de: {self.ENTORNOS_VALIDOS}"
            )

    @property
    def es_desarrollo(self) -> bool:
        return self.nombre == "development"

    @property
    def es_produccion(self) -> bool:
        return self.nombre == "production"

    def nivel_log(self) -> str:
        """En producción solo INFO; en desarrollo también DEBUG."""
        return "DEBUG" if self.es_desarrollo else "INFO"

    def max_tokens_seguro(self) -> int:
        """Límite de tokens más estricto en producción para controlar costos."""
        return 256 if self.es_produccion else 512


# ── 8. Rate limiting consciente ──────────────────────────────────────────────

class RateLimiter:
    """
    Implementación simple de rate limiting por token bucket.

    Evita superar el límite de llamadas por minuto de la API.
    En producción, usa librerías especializadas como 'limits' o
    configura rate limiting en Azure API Management.
    """

    def __init__(self, llamadas_por_minuto: int = 20) -> None:
        self.llamadas_por_minuto = llamadas_por_minuto
        self._intervalo = 60.0 / llamadas_por_minuto
        self._ultimo_llamado: float = 0.0

    def esperar_si_necesario(self) -> None:
        """Bloquea hasta que sea seguro hacer la siguiente llamada."""
        ahora = time.monotonic()
        tiempo_transcurrido = ahora - self._ultimo_llamado
        if tiempo_transcurrido < self._intervalo:
            pausa = self._intervalo - tiempo_transcurrido
            logger.debug("Rate limiter: esperando %.2fs", pausa)
            time.sleep(pausa)
        self._ultimo_llamado = time.monotonic()


# ── Demo: ejecutar todas las validaciones sin API ────────────────────────────

def demo_mejores_practicas() -> None:
    """Ejecuta todas las clases/funciones anteriores como demostración."""
    print("=" * 60)
    print("Ejemplo 06 – Mejores prácticas")
    print("=" * 60)

    # ── 7. Entorno
    entorno = EntornoEjecucion()
    print(f"\n[Entorno] APP_ENV = '{entorno.nombre}'")
    print(f"  • ¿Es desarrollo? {entorno.es_desarrollo}")
    print(f"  • Nivel de log:   {entorno.nivel_log()}")
    print(f"  • max_tokens:     {entorno.max_tokens_seguro()}")

    # ── 2. Validación de configuración (con clave ficticia solo para demo)
    print("\n[Configuración] Probando validación fail-fast…")
    try:
        ConfiguracionAgente(api_key="sk-...your-key...", model="gpt-4o-mini")
    except ValueError as exc:
        print(f"  ✓ Error esperado capturado: {exc}")

    try:
        ConfiguracionAgente(api_key="sk-demo1234567890", model="modelo-no-permitido")
    except ValueError as exc:
        print(f"  ✓ Error esperado capturado: {exc}")

    cfg_valida = ConfiguracionAgente(api_key="sk-demo1234567890", model="gpt-4o-mini")
    print(f"  ✓ Configuración válida creada para modelo: {cfg_valida.model}")
    print(f"    temperature={cfg_valida.temperature}, max_tokens={cfg_valida.max_tokens}")

    # ── 3. Reintentos
    print("\n[Reintentos] Probando decorador con_reintentos…")
    intentos = {"n": 0}

    @con_reintentos(max_intentos=3, espera_inicial=0.01, excepciones=(ValueError,))
    def operacion_inestable() -> str:
        intentos["n"] += 1
        if intentos["n"] < 3:
            raise ValueError("Fallo simulado")
        return "Éxito en el intento 3"

    resultado = operacion_inestable()
    print(f"  ✓ {resultado} (tras {intentos['n']} intentos)")

    # ── 8. Rate limiting
    print("\n[Rate Limiting] Probando RateLimiter (3 llamadas rápidas)…")
    limiter = RateLimiter(llamadas_por_minuto=600)  # muy relajado para la demo
    t0 = time.monotonic()
    for i in range(3):
        limiter.esperar_si_necesario()
        print(f"  ✓ Llamada {i + 1} permitida a t={time.monotonic() - t0:.3f}s")

    # ── Resumen de mejores prácticas
    print("\n" + "=" * 60)
    print("RESUMEN – Mejores prácticas implementadas:")
    practicas = [
        "1. Credenciales SIEMPRE en .env, nunca en el código.",
        "2. Validación fail-fast al iniciar la aplicación.",
        "3. Reintentos con backoff exponencial para llamadas a la API.",
        "4. temperature=0 para respuestas reproducibles.",
        "5. max_tokens y timeout explícitos en llm_config.",
        "6. Logging estructurado con timestamps.",
        "7. Separación de entornos: development / staging / production.",
        "8. Rate limiting consciente para no exceder cuotas de la API.",
    ]
    for p in practicas:
        print(f"  ✓ {p}")
    print("=" * 60)


if __name__ == "__main__":
    load_dotenv()
    demo_mejores_practicas()
