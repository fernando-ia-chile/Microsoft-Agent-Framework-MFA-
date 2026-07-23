"""
Servidor MCP de Clima - Escenario 1
===================================
Este servidor publica herramientas meteorológicas para los agentes,
mediante el Model Context Protocol (MCP).

Herramientas publicadas:
- get_weather:  clima actual de una ciudad (mundial)
- get_forecast: pronóstico de varios días (mundial)
- get_alerts:   avisos meteorológicos derivados de las condiciones actuales

Usa la API de Open-Meteo (gratuita, sin clave de API): https://open-meteo.com/

Uso:
    python weather_server.py          # arranca en modo stdio

Normalmente NO se ejecuta a mano: lo lanza el Agente de Investigación como
subproceso a través de `MCPStdioTool`.

Modernizado al SDK de MCP 1.28.1:
- `@mcp.tool()` a secas   ->  `title`, `description` y `annotations=ToolAnnotations(...)`
- Parámetros sin describir ->  `Annotated[..., Field(description=...)]`
- Todo devolvía `str` con emojis embebidos  ->  **salida estructurada** (Pydantic)
- Errores como texto      ->  **excepciones**, que MCP transporta como error de tool
- `FastMCP(nombre)`       ->  `FastMCP(nombre, instructions=...)`

-------------------------------------------------------------------------------
ORDEN DE EJECUCIÓN (los comentarios [n] del código siguen esta numeración)
-------------------------------------------------------------------------------
  [1]      Crear el servidor FastMCP y declarar sus `instructions`
  [2]      Constantes: endpoints, códigos de tiempo y umbrales de aviso
  [3]      Modelos de salida estructurada
  [4]      make_api_request -> llamada HTTP común
  [5]      geocode_city     -> ciudad -> coordenadas (se usa en las TRES herramientas)
  [6]-[8]  Las tres herramientas publicadas por MCP
  [9]      main() -> arranca el servidor sobre transporte stdio

Convención de los comentarios:
  🔌 MCP   = instrucción propia del Model Context Protocol (materia de estudio)
  🌍 API   = relativo a la API externa de Open-Meteo
  🔧 Infra = Python/entorno, no es del protocolo
-------------------------------------------------------------------------------
"""

import logging
import sys
from typing import Annotated, Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

# 🔧 Infra: cargar variables de entorno (este servidor no necesita credenciales).
load_dotenv()

# [1] 🔌 MCP: crear el servidor. `instructions` es la descripción que el servidor
#     anuncia al cliente durante el handshake: le explica al agente para qué sirve
#     este servidor en conjunto, más allá de cada herramienta suelta.
mcp = FastMCP(
    "weather-server",
    instructions=(
        "Servidor meteorológico para agentes. Proporciona clima actual, pronóstico "
        "y avisos de cualquier ciudad del mundo usando la API de Open-Meteo. "
        "Acepta nombres de ciudad en español o en inglés; indicar el país mejora "
        "la precisión cuando el nombre se repite en varios lugares."
    ),
)

# =============================================================================
# [2] CONSTANTES
# =============================================================================
# 🌍 API: endpoints de Open-Meteo (no requieren clave).
GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_API = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "MAF-A2A-Weather-Server/1.0"

# 🌍 API: códigos WMO de estado del tiempo, traducidos.
# ⚠️ Antes había DOS diccionarios distintos (uno con emojis para el clima actual y
#    otro sin ellos para el pronóstico), que podían desincronizarse. Ahora es uno solo
#    y sin emojis: los datos son datos, y del formato se encarga el agente.
CODIGOS_TIEMPO: dict[int, str] = {
    0: "cielo despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "cubierto",
    45: "niebla",
    48: "niebla con escarcha",
    51: "llovizna ligera",
    53: "llovizna",
    55: "llovizna intensa",
    61: "lluvia ligera",
    63: "lluvia",
    65: "lluvia intensa",
    71: "nevada ligera",
    73: "nevada",
    75: "nevada intensa",
    77: "granos de nieve",
    80: "chubascos ligeros",
    81: "chubascos",
    82: "chubascos fuertes",
    85: "chubascos de nieve ligeros",
    86: "chubascos de nieve",
    95: "tormenta eléctrica",
    96: "tormenta con granizo",
}

# 🌍 API: umbrales que disparan un aviso. Antes estaban escritos a mano dentro del
#    código de la herramienta; como constantes con nombre se entienden y se ajustan.
UMBRAL_RACHAS_FUERTES_KMH = 60
UMBRAL_VIENTO_FUERTE_KMH = 40
UMBRAL_LLUVIA_INTENSA_MM = 20

