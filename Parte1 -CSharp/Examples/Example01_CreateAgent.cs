using Microsoft.Agents.AI;
using MFA.CSharp.Infrastructure;

namespace MFA.CSharp.Examples;

/// <summary>
/// 01 · Agente de Azure AI Foundry. Equivalente C# de new_01_create_agent.py.
///
/// Diferencia con Python: allí el agente se CREA/publica con to_prompt_agent + create_version.
/// En .NET (1.13-preview) la creación/versionado se realiza en el portal de Foundry o con
/// AgentAdministrationClient; este ejemplo se conecta a un agente ya publicado por su nombre.
/// Requiere `az login` y appsettings01.json con AzureAI:ProjectEndpoint.
/// </summary>
internal static class Example01_CreateAgent
{
    private const string AgentName = "DemoAssistant";

    public static async Task RunAsync()
    {
        var config = AppConfig.Load("appsettings01.json");

        Console.WriteLine("\n🤖 DEMO 01: Agente de Azure AI Foundry\n");
        Console.WriteLine("ℹ️  Conectando al agente publicado en Foundry por nombre.");
        Console.WriteLine($"   Agente: {AgentName}\n");

        AIAgent agent = FoundryConnect.Connect(config, AgentName);

        await ConsoleChat.StreamLoopAsync(agent);
    }
}
