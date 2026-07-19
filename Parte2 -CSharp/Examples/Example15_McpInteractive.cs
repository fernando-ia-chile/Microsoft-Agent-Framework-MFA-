using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;
using MFA.CSharp.Part2.Infrastructure;

namespace MFA.CSharp.Part2.Examples;

/// <summary>
/// 15 · MCP interactivo — agente + servidor de calculadora.
/// Equivalente C# de new_15_mcp_interactive.py.
///
/// Objetivo pedagógico: mostrar que un agente puede usar herramientas que NO
/// están en su código, sino que vienen de un servidor MCP externo y que descubre
/// en tiempo de ejecución.
///
/// Cómo funciona esta demo:
///   1. Se lanza el servidor MCP como proceso hijo (ver McpCalculatorServer.cs).
///   2. Cliente y servidor se hablan por STDIO con mensajes JSON-RPC.
///   3. El agente descubre las tools del servidor (sumar, dividir, raiz_cuadrada...).
///   4. Tú preguntas en lenguaje natural y el agente decide qué tool llamar.
///
/// Un solo proyecto: en vez de un ejecutable aparte, el cliente relanza ESTE mismo
/// ejecutable con el argumento 'mcp-server'. Así la demo funciona offline y se
/// puede LEER el código del servidor, que es la mitad interesante de MCP.
/// </summary>
internal static class Example15_McpInteractive
{
    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 75));
        Console.WriteLine("🔌 DEMO 15: MCP INTERACTIVO - Servidor de calculadora");
        Console.WriteLine(new string('=', 75));
        Console.WriteLine("""

            Esta demo conecta el agente a un servidor MCP LOCAL.

            CÓMO FUNCIONA:
            1. Se lanza el servidor MCP como proceso hijo
            2. Cliente y servidor se comunican por STDIO (JSON-RPC)
            3. El agente DESCUBRE las tools del servidor en tiempo de ejecución
            4. Tú preguntas en lenguaje natural y el agente elige qué tool usar

            Lo interesante: el agente no tiene ninguna función matemática en su código.
            Todo lo que sabe hacer con números se lo da el servidor MCP.
            """);

        // Ruta al ejecutable actual: relanzamos este mismo programa en modo servidor.
        string ejecutable = Environment.ProcessPath
            ?? throw new InvalidOperationException("No se pudo determinar la ruta del ejecutable.");

        try
        {
            Console.WriteLine("Iniciando el servidor MCP de calculadora...");
            Console.WriteLine($"Comando: {Path.GetFileName(ejecutable)} mcp-server\n");

            // El transporte stdio lanza el proceso hijo y mantiene la conexión.
            // 'await using' garantiza que el servidor se cierre al terminar.
            await using McpClient mcpClient = await McpClient.CreateAsync(
                new StdioClientTransport(new StdioClientTransportOptions
                {
                    Name = "calculadora",
                    Command = ejecutable,
                    Arguments = ["mcp-server"],
                }));

            Console.WriteLine("✅ ¡Servidor MCP iniciado!\n");

            // Descubrimiento en tiempo de ejecución: le preguntamos al servidor
            // qué herramientas ofrece. El agente no las conoce de antemano.
            IList<McpClientTool> mcpTools = await mcpClient.ListToolsAsync();
            Console.WriteLine($"🔧 Tools descubiertas ({mcpTools.Count}): " +
                              $"{string.Join(", ", mcpTools.Select(t => t.Name))}\n");

            Console.WriteLine("Creando el agente con las tools del servidor MCP...");

            // Las tools de MCP son AITool, así que se pasan igual que cualquier otra.
            AIAgent agent = AzureAgentFactory.CreateAgent(
                instructions: "Eres un asistente matemático. Usa SIEMPRE las herramientas de " +
                              "la calculadora para hacer cálculos, nunca calcules de cabeza. " +
                              "Explica brevemente los pasos que seguiste.",
                name: "CalculadoraMCP",
                tools: [.. mcpTools.Cast<AITool>()]);

            Console.WriteLine("✅ ¡Agente listo con la calculadora MCP!\n");

            Console.WriteLine(new string('=', 75));
            Console.WriteLine("MODO INTERACTIVO");
            Console.WriteLine(new string('=', 75));
            Console.WriteLine("""

                Prueba con estos ejemplos:
                1. "¿Cuánto es 15 * 23 + 45?"
                2. "Calcula la raíz cuadrada de 256"
                3. "¿Cuánto es 2 elevado a 16?"
                4. "Calcula (100 + 50) * 3 / 2"
                5. "Dame el seno de 45 grados"

                Como hay sesión, también puedes encadenar:
                   "suma 10 y 5"  ->  "ahora divide ese resultado por 3"

                Escribe 'quit' para salir
                """);

            // Sesión para que el agente recuerde el hilo de la conversación.
            AgentSession session = await agent.CreateSessionAsync();

            while (true)
            {
                Console.Write("\n💭 Tú: ");
                string? input = Console.ReadLine()?.Trim();
                if (input is null) break;
                if (input.Length == 0) continue;

                if (input is "quit" or "exit" or "q")
                {
                    Console.WriteLine("\n✅ ¡Gracias por probar MCP! Hasta luego.");
                    break;
                }

                try
                {
                    Console.Write("\n🤖 Agente: ");
                    await foreach (AgentResponseUpdate update in agent.RunStreamingAsync(input, session))
                    {
                        Console.Write(update.Text);
                    }
                    Console.WriteLine();
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"\n❌ Error: {ex.Message}");
                }
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"\n❌ ERROR: {ex.Message}");
            Console.WriteLine("\nDIAGNÓSTICO:");
            Console.WriteLine($"   1. ¿Existe el ejecutable?  {ejecutable}");
            Console.WriteLine("   2. Prueba el servidor a mano:  dotnet run -- mcp-server");
            Console.WriteLine("   3. ¿El Endpoint de appsettings03.json es solo la base, sin /openai/...?");
        }
    }
}
