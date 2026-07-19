"""
Servidor MCP de calculadora — el "otro lado" de la demo new_15.

Esto NO es un script del Agent Framework: es un servidor MCP independiente, que
podría consumir cualquier cliente MCP (Claude Desktop, VS Code, otro agente...).
Aquí lo usa `new_15_mcp_interactive.py`.

¿Qué es MCP?
    Model Context Protocol: un protocolo estándar para exponer herramientas a
    modelos de lenguaje. La gracia es que el servidor y el cliente se desarrollan
    por separado: este archivo no sabe nada de Azure OpenAI ni de MFA.

¿Cómo se comunica?
    Por STDIO: el cliente lanza este script como un proceso hijo y se hablan por
    entrada/salida estándar con mensajes JSON-RPC. Por eso el servidor NUNCA debe
    escribir con print() a stdout: ensuciaría el canal del protocolo.

Se ejecuta solo (no hace falta lanzarlo a mano):
    el cliente MCP lo arranca con `sys.executable mcp_calculator_server.py`.
"""

import math

from mcp.server.fastmcp import FastMCP

# FastMCP arma el servidor y expone como tools las funciones que decoremos.
# El nombre y los docstrings viajan al modelo: son lo que le permite decidir
# cuál herramienta usar, así que conviene que sean descriptivos.
#
# log_level="WARNING": por defecto FastMCP registra cada petición ("Processing
# request of type CallToolRequest") y esos mensajes se cuelan en la salida del
# cliente, en medio de la respuesta del agente. Subimos el umbral para que la
# demo se vea limpia; ponlo en "INFO" si quieres espiar el tráfico del protocolo.
mcp = FastMCP("calculadora", log_level="WARNING")


@mcp.tool()
def sumar(a: float, b: float) -> float:
    """Suma dos números."""
    return a + b


@mcp.tool()
def restar(a: float, b: float) -> float:
    """Resta el segundo número al primero."""
    return a - b


@mcp.tool()
def multiplicar(a: float, b: float) -> float:
    """Multiplica dos números."""
    return a * b


@mcp.tool()
def dividir(a: float, b: float) -> float:
    """Divide el primer número por el segundo."""
    if b == 0:
        raise ValueError("No se puede dividir por cero")
    return a / b


@mcp.tool()
def potencia(base: float, exponente: float) -> float:
    """Eleva un número a una potencia."""
    return base ** exponente


@mcp.tool()
def raiz_cuadrada(numero: float) -> float:
    """Calcula la raíz cuadrada de un número."""
    if numero < 0:
        raise ValueError("No se puede sacar la raíz cuadrada de un número negativo")
    return math.sqrt(numero)


@mcp.tool()
def seno_grados(grados: float) -> float:
    """Calcula el seno de un ángulo expresado en grados."""
    return math.sin(math.radians(grados))


@mcp.tool()
def coseno_grados(grados: float) -> float:
    """Calcula el coseno de un ángulo expresado en grados."""
    return math.cos(math.radians(grados))


if __name__ == "__main__":
    # transport="stdio": el servidor habla por entrada/salida estándar con el
    # proceso que lo lanzó. Es el modo que usa MCPStdioTool.
    mcp.run(transport="stdio")
