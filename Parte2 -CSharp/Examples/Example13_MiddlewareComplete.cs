using System.ComponentModel;
using System.Data;
using System.Globalization;
using System.Text;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using MFA.CSharp.Part2.Infrastructure;

namespace MFA.CSharp.Part2.Examples;

/// <summary>
/// 13 · Middleware completo: los 3 tipos trabajando juntos.
/// Equivalente C# de new_13_middleware_complete.py.
///
/// Objetivo pedagógico: mostrar dónde se engancha cada tipo de middleware en el
/// ciclo de vida de una petición. Cuatro piezas, tres tipos:
///   1. TIMING     (agent run)   → mide cuánto tarda el run completo
///   2. SEGURIDAD  (agent run)   → bloquea peticiones con contenido sensible
///   3. LOGGER     (function)    → registra cada llamada a una herramienta
///   4. TOKENS     (chat client) → informa el consumo real de tokens
///
/// En .NET los middleware se registran con el patrón builder:
///   agent.AsBuilder().Use(runFunc:, runStreamingFunc:).Use(funcMiddleware).Build()
/// El middleware de chat client se inserta antes, sobre el propio IChatClient.
/// </summary>
internal static class Example13_MiddlewareComplete
{
    private static readonly string[] s_palabrasBloqueadas =
        ["password", "contraseña", "secret", "hack", "exploit", "bypass"];

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 75));
        Console.WriteLine("🎯 DEMO 13: MIDDLEWARE COMPLETO - Los 3 tipos trabajando juntos");
        Console.WriteLine(new string('=', 75));
        Console.WriteLine("""

            Esta demo ejecuta 4 middleware al mismo tiempo:

            1️⃣  TIMING (agent)       → mide cuánto tarda cada petición
            2️⃣  SEGURIDAD (agent)    → bloquea contenido sensible
            3️⃣  LOGGER (function)    → registra todas las llamadas a tools
            4️⃣  TOKENS (chat)        → informa el consumo real de tokens

            ¡Observa cómo se combinan en una conversación real!
            """);
        Console.WriteLine(new string('=', 75));
        Console.WriteLine("\n🔧 Creando el agente con los 4 middleware...\n");

        // --- MIDDLEWARE 4: TOKENS (chat client) -----------------------------
        // Se inserta sobre el IChatClient, ANTES de construir el agente, usando
        // el builder de Microsoft.Extensions.AI.
        IChatClient chatClient = AzureAgentFactory.CreateChatClient()
            .AsBuilder()
            .Use(TokenCounterMiddleware, TokenCounterStreamingMiddleware)
            .Build();

        AIAgent agenteBase = new ChatClientAgent(
            chatClient,
            new ChatClientAgentOptions
            {
                Name = "MiddlewareBot",
                ChatOptions = new ChatOptions
                {
                    Instructions = "Eres un asistente útil con acceso a varias herramientas. " +
                                   "Sé amable, conciso y directo en tus respuestas.",
                    Tools =
                    [
                        AIFunctionFactory.Create(GetWeather),
                        AIFunctionFactory.Create(Calculate),
                        AIFunctionFactory.Create(GetTime),
                        AIFunctionFactory.Create(SearchDatabase),
                    ],
                },
            });

        // --- MIDDLEWARE 1, 2 y 3 --------------------------------------------
        // El orden importa: el primero en registrarse es el más externo.
        AIAgent agent = agenteBase
            .AsBuilder()
                .Use(runFunc: TimingMiddleware, runStreamingFunc: TimingStreamingMiddleware)
                .Use(runFunc: SecurityMiddleware, runStreamingFunc: SecurityStreamingMiddleware)
                .Use(FunctionLoggerMiddleware)
            .Build();

        Console.WriteLine("✅ ¡Agente creado con 4 capas de middleware!");

        Console.WriteLine("\n" + new string('=', 75));
        Console.WriteLine("📝 PRUEBAS SUGERIDAS:");
        Console.WriteLine(new string('=', 75));
        Console.WriteLine("""

            ✅ PRUEBA 1: "cuéntame un chiste"
               → Dispara: Timing + Tokens

            ✅ PRUEBA 2: "¿qué clima hace en Tokio?"
               → Dispara: Timing + Logger + Tokens

            ✅ PRUEBA 3: "¿qué hora es y cuánto es 15 * 8?"
               → Dispara: Timing + Logger (2 llamadas) + Tokens

            ✅ PRUEBA 4: "¿cuál es mi password?"
               → Dispara: Seguridad (BLOQUEA) + Timing

            ✅ PRUEBA 5: "busca usuarios y dame el clima de París"
               → Dispara: LOS 4 middleware

            Escribe 'quit' para salir
            """);
        Console.WriteLine(new string('=', 75) + "\n");

        AgentSession session = await agent.CreateSessionAsync();

        while (true)
        {
            Console.Write("💬 Tú: ");
            string? input = Console.ReadLine()?.Trim();
            if (input is null) break;
            if (input.Length == 0) continue;

            if (input is "quit" or "exit" or "q" or "bye")
            {
                Console.WriteLine("\n👋 ¡Demo terminada! Gracias por probar los middleware.");
                break;
            }

            Console.WriteLine("\n" + new string('-', 75));
            Console.WriteLine("🔄 PROCESANDO TU PETICIÓN...");
            Console.WriteLine(new string('-', 75));

            try
            {
                Console.Write("\n🤖 Agente: ");
                await foreach (AgentResponseUpdate update in agent.RunStreamingAsync(input, session))
                {
                    Console.Write(update.Text);
                }
                Console.WriteLine("\n");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"\n❌ Error: {ex.Message}\n");
            }

            Console.WriteLine(new string('-', 75));
            Console.WriteLine("✅ ¡Petición completada!\n");
        }
    }

    // ========================================================================
    // MIDDLEWARE 1: TIMING (agent run)
    // ========================================================================
    // En .NET hay que aportar las dos variantes: la de streaming y la normal.
    // Ojo con el streaming: el iterador se consume perezosamente, así que el
    // cronómetro debe detenerse DESPUÉS de recorrer todas las actualizaciones,
    // no al obtener el iterador (ahí el tiempo sería ~0).

    private static async Task<AgentResponse> TimingMiddleware(
        IEnumerable<ChatMessage> messages,
        AgentSession? session,
        AgentRunOptions? options,
        AIAgent innerAgent,
        CancellationToken cancellationToken)
    {
        var inicio = DateTime.Now;
        Console.WriteLine($"\n⏱️  [TIMING] Inicio {inicio:HH:mm:ss}");
        try
        {
            return await innerAgent.RunAsync(messages, session, options, cancellationToken);
        }
        finally
        {
            Console.WriteLine($"⏱️  [TIMING] Completado en {(DateTime.Now - inicio).TotalSeconds:F2} s");
        }
    }

    private static async IAsyncEnumerable<AgentResponseUpdate> TimingStreamingMiddleware(
        IEnumerable<ChatMessage> messages,
        AgentSession? session,
        AgentRunOptions? options,
        AIAgent innerAgent,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken)
    {
        var inicio = DateTime.Now;
        Console.WriteLine($"\n⏱️  [TIMING] Inicio {inicio:HH:mm:ss}");

        try
        {
            await foreach (var update in innerAgent.RunStreamingAsync(messages, session, options, cancellationToken))
            {
                yield return update;
            }
        }
        finally
        {
            // Este 'finally' corre cuando el stream terminó DE VERDAD, porque
            // envuelve al await foreach y no solo a la obtención del iterador.
            Console.WriteLine($"\n⏱️  [TIMING] Completado en {(DateTime.Now - inicio).TotalSeconds:F2} s");
        }
    }

    // ========================================================================
    // MIDDLEWARE 2: SEGURIDAD (agent run)
    // ========================================================================
    // Bloquea la petición si detecta contenido sensible. Al no llamar al
    // innerAgent, la ejecución se corta y se devuelve una respuesta propia.

    private static string? DetectarPalabraBloqueada(IEnumerable<ChatMessage> messages)
    {
        string texto = string.Join(" ", messages.Select(m => m.Text ?? "")).ToLowerInvariant();
        return s_palabrasBloqueadas.FirstOrDefault(p => texto.Contains(p, StringComparison.Ordinal));
    }

    private static void AvisarBloqueo(string palabra)
    {
        Console.WriteLine($"\n🚫 [SEGURIDAD] ¡Petición BLOQUEADA! Detectado: '{palabra}'");
        Console.WriteLine("🚫 [SEGURIDAD] Contiene contenido sensible y no se procesará.");
    }

    private static async Task<AgentResponse> SecurityMiddleware(
        IEnumerable<ChatMessage> messages,
        AgentSession? session,
        AgentRunOptions? options,
        AIAgent innerAgent,
        CancellationToken cancellationToken)
    {
        string? palabra = DetectarPalabraBloqueada(messages);
        if (palabra is not null)
        {
            AvisarBloqueo(palabra);
            // Devolvemos una respuesta propia SIN llamar al modelo.
            return new AgentResponse(
                new ChatMessage(ChatRole.Assistant, "Petición bloqueada por política de seguridad."));
        }

        return await innerAgent.RunAsync(messages, session, options, cancellationToken);
    }

    private static async IAsyncEnumerable<AgentResponseUpdate> SecurityStreamingMiddleware(
        IEnumerable<ChatMessage> messages,
        AgentSession? session,
        AgentRunOptions? options,
        AIAgent innerAgent,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken)
    {
        string? palabra = DetectarPalabraBloqueada(messages);
        if (palabra is not null)
        {
            AvisarBloqueo(palabra);
            yield return new AgentResponseUpdate(ChatRole.Assistant, "Petición bloqueada por política de seguridad.");
            yield break;   // corta el pipeline: el modelo nunca se llama
        }

        await foreach (var update in innerAgent.RunStreamingAsync(messages, session, options, cancellationToken))
        {
            yield return update;
        }
    }

    // ========================================================================
    // MIDDLEWARE 3: LOGGER DE FUNCIONES (function calling)
    // ========================================================================

    private static async ValueTask<object?> FunctionLoggerMiddleware(
        AIAgent agent,
        FunctionInvocationContext context,
        Func<FunctionInvocationContext, CancellationToken, ValueTask<object?>> next,
        CancellationToken cancellationToken)
    {
        Console.WriteLine($"\n🔧 [FUNCIÓN] Llamando a la tool: {context.Function.Name}");
        Console.WriteLine($"🔧 [FUNCIÓN] Argumentos: {FormatearArgumentos(context.Arguments)}");

        object? resultado = await next(context, cancellationToken);

        Console.WriteLine($"🔧 [FUNCIÓN] Resultado: {resultado}");
        return resultado;
    }

    private static string FormatearArgumentos(AIFunctionArguments argumentos)
        => argumentos.Count == 0
            ? "(sin argumentos)"
            : string.Join(", ", argumentos.Select(a => $"{a.Key}={a.Value}"));

    // ========================================================================
    // MIDDLEWARE 4: CONTADOR DE TOKENS (chat client)
    // ========================================================================
    // 'Usage' viene del propio proveedor: son tokens REALES, no una estimación.

    private static async Task<ChatResponse> TokenCounterMiddleware(
        IEnumerable<ChatMessage> messages,
        ChatOptions? options,
        IChatClient innerChatClient,
        CancellationToken cancellationToken)
    {
        Console.WriteLine($"\n🤖 [LLAMADA IA] Enviando {messages.Count()} mensaje(s) al modelo");

        ChatResponse response = await innerChatClient.GetResponseAsync(messages, options, cancellationToken);

        InformarUso(response.Usage);
        return response;
    }

    /// <summary>
    /// Variante de streaming. La sobrecarga Use(...) del chat client exige AMBOS
    /// delegados. Aquí el consumo no llega en la respuesta final sino dentro de las
    /// actualizaciones, como contenido de tipo UsageContent, así que hay que
    /// buscarlo mientras se recorre el stream.
    /// </summary>
    private static async IAsyncEnumerable<ChatResponseUpdate> TokenCounterStreamingMiddleware(
        IEnumerable<ChatMessage> messages,
        ChatOptions? options,
        IChatClient innerChatClient,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken)
    {
        Console.WriteLine($"\n🤖 [LLAMADA IA] Enviando {messages.Count()} mensaje(s) al modelo");

        UsageDetails? uso = null;

        await foreach (var update in innerChatClient.GetStreamingResponseAsync(messages, options, cancellationToken))
        {
            foreach (var contenido in update.Contents)
            {
                if (contenido is UsageContent usageContent) uso = usageContent.Details;
            }

            yield return update;
        }

        InformarUso(uso);
    }

    private static void InformarUso(UsageDetails? uso)
    {
        if (uso is null) return;
        Console.WriteLine($"\n🤖 [LLAMADA IA] Tokens de entrada : {uso.InputTokenCount}");
        Console.WriteLine($"🤖 [LLAMADA IA] Tokens de salida  : {uso.OutputTokenCount}");
        Console.WriteLine($"🤖 [LLAMADA IA] Tokens totales    : {uso.TotalTokenCount}");
    }

    // ========================================================================
    // TOOLS DE LA DEMO
    // ========================================================================

    [Description("Consulta el clima actual de una ciudad.")]
    private static string GetWeather(
        [Description("Nombre de la ciudad, p. ej. 'Tokio' o 'París'")] string ciudad)
    {
        var datos = new Dictionary<string, string>
        {
            ["seattle"] = "☁️ Nublado, 15°C, llovizna ligera",
            ["londres"] = "🌧️ Lluvioso, 12°C, lluvia fuerte",
            ["tokio"] = "☀️ Soleado, 22°C, cielo despejado",
            ["mumbai"] = "🌤️ Parcialmente nublado, 28°C, húmedo",
            ["paris"] = "⛅ Parcialmente nublado, 18°C, templado",
            ["santiago"] = "🌤️ Despejado, 24°C, seco",
            ["nueva york"] = "🌨️ Nevando, -2°C, nieve ligera",
        };

        // Normalizamos acentos para que 'París' y 'Paris' encuentren lo mismo.
        string clave = QuitarAcentos(ciudad.ToLowerInvariant());
        return datos.TryGetValue(clave, out string? valor)
            ? valor
            : $"No hay datos de clima para {ciudad}";
    }

    private static string QuitarAcentos(string texto)
    {
        string normalizado = texto.Normalize(NormalizationForm.FormD);
        var sb = new StringBuilder();
        foreach (char c in normalizado)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(c) != UnicodeCategory.NonSpacingMark) sb.Append(c);
        }
        return sb.ToString().Normalize(NormalizationForm.FormC);
    }

    [Description("Evalúa una expresión matemática.")]
    private static string Calculate(
        [Description("Expresión matemática, p. ej. '2 + 2' o '10 * 5'")] string expresion)
    {
        try
        {
            // En .NET no existe eval(); DataTable.Compute evalúa aritmética acotada.
            object resultado = new DataTable().Compute(expresion, null);
            return $"Resultado: {resultado}";
        }
        catch
        {
            return $"Error: no se pudo calcular '{expresion}'";
        }
    }

    [Description("Devuelve la hora actual.")]
    private static string GetTime() => $"Hora actual: {DateTime.Now:HH:mm:ss}";

    [Description("Simula una búsqueda en una base de datos.")]
    private static string SearchDatabase(
        [Description("Qué buscar: 'usuarios', 'productos' u 'ordenes'")] string consulta)
    {
        var resultados = new Dictionary<string, string>
        {
            ["usuarios"] = "Se encontraron 150 usuarios que cumplen el criterio",
            ["productos"] = "Se encontraron 45 productos en inventario",
            ["ordenes"] = "Se encontraron 230 órdenes en los últimos 30 días",
        };

        return resultados.TryGetValue(consulta.ToLowerInvariant(), out string? valor)
            ? valor
            : $"Sin resultados para: {consulta}";
    }
}
