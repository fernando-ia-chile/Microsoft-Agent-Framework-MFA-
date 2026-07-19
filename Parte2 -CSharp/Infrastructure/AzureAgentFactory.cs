using Azure;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;

namespace MFA.CSharp.Part2.Infrastructure;

/// <summary>
/// Fábrica compartida por los cinco ejemplos de la Parte 2. Todos usan el mismo
/// esqueleto: cliente Azure OpenAI directo (API key, agente efímero) sobre el que
/// cada demo monta su capacidad transversal.
/// </summary>
internal static class AzureAgentFactory
{
    /// <summary>
    /// Devuelve el <see cref="IChatClient"/> del deployment configurado.
    /// Se expone por separado porque algunos ejemplos lo necesitan directamente:
    /// el 12 para extraer el perfil y el 13 para insertar middleware de chat.
    /// </summary>
    public static IChatClient CreateChatClient()
    {
        var config = AppConfig.Load();
        string endpoint = config.Require("AzureOpenAI:Endpoint");
        string deployment = config.Require("AzureOpenAI:ChatDeploymentName");
        string apiKey = config.Require("AzureOpenAI:ApiKey");

        // OJO: 'Endpoint' debe ser SOLO la base (https://<recurso>.services.ai.azure.com).
        // Si incluyes /openai/v1/... el SDK agrega su propia ruta encima y obtienes 404.
        return new AzureOpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey))
            .GetChatClient(deployment)
            .AsIChatClient();
    }

    /// <summary>Crea un agente sencillo a partir del chat client configurado.</summary>
    public static AIAgent CreateAgent(string instructions, string name, IList<AITool>? tools = null)
        => new ChatClientAgent(
            CreateChatClient(),
            new ChatClientAgentOptions
            {
                Name = name,
                ChatOptions = new ChatOptions
                {
                    Instructions = instructions,
                    Tools = tools,
                },
            });
}
