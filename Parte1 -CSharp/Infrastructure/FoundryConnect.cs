extern alias identity;
using Azure.AI.Extensions.OpenAI;
using Azure.AI.Projects;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Microsoft.Extensions.Configuration;
using AzureCliCredential = identity::Azure.Identity.AzureCliCredential;

namespace MFA.CSharp.Infrastructure;

/// <summary>
/// Conexión a un agente de Azure AI Foundry (autenticación con Azure CLI: requiere `az login`).
///
/// Nota sobre la API .NET (a diferencia de Python): en esta versión (1.13-preview) el
/// Agent Framework se CONECTA a un agente ya publicado en Foundry mediante un
/// <see cref="AgentReference"/> (nombre + versión). La creación/versionado del agente se hace
/// en el portal de Foundry o con AgentAdministrationClient, no con un simple (model, instructions).
/// </summary>
internal static class FoundryConnect
{
    public static AIAgent Connect(
        IConfiguration config,
        string agentName,
        string? version = null,
        IList<AITool>? tools = null)
    {
        string endpoint = config.Require("AzureAI:ProjectEndpoint");

        var projectClient = new AIProjectClient(new Uri(endpoint), new AzureCliCredential());

        // Referencia al agente publicado en Foundry: (nombre, versión). Versión vacía = la que
        // resuelva el servicio. La creación/versionado se hace en el portal o con AgentAdministrationClient.
        var reference = new AgentReference(agentName, version ?? string.Empty);

        return projectClient.AsAIAgent(reference, tools ?? []);
    }
}
