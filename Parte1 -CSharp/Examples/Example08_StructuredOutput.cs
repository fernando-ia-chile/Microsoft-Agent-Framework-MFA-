using System.Text.Json;
using System.Text.Json.Serialization;
using Azure;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using MFA.CSharp.Infrastructure;
// Resolver ambigüedad: usar el ChatResponseFormat de Microsoft.Extensions.AI (no el de OpenAI.Chat).
using ChatResponseFormat = Microsoft.Extensions.AI.ChatResponseFormat;

namespace MFA.CSharp.Examples;

/// <summary>
/// 08 · Salida estructurada con un modelo tipado. Equivalente C# de new_08_structured_output.py.
/// Se define ResponseFormat = ChatResponseFormat.ForJsonSchema&lt;PersonInfo&gt;() y se deserializa
/// el texto de respuesta al objeto fuertemente tipado.
/// Ejemplo de entrada: "Hola, soy Fernando, tengo 49 años, soy ingeniero y vivo en Santiago de Chile".
/// </summary>
internal static class Example08_StructuredOutput
{
    // Modelo de salida estructurada.
    private sealed class PersonInfo
    {
        [JsonPropertyName("name")] public string? Name { get; set; }
        [JsonPropertyName("age")] public int? Age { get; set; }
        [JsonPropertyName("occupation")] public string? Occupation { get; set; }
        [JsonPropertyName("city")] public string? City { get; set; }
    }

    private static readonly JsonSerializerOptions JsonOpts = new() { PropertyNameCaseInsensitive = true };

    public static async Task RunAsync()
    {
        var config = AppConfig.Load("appsettings03.json");
        string endpoint = config.Require("AzureOpenAI:Endpoint");
        string deployment = config.Require("AzureOpenAI:ChatDeploymentName");
        string apiKey = config.Require("AzureOpenAI:ApiKey");

        Console.WriteLine("\n📊 DEMO 08: Salida Estructurada (JSON Schema)\n");

        // El esquema del modelo tipado se pasa como ResponseFormat en las ChatOptions del agente.
        AIAgent agent = new AzureOpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey))
            .GetChatClient(deployment)
            .AsAIAgent(new ChatClientAgentOptions
            {
                Name = "ExtractorBot",
                ChatOptions = new ChatOptions
                {
                    Instructions = "Extrae la información de la persona a partir del texto del usuario.",
                    ResponseFormat = ChatResponseFormat.ForJsonSchema<PersonInfo>(),
                },
            });

        AgentSession session = await agent.CreateSessionAsync();

        Console.WriteLine("📋 Esquema: name, age, occupation, city");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("💬 Describe a una persona (escribe 'quit' para salir)");
        Console.WriteLine(new string('=', 70) + "\n");

        while (true)
        {
            Console.Write("Tú: ");
            string? input = Console.ReadLine()?.Trim();
            if (input is null) break;
            if (input.Length == 0) continue;
            if (input is "quit" or "exit" or "q") { Console.WriteLine("\n👋 ¡Hasta luego!"); break; }

            Console.WriteLine("\n🔄 Extrayendo datos estructurados...");
            AgentResponse response = await agent.RunAsync(input, session);

            try
            {
                PersonInfo? person = JsonSerializer.Deserialize<PersonInfo>(response.Text, JsonOpts);
                if (person is not null)
                {
                    Console.WriteLine("\n📊 Información extraída:");
                    Console.WriteLine($"   Nombre:     {person.Name}");
                    Console.WriteLine($"   Edad:       {person.Age}");
                    Console.WriteLine($"   Ocupación:  {person.Occupation}");
                    Console.WriteLine($"   Ciudad:     {person.City}\n");
                }
                else { Console.WriteLine("❌ No se pudo extraer información\n"); }
            }
            catch (JsonException)
            {
                Console.WriteLine($"❌ Respuesta no-JSON: {response.Text}\n");
            }
        }
    }
}
