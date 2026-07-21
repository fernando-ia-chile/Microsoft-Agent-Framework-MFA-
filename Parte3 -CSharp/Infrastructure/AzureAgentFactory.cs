using Azure;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace MFA.CSharp.Part3.Infrastructure;

/// <summary>
/// Fábrica de agentes para el ejemplo 21 — el ÚNICO de la Parte 3 que usa un LLM.
///
/// <para>
/// ⚠️ DIFERENCIA DELIBERADA CON PYTHON: la demo 21 de Python usa
/// <c>FoundryChatClient</c> (Azure AI Foundry + <c>az login</c>). Aquí se usa
/// <b>Azure OpenAI directo con API key</b>, igual que en la Parte 2 de C#, porque:
/// </para>
/// <list type="bullet">
///   <item>Mantiene un solo patrón de autenticación en todo el proyecto C#.</item>
///   <item>No obliga a instalar Azure CLI ni a ejecutar <c>az login</c>.</item>
///   <item>Reutiliza el mismo <c>appsettings03.json</c> de la Parte 2.</item>
/// </list>
/// <para>
/// El objetivo pedagógico —"agentes de IA como ejecutores dentro de un workflow"—
/// se conserva intacto: lo único que cambia es de dónde sale el cliente de chat.
/// </para>
/// </summary>
internal static class AzureAgentFactory
{
    /// <summary>
    /// Devuelve el <see cref="IChatClient"/> del deployment configurado.
    /// <para>
    /// OJO: 'Endpoint' debe ser SOLO la base (https://recurso.services.ai.azure.com).
    /// Si incluye /openai/v1/... el SDK agrega su propia ruta encima y obtendrá un 404.
    /// Es el mismo tropiezo documentado en las Partes 1 y 2.
    /// </para>
    /// </summary>
    public static IChatClient CreateChatClient()
    {
        var config = AppConfig.Load();
        string endpoint = config.Require("AzureOpenAI:Endpoint");
        string deployment = config.Require("AzureOpenAI:ChatDeploymentName");
        string apiKey = config.Require("AzureOpenAI:ApiKey");

        return new AzureOpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey))
            .GetChatClient(deployment)
            .AsIChatClient();
    }

    /// <summary>
    /// Crea un agente especializado a partir de un <see cref="IChatClient"/> ya existente.
    /// <para>
    /// Se pasa el cliente por parámetro (en vez de crearlo dentro) para poder
    /// COMPARTIR una sola conexión entre los cuatro agentes del ejemplo 21, tal
    /// como se hace en la versión de Python.
    /// </para>
    /// </summary>
    public static AIAgent CreateAgent(IChatClient chatClient, string name, string instructions)
        => new ChatClientAgent(
            chatClient,
            new ChatClientAgentOptions
            {
                Name = name,
                ChatOptions = new ChatOptions { Instructions = instructions },
            });

    /// <summary>
    /// Indica si hay credenciales de Azure OpenAI utilizables.
    /// Permite que el ejemplo 21 avise con claridad en vez de fallar con una
    /// excepción críptica del SDK.
    /// </summary>
    public static bool IsConfigured()
    {
        try
        {
            var config = AppConfig.Load();
            return config.GetOptional("AzureOpenAI:Endpoint") is not null
                && config.GetOptional("AzureOpenAI:ChatDeploymentName") is not null
                && config.GetOptional("AzureOpenAI:ApiKey") is not null;
        }
        catch (FileNotFoundException)
        {
            return false;
        }
    }
}