# 🌍 API: rango admitido por Open-Meteo para el pronóstico.
DIAS_MIN, DIAS_MAX = 1, 16


# =============================================================================
# [3] MODELOS DE SALIDA ESTRUCTURADA
# =============================================================================
# 🔌 MCP: con salida estructurada, el servidor no devuelve un texto con emojis sino
#    un objeto con esquema. El cliente recibe el JSON Schema junto con la herramienta,
#    así que el modelo sabe QUÉ campos va a recibir antes de llamarla, y puede
#    redactar el informe en el idioma y el formato que quiera.


class ClimaActual(BaseModel):
    """Condiciones meteorológicas actuales de una ubicación."""

    ubicacion: str = Field(description="Nombre completo de la ubicación encontrada")
    hora_local: str = Field(description="Hora local de la medición")
    temperatura_c: float = Field(description="Temperatura en grados Celsius")
    sensacion_termica_c: float = Field(description="Sensación térmica en grados Celsius")
    condicion: str = Field(description="Descripción del estado del tiempo")
    humedad_pct: int = Field(description="Humedad relativa en porcentaje")
    nubosidad_pct: int = Field(description="Cobertura de nubes en porcentaje")
    viento_kmh: float = Field(description="Velocidad del viento en km/h")
    viento_direccion_grados: int = Field(description="Dirección del viento en grados")
    rachas_kmh: float = Field(description="Rachas máximas de viento en km/h")
    precipitacion_mm: float = Field(description="Precipitación acumulada en mm")


class DiaPronostico(BaseModel):
    """Pronóstico de un día concreto."""

    fecha: str = Field(description="Fecha del pronóstico (AAAA-MM-DD)")
    temperatura_min_c: float = Field(description="Temperatura mínima prevista")
    temperatura_max_c: float = Field(description="Temperatura máxima prevista")
    condicion: str = Field(description="Estado del tiempo previsto")
    precipitacion_mm: float = Field(description="Precipitación total prevista en mm")
    viento_max_kmh: float = Field(description="Viento máximo previsto en km/h")


class Pronostico(BaseModel):
    """Pronóstico de varios días para una ubicación."""

    ubicacion: str = Field(description="Nombre completo de la ubicación encontrada")
    dias: int = Field(description="Cantidad de días incluidos")
    pronostico: list[DiaPronostico] = Field(description="Pronóstico día a día")


class AvisosMeteorologicos(BaseModel):
    """Avisos derivados de las condiciones actuales."""

    ubicacion: str = Field(description="Nombre completo de la ubicación encontrada")
    hay_avisos: bool = Field(description="True si se detectó alguna condición adversa")
    avisos: list[str] = Field(description="Lista de avisos detectados")


