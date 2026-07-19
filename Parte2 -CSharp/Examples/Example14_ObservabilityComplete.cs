using System.ComponentModel;
using System.Data;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenTelemetry;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using MFA.CSharp.Part2.Infrastructure;

namespace MFA.CSharp.Part2.Examples;

/// <summary>
/// 14 · Observabilidad completa con OpenTelemetry.
/// Equivalente C# de new_14_observability_COMPLETE.py.
///
/// Objetivo pedagógico: mostrar TODO lo que el Agent Framework emite como
/// telemetría — conversación completa, respuestas del modelo, argumentos y
/// resultados de cada tool, tokens, modelo usado, IDs de traza y tiempos. Se
/// captura con un exportador propio y al salir se genera un reporte HTML.
///
/// Los atributos siguen las convenciones semánticas GenAI de OpenTelemetry
/// (gen_ai.*), así que el reporte sirve para cualquier proveedor.
///
/// ⚠️ EnableSensitiveData = true hace que los spans incluyan el CONTENIDO de los
/// mensajes. Es lo que da valor a esta demo, pero en producción hay que pensarlo
/// dos veces: esos textos terminan en tu backend de observabilidad.
/// </summary>
internal static class Example14_ObservabilityComplete
{
    private const string SourceName = "MFA.CSharp.Part2.Observability";
    private const string ReporteHtml = "complete_telemetry_report.html";

    public static async Task RunAsync()
    {
        Console.WriteLine("\n" + new string('=', 75));
        Console.WriteLine("🔭 DEMO 14: OBSERVABILIDAD COMPLETA - TODO QUEDA CAPTURADO");
        Console.WriteLine(new string('=', 75));
        Console.WriteLine("""

            Esta demo muestra CADA dato que OpenTelemetry captura del agente:
            ✅ Historial completo de la conversación
            ✅ Todas las respuestas del modelo
            ✅ Argumentos y resultados de cada tool
            ✅ Consumo de tokens
            ✅ Información del modelo usado
            ✅ IDs de traza y de span
            ✅ Marcas de tiempo y duraciones
            """);

        Console.WriteLine("Configurando el colector de telemetría...");

        var collector = new CompleteTelemetryCollector();

        // Montaje de OpenTelemetry: se registra el ActivitySource del agente y se
        // engancha nuestro exportador propio mediante un procesador simple.
        using TracerProvider tracerProvider = Sdk.CreateTracerProviderBuilder()
            .SetResourceBuilder(ResourceBuilder.CreateDefault().AddService("agent-demo", serviceVersion: "1.0.0"))
            .AddSource(SourceName)
            .AddProcessor(new SimpleActivityExportProcessor(collector))
            .Build()!;

        Console.WriteLine("✅ Colector de telemetría listo\n");

        Console.WriteLine("Creando el agente...");
        AIAgent agenteBase = AzureAgentFactory.CreateAgent(
            instructions: "Eres un asistente útil. Sé conciso.",
            name: "ObservabilityBot",
            tools:
            [
                AIFunctionFactory.Create(GetWeather),
                AIFunctionFactory.Create(Calculate),
                AIFunctionFactory.Create(Search),
            ]);

        // UseOpenTelemetry envuelve al agente para que emita spans gen_ai.*.
        // Sin esta línea no se captura NADA, aunque el TracerProvider esté montado.
        AIAgent agent = agenteBase
            .AsBuilder()
            .UseOpenTelemetry(SourceName, cfg => cfg.EnableSensitiveData = true)
            .Build();

        Console.WriteLine("✅ ¡Agente listo!\n");

        Console.WriteLine(new string('=', 75));
        Console.WriteLine("MODO INTERACTIVO");
        Console.WriteLine(new string('=', 75));
        Console.WriteLine("Prueba: 'cuéntame un chiste' · '¿qué clima hace en Tokio?' · 'calcula 50*50'");
        Console.WriteLine("Escribe 'quit' para generar el reporte completo\n");

        AgentSession session = await agent.CreateSessionAsync();

        while (true)
        {
            Console.Write("Tú: ");
            string? input = Console.ReadLine()?.Trim();
            if (input is null) break;
            if (input.Length == 0) continue;
            if (input is "quit" or "exit" or "q") break;

            Console.Write("\nAgente: ");
            await foreach (AgentResponseUpdate update in agent.RunStreamingAsync(input, session))
            {
                Console.Write(update.Text);
            }
            Console.WriteLine();

            // Vaciar el buffer para que los spans de este turno lleguen al colector.
            tracerProvider.ForceFlush();
        }

        Console.WriteLine("\n" + new string('=', 75));
        Console.WriteLine("GENERANDO EL REPORTE COMPLETO...");
        Console.WriteLine(new string('=', 75) + "\n");

        tracerProvider.ForceFlush();

        if (collector.AllData.Count == 0)
        {
            Console.WriteLine("⚠️  No se capturó telemetría: ¿conversaste antes de salir?");
            return;
        }

        string archivo = collector.GenerarReporteHtml(ReporteHtml);

        Console.WriteLine($"✅ Reporte generado: {archivo}");
        Console.WriteLine($"📊 Operaciones capturadas: {collector.AllData.Count}");
        Console.WriteLine($"\n🌐 Ábrelo en tu navegador: {Path.GetFullPath(archivo)}");
    }

