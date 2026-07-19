using System.Text.Json;
using Microsoft.Agents.AI;
using MFA.CSharp.Part2.Infrastructure;

namespace MFA.CSharp.Part2.Examples;

/// <summary>
/// 11 · Sesiones con auto-serialización.
/// Equivalente C# de new_11_threading_auto.py.
///
/// Objetivo pedagógico: demostrar que el estado de una conversación se puede
/// GUARDAR en disco y RESTAURAR, y que el agente sigue recordando todo. Tras cada
/// mensaje se hace el ciclo completo: serializar → guardar → leer → deserializar →
/// seguir conversando con la sesión restaurada. Al arrancar reanuda la conversación
/// de la ejecución anterior.
/// </summary>
internal static class Example11_ThreadingAuto
{
    private const string SessionFile = "session_history.json";

    /// <summary>Envoltorio de lo que se guarda en disco (equivale al dict de Python).</summary>
    private sealed record SavedSession(string Timestamp, int MessageNumber, JsonElement SessionData);

    private static readonly JsonSerializerOptions s_json = new() { WriteIndented = true };

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 70));
        Console.WriteLine("🧵 DEMO 11: guardar y restaurar la sesión en cada mensaje");
        Console.WriteLine(new string('=', 70));

        AIAgent agent = AzureAgentFactory.CreateAgent(
            instructions: "Eres un asistente útil. Recuerda todo lo que el usuario te cuente " +
                          "y haz referencia a ello cuando venga al caso.",
            name: "MemoryBot");

        Console.WriteLine("\n✅ Agente creado");

        // --- Reanudar la conversación anterior, si existe ---
        Console.WriteLine("📋 Buscando una sesión previa...");
        (AgentSession? session, int contador) = await CargarSesionAsync(agent);

        if (session is not null)
        {
            Console.WriteLine($"   📂 Encontrado {SessionFile}");
            Console.WriteLine($"   ✅ Sesión restaurada tras {contador} mensajes");
            Console.WriteLine("   💡 Continuamos donde lo dejaste...\n");
        }
        else
        {
            // En C# la creación de la sesión es asíncrona: CreateSessionAsync().
            session = await agent.CreateSessionAsync();
            contador = 0;
            Console.WriteLine("   📋 No había sesión previa: se creó una nueva\n");
        }

        Console.WriteLine(new string('=', 70));
        Console.WriteLine("💬 Chat interactivo con auto-serialización");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("💡 Después de cada mensaje:");
        Console.WriteLine("   1. El agente responde");
        Console.WriteLine("   2. La sesión se serializa y se guarda en JSON");
        Console.WriteLine("   3. La sesión se vuelve a leer y deserializar desde el archivo");
        Console.WriteLine("   4. El siguiente mensaje usa la sesión restaurada");
        Console.WriteLine("\n💡 Escribe 'quit' para salir");
        Console.WriteLine(new string('=', 70) + "\n");

        while (true)
        {
            Console.Write("Tú: ");
            string? input = Console.ReadLine()?.Trim();
            if (input is null) break;
            if (input.Length == 0) continue;

            if (input is "quit" or "exit" or "q")
            {
                Console.WriteLine("\n👋 ¡Demo terminada!");
                Console.WriteLine($"\n📊 Mensajes en esta ejecución: {contador}");
                Console.WriteLine($"📊 Ciclos de serialización: {contador}");
                break;
            }

            contador++;
            Console.WriteLine($"\n[Mensaje #{contador}]");

            // 1) El agente responde en streaming usando la sesión actual.
            Console.Write("Agente: ");
            await foreach (AgentResponseUpdate update in agent.RunStreamingAsync(input, session))
            {
                Console.Write(update.Text);
            }
            Console.WriteLine();

            // 2) Serializar y guardar en disco.
            Console.WriteLine($"\n💾 [Serializando y guardando en {SessionFile}...]");
            int bytes = await GuardarSesionAsync(agent, session, contador);
            Console.WriteLine($"   ✅ Guardado: {bytes} bytes");

            // 3) Volver a leer del disco y deserializar. Reasignamos 'session' con el
            //    objeto restaurado: el siguiente turno usa lo que salió del archivo,
            //    que es justamente lo que la demo quiere probar.
            Console.WriteLine($"📥 [Leyendo y deserializando {SessionFile}...]");
            (AgentSession? restaurada, _) = await CargarSesionAsync(agent);
            if (restaurada is not null)
            {
                session = restaurada;
                Console.WriteLine("   ✅ Sesión restaurada desde el archivo");
                Console.WriteLine("   💡 El próximo mensaje usará esta sesión restaurada\n");
            }
            else
            {
                Console.WriteLine("   ⚠️  No se pudo restaurar; se sigue con la sesión en memoria\n");
            }

            Console.WriteLine(new string('-', 70) + "\n");
        }

        Console.WriteLine("\n" + new string('=', 70));
        Console.WriteLine("✅ DEMO COMPLETA");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("💡 Lo que acabas de ver:");
        Console.WriteLine("   • La sesión se guardó en JSON después de cada mensaje");
        Console.WriteLine("   • La sesión se restauró desde el JSON antes del siguiente turno");
        Console.WriteLine("   • El agente mantuvo todo el historial de la conversación");
        Console.WriteLine("   • Al volver a ejecutar el ejemplo, la conversación continúa");
        Console.WriteLine($"\n📁 Revisa el archivo: {SessionFile}");
        Console.WriteLine(new string('=', 70) + "\n");
    }

    /// <summary>
    /// Serializa la sesión y la escribe en disco. Devuelve el tamaño en bytes.
    /// SerializeSessionAsync entrega un JsonElement, así que se guarda tal cual:
    /// no hay que convertir mensajes a mano.
    /// </summary>
    private static async Task<int> GuardarSesionAsync(AIAgent agent, AgentSession session, int numeroMensaje)
    {
        JsonElement estado = await agent.SerializeSessionAsync(session);

        var datos = new SavedSession(DateTime.Now.ToString("o"), numeroMensaje, estado);
        string contenido = JsonSerializer.Serialize(datos, s_json);
        await File.WriteAllTextAsync(SessionFile, contenido);
        return contenido.Length;
    }

    /// <summary>
    /// Lee el JSON del disco y reconstruye la sesión.
    /// Devuelve (sesión, nº de mensajes) o (null, 0) si no hay archivo o está roto.
    /// </summary>
    private static async Task<(AgentSession? Session, int Count)> CargarSesionAsync(AIAgent agent)
    {
        if (!File.Exists(SessionFile)) return (null, 0);

        try
        {
            string contenido = await File.ReadAllTextAsync(SessionFile);
            SavedSession? datos = JsonSerializer.Deserialize<SavedSession>(contenido);
            if (datos is null) return (null, 0);

            // La sesión SIEMPRE se reconstruye a través del agente, porque es él quien
            // le adjunta los comportamientos (historial, context providers, etc.).
            AgentSession session = await agent.DeserializeSessionAsync(datos.SessionData);
            return (session, datos.MessageNumber);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"   ⚠️  No se pudo cargar la sesión previa: {ex.Message}");
            return (null, 0);
        }
    }
}
