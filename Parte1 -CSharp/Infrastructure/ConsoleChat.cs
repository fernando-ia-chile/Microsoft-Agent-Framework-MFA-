using Microsoft.Agents.AI;

namespace MFA.CSharp.Infrastructure;

/// <summary>
/// Bucle de chat interactivo reutilizable con salida en streaming.
/// Mantiene el estado de la conversación en un <see cref="AgentSession"/>.
/// </summary>
internal static class ConsoleChat
{
    public static async Task StreamLoopAsync(AIAgent agent)
    {
        AgentSession session = await agent.CreateSessionAsync();

        Console.WriteLine(new string('=', 70));
        Console.WriteLine("💬 Chat interactivo (escribe 'quit' para salir)");
        Console.WriteLine(new string('=', 70) + "\n");

        while (true)
        {
            Console.Write("Tú: ");
            string? input = Console.ReadLine();
            if (input is null) break;

            input = input.Trim();
            if (input.Length == 0) continue;
            if (input is "quit" or "exit" or "q")
            {
                Console.WriteLine("\n👋 ¡Hasta luego!");
                break;
            }

            Console.Write("Agente: ");
            await foreach (AgentResponseUpdate update in agent.RunStreamingAsync(input, session))
            {
                Console.Write(update.Text);
            }
            Console.WriteLine("\n");
        }
    }
}
