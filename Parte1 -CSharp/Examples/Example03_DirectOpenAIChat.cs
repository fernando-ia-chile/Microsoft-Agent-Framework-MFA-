using Azure;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using OpenAI.Chat;
using MFA.CSharp.Infrastructure;

namespace MFA.CSharp.Examples;

/// <summary>
/// 03 · Chat DIRECTO con Azure OpenAI (agente efímero).
/// Equivalente C# de new_03_direct_openai_chat.py.
/// </summary>
internal static class Example03_DirectOpenAIChat
{
    public static async Task RunAsync()
    {
        var config = AppConfig.Load("appsettings03.json");
        string endpoint = config.Require("AzureOpenAI:Endpoint");
        string deployment = config.Require("AzureOpenAI:ChatDeploymentName");
        string apiKey = config.Require("AzureOpenAI:ApiKey");

        Console.WriteLine("\n🤖 DEMO 03: Chat Directo con Azure OpenAI\n");

        // Cliente Azure OpenAI (auth por API key) -> ChatClient del deployment -> AIAgent.
        AIAgent agent = new AzureOpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey))
            .GetChatClient(deployment)
            .AsAIAgent(
                instructions: "Eres un asistente útil. Sé conciso y claro.",
                name: "DirectChatBot");

        await ConsoleChat.StreamLoopAsync(agent);
    }
}
