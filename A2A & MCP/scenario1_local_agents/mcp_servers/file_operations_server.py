"""
Servidor MCP de Operaciones de Archivo - Escenario 1
====================================================
Este servidor publica herramientas de manejo de archivos para los agentes,
mediante el Model Context Protocol (MCP).

Herramientas publicadas:
- read_file:   leer el contenido de un archivo
- write_file:  escribir contenido en un archivo
- list_files:  listar archivos de un directorio
- delete_file: borrar un archivo
- file_info:   obtener información de un archivo

Uso:
    python file_operations_server.py          # arranca en modo stdio

Normalmente NO se ejecuta a mano: lo lanza el Agente Ejecutor como subproceso
a través de `MCPStdioTool`.

Modernizado al SDK de MCP 1.28.1:
- `@mcp.tool()` a secas  ->  `title`, `description` y `annotations=ToolAnnotations(...)`
- Parámetros sin describir ->  `Annotated[..., Field(description=...)]`
- Todo devolvía `str`     ->  **salida estructurada** con modelos Pydantic
- Errores como texto      ->  **excepciones**, que MCP transporta como error de tool
- `FastMCP(nombre)`       ->  `FastMCP(nombre, instructions=...)`

-------------------------------------------------------------------------------
ORDEN DE EJECUCIÓN (los comentarios [n] del código siguen esta numeración)
-------------------------------------------------------------------------------
  [1]      Crear el servidor FastMCP y declarar sus `instructions`
  [2]      Anclar el espacio de trabajo (BASE_DIR)
  [3]      Modelos de salida estructurada
  [4]      get_safe_path -> guardián de seguridad, se ejecuta en CADA herramienta
  [5]-[9]  Las cinco herramientas publicadas por MCP
  [10]     main() -> arranca el servidor sobre transporte stdio

Convención de los comentarios:
  🔌 MCP   = instrucción propia del Model Context Protocol (materia de estudio)
  🔒 Seg.  = control de seguridad
  🔧 Infra = Python/entorno, no es del protocolo
-------------------------------------------------------------------------------
"""

import logging
import pathlib
import sys
from datetime import datetime
from typing import Annotated

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
    "file-operations-server",
    instructions=(
        "Servidor de operaciones de archivo para agentes. Permite leer, escribir, "
        "listar, borrar y consultar archivos dentro de un espacio de trabajo aislado. "
        "Todas las rutas son relativas a ese espacio: no se puede salir de él."
    ),
)

# [2] 🔒 Seg.: directorio base de todas las operaciones. El espacio de trabajo queda
#     aislado del resto del disco.
#     ⚠️ Antes era pathlib.Path("./agent_workspace"), relativo al DIRECTORIO DE
#     TRABAJO: al lanzarse como subproceso MCP, el espacio cambiaba según desde
#     dónde se ejecutara. Ahora se ancla al directorio del escenario.
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent / "agent_workspace"
BASE_DIR.mkdir(exist_ok=True)


# =============================================================================
# [3] MODELOS DE SALIDA ESTRUCTURADA
# =============================================================================
# 🔌 MCP: con salida estructurada, el servidor no devuelve un texto suelto sino un
#    objeto con esquema. El cliente recibe el JSON Schema junto con la herramienta,
#    así que el modelo sabe QUÉ campos va a recibir antes de llamarla.


class ResultadoOperacion(BaseModel):
    """Resultado de una operación que modifica un archivo."""

    archivo: str = Field(description="Nombre del archivo afectado")
    exito: bool = Field(description="Indica si la operación se completó")
    mensaje: str = Field(description="Descripción legible de lo ocurrido")
    caracteres: int = Field(default=0, description="Número de caracteres escritos")


class ArchivoListado(BaseModel):
    """Una entrada dentro de un listado de directorio."""

    nombre: str = Field(description="Ruta relativa al espacio de trabajo")
    tipo: str = Field(description="ARCHIVO o DIRECTORIO")
    tamano_bytes: int = Field(description="Tamaño en bytes")
    modificado: str = Field(description="Fecha de última modificación")


class ListadoArchivos(BaseModel):
    """Resultado de listar un directorio."""

    directorio: str = Field(description="Directorio consultado")
    patron: str = Field(description="Patrón de búsqueda aplicado")
    total: int = Field(description="Cantidad de coincidencias encontradas")
    archivos: list[ArchivoListado] = Field(description="Entradas encontradas")


class InfoArchivo(BaseModel):
    """Información detallada de un archivo."""

    nombre: str = Field(description="Nombre del archivo")
    tipo: str = Field(description="ARCHIVO o DIRECTORIO")
    tamano_bytes: int = Field(description="Tamaño en bytes")
    creado: str = Field(description="Fecha de creación")
    modificado: str = Field(description="Fecha de última modificación")
    accedido: str = Field(description="Fecha de último acceso")
    ruta_absoluta: str = Field(description="Ruta absoluta en el disco")


