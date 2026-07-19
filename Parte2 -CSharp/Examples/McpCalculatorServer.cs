using System.ComponentModel;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;

namespace MFA.CSharp.Part2.Examples;

/// <summary>
/// Servidor MCP de calculadora — el "otro lado" del ejemplo 15.
/// Equivalente C# de mcp_calculator_server.py.
///
/// Esto NO es código del Agent Framework: es un servidor MCP independiente, que
/// podría consumir cualquier cliente MCP (Claude Desktop, VS Code, otro agente).
///
/// ¿Qué es MCP?
///   Model Context Protocol: un estándar para exponer herramientas a modelos de
///   lenguaje. La gracia es que servidor y cliente se desarrollan por separado:
///   este archivo no sabe nada de Azure OpenAI ni del Agent Framework.
///
/// ¿Cómo se comunica?
///   Por STDIO: el cliente lanza el proceso y se hablan por entrada/salida
///   estándar con mensajes JSON-RPC. Por eso el servidor NUNCA debe escribir con
///   Console.WriteLine a la salida estándar: ensuciaría el canal del protocolo.
///   Los logs van a la salida de ERROR (stderr), que sí es segura.
///
/// No hace falta ejecutarlo a mano: el ejemplo 15 relanza ESTE mismo ejecutable
/// con el argumento 'mcp-server', de modo que todo vive en un único proyecto.
/// </summary>
internal static class McpCalculatorServer
{
    public static async Task RunAsync()
    {
        var builder = Host.CreateApplicationBuilder();

        // CRÍTICO: redirigir los logs a stderr. Si fueran a stdout romperían el
        // canal JSON-RPC que comparten cliente y servidor.
        builder.Logging.AddConsole(options => options.LogToStandardErrorThreshold = LogLevel.Trace);

        // Registramos el servidor MCP sobre stdio y publicamos como tools todos
        // los métodos marcados con [McpServerTool] de esta clase.
        builder.Services
            .AddMcpServer()
            .WithStdioServerTransport()
            .WithTools<CalculadoraTools>();

        await builder.Build().RunAsync();
    }

    /// <summary>
    /// Las herramientas que publica el servidor. Los nombres y las descripciones
    /// viajan al modelo: son lo que le permite decidir cuál usar, así que conviene
    /// que sean descriptivos.
    /// </summary>
    [McpServerToolType]
    internal sealed class CalculadoraTools
    {
        [McpServerTool(Name = "sumar"), Description("Suma dos números.")]
        public static double Sumar(double a, double b) => a + b;

        [McpServerTool(Name = "restar"), Description("Resta el segundo número al primero.")]
        public static double Restar(double a, double b) => a - b;

        [McpServerTool(Name = "multiplicar"), Description("Multiplica dos números.")]
        public static double Multiplicar(double a, double b) => a * b;

        [McpServerTool(Name = "dividir"), Description("Divide el primer número por el segundo.")]
        public static double Dividir(double a, double b)
            => b == 0 ? throw new ArgumentException("No se puede dividir por cero") : a / b;

        [McpServerTool(Name = "potencia"), Description("Eleva un número a una potencia.")]
        public static double Potencia(double numeroBase, double exponente) => Math.Pow(numeroBase, exponente);

        [McpServerTool(Name = "raiz_cuadrada"), Description("Calcula la raíz cuadrada de un número.")]
        public static double RaizCuadrada(double numero)
            => numero < 0
                ? throw new ArgumentException("No se puede sacar la raíz cuadrada de un número negativo")
                : Math.Sqrt(numero);

        [McpServerTool(Name = "seno_grados"), Description("Calcula el seno de un ángulo expresado en grados.")]
        public static double SenoGrados(double grados) => Math.Sin(grados * Math.PI / 180.0);

        [McpServerTool(Name = "coseno_grados"), Description("Calcula el coseno de un ángulo expresado en grados.")]
        public static double CosenoGrados(double grados) => Math.Cos(grados * Math.PI / 180.0);
    }
}
