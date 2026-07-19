using System.Text;
using MFA.CSharp.Part2.Examples;

Console.OutputEncoding = Encoding.UTF8;

// El ejemplo 15 arranca un servidor MCP como proceso hijo, reutilizando ESTE mismo
// ejecutable con el argumento 'mcp-server'. Así todo vive en un único proyecto.
if (args.Length > 0 && args[0].Trim() is "mcp-server")
{
    await McpCalculatorServer.RunAsync();
    return;
}

// Catálogo de ejemplos: clave, título y método a ejecutar.
var examples = new (string Key, string Title, Func<Task> Run)[]
{
    ("11", "Sesiones con auto-serialización (persistencia)", Example11_ThreadingAuto.RunAsync),
    ("12", "Memoria de largo plazo con IA", Example12_LongTermMemoryAI.RunAsync),
    ("13", "Middleware completo (los 3 tipos)", Example13_MiddlewareComplete.RunAsync),
    ("14", "Observabilidad con OpenTelemetry", Example14_ObservabilityComplete.RunAsync),
    ("15", "MCP interactivo (servidor calculadora)", Example15_McpInteractive.RunAsync),
};

// Ejecución directa opcional:  dotnet run -- 13
string? selection = args.Length > 0 ? args[0].Trim() : null;
bool runOnce = selection is not null;

while (true)
{
    if (selection is null)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("  Microsoft Agent Framework — Parte 2 en C# (.NET 10)");
        Console.WriteLine("  Capacidades transversales");
        Console.WriteLine("  Autor: Fernando Valdés Herrera");
        Console.WriteLine(new string('=', 70));
        foreach (var e in examples) Console.WriteLine($"  {e.Key}. {e.Title}");
        Console.WriteLine("   q. Salir");
        Console.Write("\nElige un ejemplo: ");
        selection = Console.ReadLine()?.Trim();
    }

    if (selection is null || selection is "q" or "quit" or "exit") break;

    var chosen = Array.Find(examples, e => e.Key == selection);
    if (chosen.Run is null)
    {
        Console.WriteLine($"⚠️  Opción '{selection}' no válida.");
    }
    else
    {
        try
        {
            await chosen.Run();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"\n❌ Error ejecutando el ejemplo: {ex.Message}");
        }
    }

    if (runOnce) break;
    selection = null; // volver a mostrar el menú
}

Console.WriteLine("\n👋 ¡Hasta luego!");
