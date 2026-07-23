using Scenario1.Host.A2A;

namespace Scenario1.Host.Agents;

/// <summary>
/// Agente de Investigación - Agente 1 del Escenario 1.
/// </summary>
/// <remarks>
/// Investiga y recopila información meteorológica usando el servidor MCP de clima.
///
/// Capacidades:
/// <list type="bullet">
///   <item>Se conecta al servidor MCP de clima hablando protocolo MCP de verdad (stdio)</item>
///   <item>Recibe peticiones del Agente Coordinador vía A2A</item>
///   <item>Devuelve los resultados de la investigación vía A2A</item>
/// </list>
///
/// Rol: Recopilador de Información.
///
/// <para>
/// ORDEN DE EJECUCIÓN (los comentarios [n] siguen esta numeración):
/// <code>
///   [1]  Constructor              -> declara qué servidor MCP usará
///   [2]  Instrucciones            -> el system prompt del agente
///   [3]  ManejarMensajeAsync      -> ENTRADA A2A: primera llamada del Coordinador
///   [4]  InvestigarClimaAsync     -> construye la consulta para el modelo
///   [C.*] AgenteConMcp            -> conexión MCP y llamada al modelo (clase base)
/// </code>
/// </para>
///
/// Convención de los comentarios:
/// <code>
///   ⚙️ MFA   = instrucción propia del Microsoft Agent Framework (materia de estudio)
///   🔌 MCP   = relativo al Model Context Protocol
///   📡 A2A   = relativo a la comunicación Agente-a-Agente
///   🔧 Infra = .NET/entorno, no es del framework
/// </code>
/// </remarks>
internal sealed class ResearchAgent : AgenteConMcp
{
    // [1] 🔌 MCP: se declara el proyecto del servidor que este agente lanzará como
    //     subproceso. La clase base se encarga del resto del ciclo de vida.
    public ResearchAgent() : base("Scenario1.WeatherServer", "servidor_clima")
    {
        Console.WriteLine($"✅ {Nombre} inicializado (ID: {AgenteId})");
        Console.WriteLine($"   Rol: {Rol}");
    }

    public override string AgenteId => "research-agent";
    public override string Nombre => "Agente de Investigación";
    public override string Rol => "Recopilador de Información - Investigación Meteorológica";

    // [2] ⚙️ MFA: las instrucciones son el system prompt del agente. Aquí se le
    //     prohíbe inventar datos y se le obliga a usar las herramientas MCP.
    //     ⚠️ Hay que pedir el español EXPLÍCITAMENTE o el modelo responde en inglés.
    protected override string Instrucciones =>
        """
        Eres un Agente de Investigación especializado en información meteorológica.

        Tus responsabilidades:
        1. Investigar el clima cuando el Agente Coordinador te lo solicite.
        2. Usar SIEMPRE las herramientas MCP disponibles para obtener datos reales.
           Nunca inventes temperaturas ni condiciones.
        3. Entregar resúmenes completos pero concisos.
        4. Citar la fuente de los datos (API de Open-Meteo).

        Herramientas MCP disponibles:
        - get_weather(city, country): clima actual de una ciudad.
        - get_forecast(city, country, days): pronóstico detallado.
        - get_alerts(city, country): avisos meteorológicos.

        RESPONDE SIEMPRE EN ESPAÑOL, sin excepción.
        """;

