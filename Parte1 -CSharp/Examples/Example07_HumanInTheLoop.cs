using System.ComponentModel;
using Azure;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using MFA.CSharp.Infrastructure;
// Resolver ambigüedad ChatMessage/ChatRole (existen en Microsoft.Extensions.AI y en OpenAI.Chat).
using ChatMessage = Microsoft.Extensions.AI.ChatMessage;
using ChatRole = Microsoft.Extensions.AI.ChatRole;

namespace MFA.CSharp.Examples;

/// <summary>
/// 07 · Human-in-the-loop con aprobación NATIVA. Equivalente C# de new_07_human_in_the_loop.py.
/// create_file se ejecuta sola; delete_file se envuelve en ApprovalRequiredAIFunction, por lo
/// que el agente pide aprobación (ToolApprovalRequestContent) antes de ejecutarla.
/// </summary>
internal static class Example07_HumanInTheLoop
{
    private static readonly string DemoDir = Path.Combine(AppContext.BaseDirectory, "demo_files");

    [Description("Crea un archivo con contenido. Operación segura (sin aprobación).")]
    private static string CreateFile(
        [Description("Nombre del archivo")] string filename,
        [Description("Contenido a escribir")] string content)
    {
        try
        {
            File.WriteAllText(Path.Combine(DemoDir, filename), content);
            return $"✅ Archivo '{filename}' creado con {content.Length} caracteres";
        }
        catch (Exception e) { return $"❌ Error creando el archivo: {e.Message}"; }
    }

    [Description("Borra un archivo. Operación peligrosa (requiere aprobación).")]
    private static string DeleteFile([Description("Nombre del archivo a borrar")] string filename)
    {
        try
        {
            string path = Path.Combine(DemoDir, filename);
            if (!File.Exists(path)) return $"⚠️ Archivo '{filename}' no encontrado";
            File.Delete(path);
            return $"🗑️ Archivo '{filename}' borrado correctamente";
        }
        catch (Exception e) { return $"❌ Error borrando el archivo: {e.Message}"; }
    }

    public static async Task RunAsync()
    {
        Directory.CreateDirectory(DemoDir);

        var config = AppConfig.Load("appsettings03.json");
        string endpoint = config.Require("AzureOpenAI:Endpoint");
        string deployment = config.Require("AzureOpenAI:ChatDeploymentName");
        string apiKey = config.Require("AzureOpenAI:ApiKey");

        Console.WriteLine("\n🔒 DEMO 07: Human-in-the-Loop (Crear vs Borrar)\n");
        Console.WriteLine($"📁 Los archivos se crean en: {DemoDir}\n");

        // La operación peligrosa se envuelve para exigir aprobación.
        AITool createTool = AIFunctionFactory.Create(CreateFile);
        AITool deleteTool = new ApprovalRequiredAIFunction(AIFunctionFactory.Create(DeleteFile));

        AIAgent agent = new AzureOpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey))
            .GetChatClient(deployment)
            .AsAIAgent(
                instructions: "Eres un asistente de archivos. Para crear llama a CreateFile; para borrar llama a DeleteFile. " +
                              "No pidas confirmación en el chat: el sistema gestiona las aprobaciones.",
                name: "FileBot",
                tools: [createTool, deleteTool]);

        AgentSession session = await agent.CreateSessionAsync();

        Console.WriteLine(new string('=', 70));
        Console.WriteLine("💬 Chat interactivo (escribe 'quit' para salir)");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("💡 Prueba: 'Crea test.txt con hola' y luego 'Borra test.txt'\n");

        while (true)
        {
            Console.Write("Tú: ");
            string? input = Console.ReadLine()?.Trim();
            if (input is null) break;
            if (input.Length == 0) continue;
            if (input is "quit" or "exit" or "q") { Console.WriteLine("\n👋 ¡Hasta luego!"); break; }

            AgentResponse response = await agent.RunAsync(input, session);

            // Resolver en bucle todas las solicitudes de aprobación pendientes.
            List<ToolApprovalRequestContent> approvals = ExtractApprovals(response);
            while (approvals.Count > 0)
            {
                var userMessages = new List<ChatMessage>();
                foreach (ToolApprovalRequestContent req in approvals)
                {
                    bool approved = AskApproval(req);
                    Console.WriteLine(approved ? "✅ APROBADO" : "❌ RECHAZADO");
                    userMessages.Add(new ChatMessage(ChatRole.User, [req.CreateResponse(approved)]));
                }
                response = await agent.RunAsync(userMessages, session);
                approvals = ExtractApprovals(response);
            }

            Console.WriteLine($"Agente: {response.Text}\n");
        }
    }

    private static List<ToolApprovalRequestContent> ExtractApprovals(AgentResponse response) =>
        response.Messages
            .SelectMany(m => m.Contents)
            .OfType<ToolApprovalRequestContent>()
            .ToList();

    private static bool AskApproval(ToolApprovalRequestContent req)
    {
        var call = req.ToolCall as FunctionCallContent;
        Console.WriteLine("\n" + new string('=', 70));
        Console.WriteLine("🚨 SE REQUIERE APROBACIÓN");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine($"📝 Función: {call?.Name}");
        if (call?.Arguments is { Count: > 0 } args)
        {
            Console.WriteLine("📊 Argumentos:");
            foreach (var kv in args) Console.WriteLine($"   {kv.Key} = {kv.Value}");
        }
        Console.WriteLine(new string('-', 70));
        while (true)
        {
            Console.Write("⚠️ ¿Apruebas esta acción? (sí/no): ");
            string r = (Console.ReadLine() ?? string.Empty).Trim().ToLowerInvariant();
            if (r is "si" or "sí" or "s" or "yes" or "y") return true;
            if (r is "no" or "n") return false;
            Console.WriteLine("   Responde 'sí' o 'no'.");
        }
    }
}
