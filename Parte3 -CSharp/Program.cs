using System.Text;
using MFA.CSharp.Part3.Examples;

// Sin esto los emojis y las tildes salen como interrogantes en la consola de Windows.
Console.OutputEncoding = Encoding.UTF8;

// Catálogo de ejemplos: clave, título y método a ejecutar.
// La numeración (16-21) se conserva de la versión de Python para que la
// correspondencia entre ambos proyectos sea inmediata.
var examples = new (string Key, string Title, Func<Task> Run)[]
{
    ("16", "Workflow secuencial (cadena lineal)",        Example16_SequentialWorkflow.RunAsync),
    ("17", "Workflow concurrente (fan-out / fan-in)",    Example17_ConcurrentWorkflow.RunAsync),
    ("18", "Workflow con ramificación (switch)",         Example18_BranchingWorkflow.RunAsync),
    ("19", "Human-in-the-loop + checkpointing",          Example19_InteractiveCheckpointing.RunAsync),
    ("20", "Visualización de workflows (Mermaid / DOT)", Example20_VisualizationWorkflow.RunAsync),
    ("21", "Agentes de IA en el workflow [requiere Azure OpenAI]", Example21_AgentsInWorkflow.RunAsync),
};

// Ejecución directa opcional:  dotnet run -- 18
string? selection = args.Length > 0 ? args[0].Trim() : null;
bool runOnce = selection is not null;

while (true)
{
    if (selection is null)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 78));
        Console.WriteLine("  Microsoft Agent Framework — Parte 3 en C# (.NET 10)");
        Console.WriteLine("  Workflows: grafos de ejecutores");
        Console.WriteLine("  Autor: Fernando Valdés Herrera");
        Console.WriteLine(new string('=', 78));
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