# =============================================================================
# [4] GUARDIÁN DE SEGURIDAD — se ejecuta al principio de CADA herramienta
# =============================================================================
def get_safe_path(filename: str) -> pathlib.Path:
    """
    Devuelve una ruta segura dentro del espacio de trabajo.

    Args:
        filename: nombre o ruta relativa solicitada

    Returns:
        Objeto Path dentro del directorio base.

    Raises:
        ValueError: si la ruta intenta salirse del directorio base.
    """
    requested_path = BASE_DIR / filename
    resolved_path = requested_path.resolve()

    # [4.1] 🔒 Seg.: comprobación anti-escape (evita rutas del tipo "../../secreto").
    #       ⚠️ Antes se usaba str.startswith(), que es comparación de TEXTO, no de
    #       rutas: un directorio hermano llamado "agent_workspace_evil" pasaba el
    #       filtro. Path.is_relative_to() compara por componentes y no tiene ese fallo.
    if not resolved_path.is_relative_to(BASE_DIR.resolve()):
        raise ValueError(f"Acceso denegado: la ruta '{filename}' está fuera del espacio permitido")

    return resolved_path


# =============================================================================
# [5] HERRAMIENTA MCP: leer un archivo
# =============================================================================
# 🔌 MCP: los `annotations` son PISTAS DE COMPORTAMIENTO para el cliente. No cambian
#    lo que hace la función: describen qué efectos tiene, para que el cliente pueda
#    decidir si pedir confirmación al usuario, si puede reintentar, etc.
#      - readOnlyHint    -> no modifica nada
#      - destructiveHint -> puede destruir datos
#      - idempotentHint  -> repetirla da el mismo resultado
#      - openWorldHint   -> toca sistemas externos (internet, etc.)
@mcp.tool(
    title="Leer archivo",
    description="Lee y devuelve el contenido completo de un archivo de texto.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False),
)
def read_file(
    filename: Annotated[str, Field(description="Nombre del archivo, relativo al espacio de trabajo")],
) -> str:
    """Lee el contenido de un archivo de texto."""
    file_path = get_safe_path(filename)

    # [5.1] Los errores se lanzan como EXCEPCIÓN. MCP las transporta al cliente como
    #       error de herramienta, y el agente puede explicárselo al usuario.
    #       Antes se devolvía el texto "Error: ..." como si fuera contenido válido,
    #       de modo que el modelo no podía distinguir un fallo de un archivo cuyo
    #       contenido empezara por "Error:".
    if not file_path.exists():
        raise FileNotFoundError(f"El archivo '{filename}' no existe.")

    if not file_path.is_file():
        raise ValueError(f"'{filename}' no es un archivo.")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise ValueError(
            f"No se puede leer '{filename}' como texto: podría ser un archivo binario."
        ) from e


# =============================================================================
# [6] HERRAMIENTA MCP: escribir un archivo
# =============================================================================
@mcp.tool(
    title="Escribir archivo",
    description=(
        "Escribe contenido en un archivo del espacio de trabajo. "
        "Por defecto sobrescribe; con append=True añade al final."
    ),
    # 🔌 MCP: no es de solo lectura y puede sobrescribir, así que NO es idempotente
    #    cuando append=True (cada llamada añade más texto).
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False),
)
def write_file(
    filename: Annotated[str, Field(description="Nombre del archivo a escribir")],
    content: Annotated[str, Field(description="Contenido que se va a guardar")],
    append: Annotated[bool, Field(description="True para añadir al final en vez de sobrescribir")] = False,
) -> ResultadoOperacion:
    """Escribe contenido en un archivo."""
    file_path = get_safe_path(filename)

    # [6.1] Crear los directorios intermedios si no existen.
    file_path.parent.mkdir(parents=True, exist_ok=True)

    modo = "a" if append else "w"
    with open(file_path, modo, encoding="utf-8") as f:
        f.write(content)

    accion = "añadido a" if append else "escrito en"

    # [6.2] 🔌 MCP: devolver el modelo Pydantic. El cliente recibe además su esquema.
    return ResultadoOperacion(
        archivo=filename,
        exito=True,
        mensaje=f"Contenido {accion} '{filename}' correctamente ({len(content)} caracteres)",
        caracteres=len(content),
    )