    // ========================================================================
    // EXPORTADOR PROPIO: se queda con TODO lo que pasa por la telemetría
    // ========================================================================
    // Un BaseExporter<Activity> es la interfaz estándar de OpenTelemetry en .NET
    // (Activity es la implementación de 'Span'). En vez de mandar los datos a un
    // backend, los guardamos en memoria para armar el reporte al final.

    private sealed class CompleteTelemetryCollector : BaseExporter<Activity>
    {
        public List<OperacionCapturada> AllData { get; } = [];

        public override ExportResult Export(in Batch<Activity> batch)
        {
            foreach (Activity activity in batch)
            {
                AllData.Add(Extraer(activity));
            }
            return ExportResult.Success;
        }

        private static OperacionCapturada Extraer(Activity a) => new(
            SpanName: a.DisplayName,
            DurationMs: Math.Round(a.Duration.TotalMilliseconds, 2),
            StartTime: a.StartTimeUtc.ToLocalTime().ToString("o"),
            Status: a.Status.ToString(),
            TraceId: a.TraceId.ToString(),
            SpanId: a.SpanId.ToString(),
            Attributes: a.TagObjects.ToDictionary(t => t.Key, t => t.Value?.ToString() ?? ""));

        public string GenerarReporteHtml(string archivo)
        {
            var html = new StringBuilder();
            html.Append("""
                <!DOCTYPE html>
                <html lang="es">
                <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Reporte de telemetría del agente</title>
                <style>
                  *{margin:0;padding:0;box-sizing:border-box}
                  body{font-family:'Segoe UI',Tahoma,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);padding:20px;color:#333}
                  .container{max-width:1200px;margin:0 auto;background:#fff;border-radius:12px;padding:28px}
                  h1{margin-bottom:6px}
                  .sub{color:#666;margin-bottom:20px}
                  .cards{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:26px}
                  .card{flex:1;min-width:170px;background:#f8f9fa;border-radius:10px;padding:16px;text-align:center}
                  .card .n{font-size:1.9em;font-weight:700;color:#667eea}
                  .card .l{color:#666;font-size:.86em}
                  .op{border:1px solid #e3e3e3;border-radius:10px;margin-bottom:16px;overflow:hidden}
                  .op h2{background:#667eea;color:#fff;font-size:1em;padding:10px 14px}
                  .op .body{padding:14px}
                  table{width:100%;border-collapse:collapse;font-size:.88em}
                  td{padding:6px 8px;border-bottom:1px solid #f0f0f0;vertical-align:top}
                  td.k{font-weight:600;width:34%;color:#555}
                  td.v{font-family:Consolas,monospace;word-break:break-word}
                  .tablewrap{overflow-x:auto}
                  .badge{display:inline-block;background:#4caf50;color:#fff;border-radius:12px;padding:2px 10px;font-size:.8em}
                </style>
                </head>
                <body><div class="container">
                <h1>🔭 Reporte de telemetría del agente</h1>
                <div class="sub">Microsoft Agent Framework · Parte 2 en C# · Autor: Fernando Valdés Herrera</div>
                """);

            long tokensEntrada = SumarTokens("gen_ai.usage.input_tokens");
            long tokensSalida = SumarTokens("gen_ai.usage.output_tokens");

            html.Append($"""
                <div class="cards">
                  <div class="card"><div class="n">{AllData.Count}</div><div class="l">Operaciones</div></div>
                  <div class="card"><div class="n">{tokensEntrada}</div><div class="l">Tokens de entrada</div></div>
                  <div class="card"><div class="n">{tokensSalida}</div><div class="l">Tokens de salida</div></div>
                  <div class="card"><div class="n">{AllData.Sum(d => d.DurationMs):F0} ms</div><div class="l">Duración total</div></div>
                </div>
                """);

            foreach (OperacionCapturada op in AllData)
            {
                html.Append($"""
                    <div class="op">
                      <h2>{Escape(op.SpanName)} <span class="badge">{op.DurationMs} ms</span></h2>
                      <div class="body"><div class="tablewrap"><table>
                        <tr><td class="k">Inicio</td><td class="v">{Escape(op.StartTime)}</td></tr>
                        <tr><td class="k">Estado</td><td class="v">{Escape(op.Status)}</td></tr>
                        <tr><td class="k">Trace ID</td><td class="v">{Escape(op.TraceId)}</td></tr>
                        <tr><td class="k">Span ID</td><td class="v">{Escape(op.SpanId)}</td></tr>
                    """);

                foreach (var (clave, valor) in op.Attributes.OrderBy(a => a.Key))
                {
                    html.Append($"""<tr><td class="k">{Escape(clave)}</td><td class="v">{Escape(valor)}</td></tr>""");
                }

                html.Append("</table></div></div></div>");
            }

            html.Append("</div></body></html>");

            File.WriteAllText(archivo, html.ToString(), Encoding.UTF8);
            return archivo;
        }

