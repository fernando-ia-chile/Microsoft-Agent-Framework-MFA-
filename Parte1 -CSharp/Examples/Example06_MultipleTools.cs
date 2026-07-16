using System.ComponentModel;
using System.Data;
using Azure;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using MFA.CSharp.Infrastructure;

namespace MFA.CSharp.Examples;

/// <summary>
/// 06 · Múltiples function tools. Equivalente C# de new_06_multiple_tools.py.
/// El modelo elige automáticamente la herramienta adecuada según la pregunta.
/// (La herramienta de hora usa TimeZoneInfo local, sin depender de una API externa.)
/// </summary>
internal static class Example06_MultipleTools
{
    [Description("Obtiene el clima actual de una ciudad.")]
    private static string GetWeather([Description("Nombre de la ciudad")] string location) =>
        location.Trim().ToLowerInvariant() switch
        {
            "london" or "londres" => "🌧️ 15°C, Lluvioso",
            "paris" or "parís" => "☀️ 22°C, Soleado",
            "tokyo" or "tokio" => "⛅ 18°C, Parcialmente nublado",
            "new york" or "nueva york" => "🌤️ 20°C, Despejado",
            _ => $"No hay datos de clima para {location}",
        };

    [Description("Calcula una expresión matemática.")]
    private static string Calculate([Description("Expresión matemática")] string expression)
    {
        try { return $"Resultado: {new DataTable().Compute(expression, null)}"; }
        catch { return $"No se pudo calcular '{expression}'"; }
    }

    [Description("Obtiene la hora actual en una zona horaria (IANA o Windows), p. ej. 'America/Santiago'.")]
    private static string GetTime([Description("Zona horaria, p. ej. 'Europe/London'")] string timezone)
    {
        try
        {
            TimeZoneInfo tz = TimeZoneInfo.FindSystemTimeZoneById(timezone);
            DateTimeOffset now = TimeZoneInfo.ConvertTime(DateTimeOffset.UtcNow, tz);
            return $"⏰ Hora actual en {timezone}: {now:HH:mm:ss}";
        }
        catch
        {
            return $"No se pudo obtener la hora para '{timezone}'";
        }
    }

    public static async Task RunAsync()
    {
        var config = AppConfig.Load("appsettings03.json");
        string endpoint = config.Require("AzureOpenAI:Endpoint");
        string deployment = config.Require("AzureOpenAI:ChatDeploymentName");
        string apiKey = config.Require("AzureOpenAI:ApiKey");

        Console.WriteLine("\n🛠️ DEMO 06: Múltiples Function Tools\n");

        AIAgent agent = new AzureOpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey))
            .GetChatClient(deployment)
            .AsAIAgent(
                instructions: "Eres un asistente con herramientas de clima, calculadora y hora. Elige la correcta automáticamente.",
                name: "MultiToolBot",
                tools:
                [
                    AIFunctionFactory.Create(GetWeather),
                    AIFunctionFactory.Create(Calculate),
                    AIFunctionFactory.Create(GetTime),
                ]);

        Console.WriteLine("   🌤️  Clima  ·  🧮 Calculadora  ·  ⏰ Hora");
        await ConsoleChat.StreamLoopAsync(agent);
    }
}