# =============================================================================
# [7] HERRAMIENTA MCP: listar archivos
# =============================================================================
@mcp.tool(
    title="Listar archivos",
    description="Lista los archivos de un directorio del espacio de trabajo, con filtro opcional.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False),
)
def list_files(
    directory: Annotated[str, Field(description="Directorio a listar, relativo al espacio de trabajo")] = ".",
    pattern: Annotated[str, Field(description="Patrón glob, p. ej. '*.txt'")] = "*",
) -> ListadoArchivos:
    """Lista los archivos de un directorio."""
    dir_path = get_safe_path(directory)

    if not dir_path.exists():
        raise FileNotFoundError(f"El directorio '{directory}' no existe.")

    if not dir_path.is_dir():
        raise ValueError(f"'{directory}' no es un directorio.")

    # [7.1] Recorrer las coincidencias y armar una entrada por cada una.
    entradas: list[ArchivoListado] = []
    for ruta in sorted(dir_path.glob(pattern)):
        stat = ruta.stat()
        entradas.append(
            ArchivoListado(
                nombre=str(ruta.relative_to(BASE_DIR)),
                tipo="DIRECTORIO" if ruta.is_dir() else "ARCHIVO",
                tamano_bytes=stat.st_size if ruta.is_file() else 0,
                modificado=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            )
        )

    # [7.2] `total` viaja explícito en la respuesta. Con la salida en texto plano
    #       anterior había que contar las líneas para saber cuántos había.
    return ListadoArchivos(
        directorio=directory,
        patron=pattern,
        total=len(entradas),
        archivos=entradas,
    )


# =============================================================================
# [8] HERRAMIENTA MCP: borrar un archivo
# =============================================================================
@mcp.tool(
    title="Borrar archivo",
    description="Borra un archivo del espacio de trabajo. La operación no se puede deshacer.",
    # 🔌 MCP: destructiveHint=True avisa al cliente de que esta herramienta DESTRUYE
    #    datos. Es la pista que permite exigir aprobación humana antes de ejecutarla
    #    (en MFA: approval_mode="always_require" en la herramienta MCP del agente).
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False),
)
def delete_file(
    filename: Annotated[str, Field(description="Nombre del archivo a borrar")],
) -> ResultadoOperacion:
    """Borra un archivo."""
    file_path = get_safe_path(filename)

    if not file_path.exists():
        raise FileNotFoundError(f"El archivo '{filename}' no existe.")

    if file_path.is_dir():
        raise ValueError(f"'{filename}' es un directorio, no un archivo.")

    file_path.unlink()

    return ResultadoOperacion(
        archivo=filename,
        exito=True,
        mensaje=f"Archivo '{filename}' borrado correctamente",
    )


# =============================================================================
# [9] HERRAMIENTA MCP: información de un archivo
# =============================================================================
@mcp.tool(
    title="Información de archivo",
    description="Devuelve el tamaño y las fechas de creación, modificación y acceso de un archivo.",
    annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False),
)
def file_info(
    filename: Annotated[str, Field(description="Nombre del archivo a consultar")],
) -> InfoArchivo:
    """Obtiene información detallada de un archivo."""
    file_path = get_safe_path(filename)

    if not file_path.exists():
        raise FileNotFoundError(f"'{filename}' no existe.")

    stat = file_path.stat()
    formato = "%Y-%m-%d %H:%M:%S"

    return InfoArchivo(
        nombre=filename,
        tipo="DIRECTORIO" if file_path.is_dir() else "ARCHIVO",
        tamano_bytes=stat.st_size,
        creado=datetime.fromtimestamp(stat.st_ctime).strftime(formato),
        modificado=datetime.fromtimestamp(stat.st_mtime).strftime(formato),
        accedido=datetime.fromtimestamp(stat.st_atime).strftime(formato),
        ruta_absoluta=str(file_path.resolve()),
    )


# =============================================================================
# [10] ARRANQUE DEL SERVIDOR
# =============================================================================
def main():
    """Arranca el servidor MCP de operaciones de archivo sobre transporte stdio."""
    # [10.1] 🚨 En transporte stdio, **stdout ES el canal JSON-RPC**: cualquier
    #        print() hacia stdout corrompe el protocolo y el cliente corta con
    #        "Connection closed". Por eso los mensajes informativos van a stderr.
    # [10.2] 🔧 Infra: se fuerza UTF-8 porque la consola de Windows usa cp1252 y
    #        los emojis provocan UnicodeEncodeError al arrancar el subproceso.
    if sys.platform == "win32":
        sys.stderr.reconfigure(encoding="utf-8")

    # [10.3] 🔧 Infra: bajar el logging. Al correr como subproceso, su stderr se
    #        mezcla con la interfaz del agente y taparía la demostración.
    logging.getLogger().setLevel(logging.WARNING)
    for _ruidoso in ("mcp", "httpx", "httpcore"):
        logging.getLogger(_ruidoso).setLevel(logging.WARNING)

    print("📁 Servidor MCP de Archivos iniciando (transporte: stdio)", file=sys.stderr)
    print(f"📡 Nombre del servidor: {mcp.name}", file=sys.stderr)
    print(f"📂 Espacio de trabajo: {BASE_DIR.resolve()}", file=sys.stderr)
    print("🔧 Herramientas: read_file, write_file, list_files, delete_file, file_info", file=sys.stderr)
    print("🚀 Listo para recibir conexiones de agentes...", file=sys.stderr)

    # [10.4] 🔌 MCP: ejecutar el servidor. `stdio` es el transporte para agentes
    #        locales lanzados como subproceso; existen también `sse` y
    #        `streamable-http` para servidores remotos.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