        private long SumarTokens(string clave) => AllData
            .Select(d => d.Attributes.TryGetValue(clave, out string? v) && long.TryParse(v, out long n) ? n : 0)
            .Sum();

        private static string Escape(string texto) => texto
            .Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;");
    }

    private sealed record OperacionCapturada(
        string SpanName,
        double DurationMs,
        string StartTime,
        string Status,
        string TraceId,
        string SpanId,
        Dictionary<string, string> Attributes);

    // ========================================================================
    // TOOLS DE LA DEMO
    // ========================================================================
    // Cada llamada genera su propio span 'execute_tool' con argumentos y
    // resultado, que es lo que hace visible el reporte.

    [Description("Consulta el clima de una ciudad.")]
    private static string GetWeather(
        [Description("Nombre de la ciudad, p. ej. 'Tokio'")] string ciudad)
        => $"Clima en {ciudad}: 22°C, soleado";

    [Description("Evalúa una expresión matemática.")]
    private static string Calculate(
        [Description("Expresión matemática, p. ej. '50 * 50'")] string expresion)
    {
        try
        {
            object resultado = new DataTable().Compute(expresion, null);
            return $"= {resultado}";
        }
        catch
        {
            return $"Error: no se pudo calcular '{expresion}'";
        }
    }

    [Description("Busca en una base de datos simulada.")]
    private static string Search(
        [Description("Qué buscar: 'usuarios' o 'productos'")] string consulta)
    {
        var resultados = new Dictionary<string, string[]>
        {
            ["usuarios"] = ["Ana", "Bruno"],
            ["productos"] = ["Laptop", "Teléfono"],
        };

        return resultados.TryGetValue(consulta.ToLowerInvariant(), out string[]? items)
            ? $"Encontrado: {string.Join(", ", items)}"
            : $"Sin resultados para '{consulta}'";
    }
}
