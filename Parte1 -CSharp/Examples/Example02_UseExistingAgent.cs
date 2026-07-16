using Microsoft.Agents.AI;
using MFA.CSharp.Infrastructure;

namespace MFA.CSharp.Examples;

/// <summary>
/// 02 · Usar un agente EXISTENTE de Azure AI Foundry. Equivalente C# de new_02_use_existing_agent.py.
/// Se conecta por nombre (y versión opcional) mediante AgentReference.
/// Requiere `az login` y appsettings02.json con AzureAI:ProjectEndpoint y AzureAI:AgentName.
/// </summary>
internal static class Example02_UseExistingAgent
{
    public static async Task RunAsync()
    {
        var config = AppConfig.Load("appsettings02.json");
        string agentName = config.Require("AzureAI:AgentName");
        string? version = config.Optional("AzureAI:AgentVersion"); // null = última publicada

        Console.WriteLine("\n🔗 DEMO 02: Conectar a un Agente EXISTENTE de Foundry\n");
        Console.WriteLine($"   Agente:  {agentName}");
        Console.WriteLine($"   Versión: {version ?? "(última)"}\n");

        AIAgent agent = FoundryConnect.Connect(config, agentName, version);

        await ConsoleChat.StreamLoopAsync(agent);
    }
}
