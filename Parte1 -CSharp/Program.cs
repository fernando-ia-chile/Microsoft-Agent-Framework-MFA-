using System.Text;
using MFA.CSharp.Examples;

Console.OutputEncoding = Encoding.UTF8;

// Catálogo de ejemplos: clave, título y método a ejecutar.
var examples = new (string Key, string Title, Func<Task> Run)[]
{
    ("1", "Crear/usar agente en Azure AI Foundry (Foundry)", Example01_CreateAgent.RunAsync),
    ("2", "Usar un agente existente de Foundry", Example02_UseExistingAgent.RunAsync),
    ("3", "Chat directo con Azure OpenAI", Example03_DirectOpenAIChat.RunAsync),
    ("4", "File Search / vector store (Foundry)", Example04_FileSearchTool.RunAsync),
    ("5", "Function tool: calculadora", Example05_FunctionToolCalculator.RunAsync),
    ("6", "Múltiples function tools", Example06_MultipleTools.RunAsync),
    ("7", "Human-in-the-loop (aprobación humana)", Example07_HumanInTheLoop.RunAsync),
    ("8", "Salida estructurada (JSON schema)", Example08_StructuredOutput.RunAsync),
};

// Ejecución directa opcional:  dotnet run -- 3
string? selection = args.Length > 0 ? args[0].Trim() : null;
bool runOnce = selection is not null;

while (true)
{
    if (selection is null)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("  Microsoft Agent Framework — Ejemplos en C# (.NET 10)");
        Console.WriteLine("  Autor: Fernando Valdés H.");
        Console.WriteLine(new string('=', 70));
        foreach (var e in examples) Console.WriteLine($"  {e.Key}. {e.Title}");
        Console.WriteLine("  q. Salir");
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