    // =========================================================================
    // [3] ENTRADA A2A — es la PRIMERA llamada que recibe el agente desde fuera
    // =========================================================================
    /// <summary>
    /// Buzón del agente: punto de entrada de todo mensaje A2A entrante.
    /// </summary>
    /// <remarks>
    /// Todo lo que otro agente quiera pedirle a este agente pasa por aquí: clasifica
    /// el mensaje por su campo <c>Tipo</c> y lo deriva al método correspondiente.
    /// El Coordinador nunca llama a los métodos internos.
    /// </remarks>
    public override async Task<RespuestaA2A> ManejarMensajeAsync(
        MensajeA2A mensaje, CancellationToken ct = default)
    {
        // [3.1] Leer la cabecera del mensaje A2A.
        Console.WriteLine();
        Console.WriteLine($"📨 Mensaje recibido de {mensaje.Emisor}");
        Console.WriteLine($"   Tipo: {mensaje.Tipo}");

        // [3.2] CLASIFICACIÓN por tipo de mensaje: es el "enrutador" del protocolo A2A.
        //       Cada rama es una capacidad que este agente publica hacia los demás.
        switch (mensaje.Tipo)
        {
            // [3.3] Rama 1 — petición de investigación: el trabajo real (sigue en [4]).
            case TipoMensaje.PeticionInvestigacion:
                return await ProcesarPeticionInvestigacionAsync(mensaje, ct);

            // [3.4] Rama 2 — ping: comprobación de salud. No gasta tokens ni toca MCP;
            //       sirve para que el orquestador verifique que el agente está vivo.
            case TipoMensaje.Ping:
                Console.WriteLine($"   ✅ {Nombre}: activo");
                return RespuestaA2A.Pong(AgenteId);

            // [3.5] Rama 3 — tipo desconocido: se responde con error en vez de reventar,
            //       para que el emisor pueda manejarlo (buena práctica en A2A).
            default:
                return RespuestaA2A.Fallida(AgenteId, $"Tipo de mensaje desconocido: {mensaje.Tipo}");
        }
    }

    // =========================================================================
    // [4] LÓGICA DE NEGOCIO — validar la petición y construir la respuesta A2A
    // =========================================================================
    private async Task<RespuestaA2A> ProcesarPeticionInvestigacionAsync(
        MensajeA2A mensaje, CancellationToken ct)
    {
        // [4.1] Desempaquetar la carga útil que venía en `Datos`.
        var ciudad = mensaje.Datos.GetValueOrDefault("city")?.ToString() ?? "Santiago";
        var pais = mensaje.Datos.GetValueOrDefault("country")?.ToString() ?? "";
        var tarea = mensaje.Datos.GetValueOrDefault("task")?.ToString() ?? "weather_lookup";

        Console.WriteLine();
        Console.WriteLine($"📊 {Nombre} recibió una petición de investigación:");
        Console.WriteLine($"   Tarea: {tarea}");
        Console.WriteLine($"   Parámetros: ciudad={ciudad}, país={pais}");
        Console.WriteLine($"   🌐 Obteniendo datos EN VIVO para {ciudad}, {pais}...");

        try
        {
            // [4.2] La consulta va en lenguaje natural. Fíjate en que NO se nombra la
            //       herramienta a llamar: es el modelo quien elige entre get_weather,
            //       get_forecast y get_alerts según lo que se le pida.
            var consulta = $"Consulta el clima actual de {ciudad}, {pais} " +
                           "y resume las condiciones para un informe.";

            var informe = await PreguntarAlAgenteAsync(consulta, ct);

            Console.WriteLine($"   ✅ Datos REALES recuperados para {ciudad}, {pais}");

            // [4.3] Envolver el resultado en el sobre de respuesta A2A. Esta forma es
            //       un CONTRATO: el Coordinador lee `Estado` y `Contenido`.
            return RespuestaA2A.Exitosa(AgenteId, informe, tarea, new()
            {
                ["fuente"] = "Servidor MCP de clima (protocolo MCP real)",
                ["confianza"] = "alta",
            });
        }
        catch (Exception ex)
        {
            // [4.4] Un fallo se devuelve como respuesta A2A de error, no como
            //       excepción: el Coordinador debe poder seguir con los demás pasos.
            Console.WriteLine($"❌ Error procesando la petición de investigación: {ex.Message}");
            return RespuestaA2A.Fallida(AgenteId, ex.Message, tarea);
        }
    }
}
