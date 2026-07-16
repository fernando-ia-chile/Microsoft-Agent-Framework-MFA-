using Microsoft.Agents.AI;
using MFA.CSharp.Infrastructure;

namespace MFA.CSharp.Examples;

/// <summary>
/// 04 · Búsqueda de archivos (File Search). Equivalente C# de new_04_file_search_tool.py.
///
/// En Foundry la File Search se configura sobre el agente con un VECTOR STORE. En .NET
/// (1.13-preview) el agente con file search + vector store se define en el portal de Foundry;
/// este ejemplo se conecta a ese agente por nombre y chatea (el modelo responde "grounded"
/// en los documentos indexados). Requiere `az login` y appsettings01.json con VectorStoreId.
/// </summary>
internal static class Example04_FileSearchTool
{
    private const string AgentName = "FileSearchBot";

    public static async Task RunAsync()
    {
        var config = AppConfig.Load("appsettings01.json");
        string? vectorStoreId = config.Optional("AzureAI:VectorStoreId");

        Console.WriteLine("\n🔍 DEMO 04: Herramienta de Búsqueda de Archivos (File Search)\n");
        if (vectorStoreId is null)
        {
            Console.WriteLine("⚠️  Configura AzureAI:VectorStoreId en appsettings01.json y crea, en el");
            Console.WriteLine("    portal de Foundry, un agente con File Search apuntando a ese vector store.\n");
        }
        else
        {
            Console.WriteLine($"   Vector Store: {vectorStoreId}");
        }
        Console.WriteLine($"   Agente: {AgentName}\n");

        AIAgent agent = FoundryConnect.Connect(config, AgentName);

        await ConsoleChat.StreamLoopAsync(agent);
    }
}