# =============================================================================
# [4] LLAMADA HTTP COMÚN
# =============================================================================
async def make_api_request(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Realiza una petición a las APIs de Open-Meteo.

    Raises:
        ConnectionError: si la API no responde correctamente.
    """
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # [4.1] Antes se devolvía None y cada herramienta lo traducía a un texto
            #       de error. Ahora se lanza: MCP lo transporta como error de tool y
            #       el agente puede explicar al usuario qué pasó.
            raise ConnectionError(f"No se pudo contactar con la API de Open-Meteo: {e}") from e


# =============================================================================
# [5] GEOCODIFICACIÓN — ciudad -> coordenadas (la usan las TRES herramientas)
# =============================================================================
async def geocode_city(city: str, country: str = "") -> tuple[float, float, str]:
    """
    Obtiene las coordenadas de una ciudad con la API de geocodificación de Open-Meteo.

    Returns:
        Tupla (latitud, longitud, nombre_completo).

    Raises:
        LookupError: si no se encuentra la ciudad.
    """
    # [5.1] ⚠️ La API de geocodificación de Open-Meteo **NO acepta un parámetro
    #       `country`**: lo ignora en silencio. El código anterior lo enviaba y creía
    #       estar filtrando, así que "Tokio, Japón" devolvía Tokio (Dakota del Norte).
    #       Solución: pedir VARIOS candidatos y filtrar por país aquí.
    # [5.2] language="es" permite buscar por el nombre en español ("Tokio", "Londres")
    #       y devuelve los nombres de país también en español.
    params = {"name": city, "count": 10, "language": "es", "format": "json"}

    data = await make_api_request(GEOCODING_API, params)

    if not data or not data.get("results"):
        raise LookupError(f"No se encontró la ubicación '{city}'. Revisa la ortografía.")

    resultados = data["results"]

    # [5.3] Filtrar por país: se acepta tanto el nombre ("Japón") como el código
    #       ISO de dos letras ("JP"), sin distinguir mayúsculas.
    if country:
        objetivo = country.strip().casefold()
        coincidencias = [
            r
            for r in resultados
            if objetivo in (r.get("country", "").casefold(), r.get("country_code", "").casefold())
        ]
        # Si el país no coincide con ninguno, se conserva el mejor resultado global
        # en vez de fallar: es preferible responder algo a no responder.
        resultados = coincidencias or resultados

    result = resultados[0]
    nombre = result["name"]
    pais = result.get("country", "")
    region = result.get("admin1", "")

    nombre_completo = f"{nombre}, {region}, {pais}" if region else f"{nombre}, {pais}"

    return (result["latitude"], result["longitude"], nombre_completo)


# =============================================================================
# [6] HERRAMIENTA MCP: clima actual
# =============================================================================
# 🔌 MCP: los `annotations` son PISTAS DE COMPORTAMIENTO para el cliente. No cambian
#    lo que hace la función: describen qué efectos tiene.
#    ⚠️ Aquí `openWorldHint=True`, al contrario que en el servidor de archivos: estas
#    herramientas consultan un sistema EXTERNO (Open-Meteo), así que pueden fallar
#    por red y su resultado cambia con el tiempo aunque los argumentos sean iguales.
@mcp.tool(
    title="Clima actual",
    description=(
        "Consulta las condiciones meteorológicas actuales de cualquier ciudad del "
        "mundo. Indicar el país mejora la precisión."
    ),
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True),
)
async def get_weather(
    city: Annotated[str, Field(description="Nombre de la ciudad, p. ej. 'Tokio' o 'Londres'")],
    country: Annotated[str, Field(description="País o código ISO, p. ej. 'Japón' o 'JP'")] = "",
) -> ClimaActual:
    """Obtiene el clima actual de una ciudad."""
    # [6.1] Traducir el nombre de la ciudad a coordenadas (ver [5]).
    lat, lon, ubicacion = await geocode_city(city, country)

    # [6.2] 🌍 API: pedir las variables actuales que interesan.
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
            "rain,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        ),
        "timezone": "auto",
    }

    data = await make_api_request(WEATHER_API, params)

    if "current" not in data:
        raise ValueError(f"La API no devolvió datos actuales para {ubicacion}")

    actual = data["current"]

    # [6.3] 🔌 MCP: devolver el modelo Pydantic. El cliente recibe además su esquema,
    #       y el agente redacta el informe con los campos que necesite.
    return ClimaActual(
        ubicacion=ubicacion,
        hora_local=actual.get("time", ""),
        temperatura_c=actual.get("temperature_2m", 0.0),
        sensacion_termica_c=actual.get("apparent_temperature", 0.0),
        condicion=CODIGOS_TIEMPO.get(actual.get("weather_code", 0), "desconocido"),
        humedad_pct=actual.get("relative_humidity_2m", 0),
        nubosidad_pct=actual.get("cloud_cover", 0),
        viento_kmh=actual.get("wind_speed_10m", 0.0),
        viento_direccion_grados=actual.get("wind_direction_10m", 0),
        rachas_kmh=actual.get("wind_gusts_10m", 0.0),
        precipitacion_mm=actual.get("precipitation", 0.0),
    )


# =============================================================================
# [7] HERRAMIENTA MCP: pronóstico
# =============================================================================
@mcp.tool(
    title="Pronóstico del tiempo",
    description="Consulta el pronóstico de los próximos días de cualquier ciudad del mundo.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True),
)
async def get_forecast(
    city: Annotated[str, Field(description="Nombre de la ciudad, p. ej. 'Santiago'")],
    country: Annotated[str, Field(description="País o código ISO, p. ej. 'Chile' o 'CL'")] = "",
    days: Annotated[int, Field(description="Número de días a pronosticar (1 a 16)", ge=1, le=16)] = 5,
) -> Pronostico:
    """Obtiene el pronóstico de varios días de una ciudad."""
    lat, lon, ubicacion = await geocode_city(city, country)

    # [7.1] Ajustar al rango admitido por la API en vez de fallar.
    days = max(DIAS_MIN, min(days, DIAS_MAX))

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": (
            "temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "wind_speed_10m_max,weather_code"
        ),
        "timezone": "auto",
        "forecast_days": days,
    }

    data = await make_api_request(WEATHER_API, params)

    if "daily" not in data:
        raise ValueError(f"La API no devolvió pronóstico para {ubicacion}")

    diario = data["daily"]

    # [7.2] Convertir las listas paralelas que devuelve la API en objetos por día.
    dias_pronostico = [
        DiaPronostico(
            fecha=diario["time"][i],
            temperatura_min_c=diario["temperature_2m_min"][i],
            temperatura_max_c=diario["temperature_2m_max"][i],
            condicion=CODIGOS_TIEMPO.get(diario["weather_code"][i], "desconocido"),
            precipitacion_mm=diario["precipitation_sum"][i],
            viento_max_kmh=diario["wind_speed_10m_max"][i],
        )
        for i in range(len(diario["time"]))
    ]

    return Pronostico(ubicacion=ubicacion, dias=len(dias_pronostico), pronostico=dias_pronostico)


# =============================================================================
# [8] HERRAMIENTA MCP: avisos meteorológicos
# =============================================================================
@mcp.tool(
    title="Avisos meteorológicos",
    description=(
        "Revisa las condiciones actuales de una ciudad y devuelve avisos por viento "
        "fuerte o lluvia intensa. Open-Meteo no publica alertas oficiales: los avisos "
        "se derivan de los valores medidos."
    ),
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True),
)
async def get_alerts(
    city: Annotated[str, Field(description="Nombre de la ciudad, p. ej. 'Melbourne'")],
    country: Annotated[str, Field(description="País o código ISO, p. ej. 'Australia' o 'AU'")] = "",
) -> AvisosMeteorologicos:
    """Obtiene avisos meteorológicos derivados de las condiciones actuales."""
    lat, lon, ubicacion = await geocode_city(city, country)

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m",
        "timezone": "auto",
    }

    data = await make_api_request(WEATHER_API, params)
    actual = data.get("current", {})

    viento = actual.get("wind_speed_10m", 0)
    rachas = actual.get("wind_gusts_10m", 0)
    precipitacion = actual.get("precipitation", 0)

    # [8.1] Comparar contra los umbrales con nombre definidos en [2].
    avisos: list[str] = []

    if rachas > UMBRAL_RACHAS_FUERTES_KMH:
        avisos.append(f"AVISO POR VIENTO FUERTE: rachas de hasta {rachas} km/h")
    elif viento > UMBRAL_VIENTO_FUERTE_KMH:
        avisos.append(f"AVISO POR VIENTO: viento sostenido de {viento} km/h")

    if precipitacion > UMBRAL_LLUVIA_INTENSA_MM:
        avisos.append(f"AVISO POR LLUVIA INTENSA: {precipitacion} mm de precipitación")

    # [8.2] `hay_avisos` viaja explícito: el agente no tiene que deducir la ausencia
    #       de avisos a partir de una frase como "No active weather warnings".
    return AvisosMeteorologicos(
        ubicacion=ubicacion,
        hay_avisos=bool(avisos),
        avisos=avisos,
    )


# =============================================================================
# [9] ARRANQUE DEL SERVIDOR
# =============================================================================
def main():
    """Arranca el servidor MCP de clima sobre transporte stdio."""
    # [9.1] 🚨 En transporte stdio, **stdout ES el canal JSON-RPC**: cualquier
    #       print() hacia stdout corrompe el protocolo y el cliente corta con
    #       "Connection closed". Por eso los mensajes informativos van a stderr.
    # [9.2] 🔧 Infra: se fuerza UTF-8 porque la consola de Windows usa cp1252 y
    #       los emojis provocan UnicodeEncodeError al arrancar el subproceso.
    if sys.platform == "win32":
        sys.stderr.reconfigure(encoding="utf-8")

    # [9.3] 🔧 Infra: bajar el logging. Al correr como subproceso, su stderr se
    #       mezcla con la interfaz del agente y taparía la demostración.
    logging.getLogger().setLevel(logging.WARNING)
    for _ruidoso in ("mcp", "httpx", "httpcore"):
        logging.getLogger(_ruidoso).setLevel(logging.WARNING)

    print("🌤️  Servidor MCP de Clima iniciando (transporte: stdio)", file=sys.stderr)
    print(f"📡 Nombre del servidor: {mcp.name}", file=sys.stderr)
    print("🔧 Herramientas: get_weather, get_forecast, get_alerts", file=sys.stderr)
    print("🌍 Fuente de datos: API de Open-Meteo (sin clave)", file=sys.stderr)
    print("🚀 Listo para recibir conexiones de agentes...", file=sys.stderr)

    # [9.4] 🔌 MCP: ejecutar el servidor. `stdio` es el transporte para agentes
    #       locales lanzados como subproceso; existen también `sse` y
    #       `streamable-http` para servidores remotos.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
