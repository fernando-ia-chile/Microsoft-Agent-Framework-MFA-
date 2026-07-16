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
/// 05 · Function tool: calculadora. Equivalente C# de new_05_function_tool_calculator.py.
/// Las herramientas son métodos normales anotados con [Description], envueltos con
/// AIFunctionFactory.Create y pasados en 'tools'.
/// </summary>
internal static class Example05_FunctionToolCalculator
{
    // Herramienta expuesta al modelo. En .NET no existe eval(); usamos DataTable.Compute
    // para evaluar expresiones aritméticas de forma acotada.
    [Description("Evalúa una expresión matemática y devuelve el resultado.")]
    private static string Calculate(
        [Description("Expresión a evaluar, p. ej. '2 + 2' o '10 * 5'")] string expression)
    {
        try
        {
            object result = new DataTable().Compute(expression, null);
            return $"Resultado: {result}";
        }
        catch
        {
            return $"Error: no se pudo calcular '{expression}'";
        }
    }

    public static async Task RunAsync()
    {
        var config = AppConfig.Load("appsettings03.json");
        string endpoint = config.Require("AzureOpenAI:Endpoint");
        string deployment = config.Require("AzureOpenAI:ChatDeploymentName");
        string apiKey = config.Require("AzureOpenAI:ApiKey");

        Console.WriteLine("\n🧮 DEMO 05: Function Tools - Calculadora\n");

        AIAgent agent = new AzureOpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey))
            .GetChatClient(deployment)
            .AsAIAgent(
                instructions: "Eres un asistente de matemáticas. Usa la herramienta 'Calculate' para los cálculos.",
                name: "CalculatorBot",
                tools: [AIFunctionFactory.Create(Calculate)]);

        await ConsoleChat.StreamLoopAsync(agent);
    }
}
