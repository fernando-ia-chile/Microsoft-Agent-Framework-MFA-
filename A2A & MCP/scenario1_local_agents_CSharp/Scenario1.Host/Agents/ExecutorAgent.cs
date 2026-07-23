using Scenario1.Host.A2A;

namespace Scenario1.Host.Agents;

/// <summary>
/// Agente Ejecutor - Agente 3 del Escenario 1.
/// </summary>
/// <remarks>
/// Ejecuta operaciones de archivo usando el servidor MCP de archivos.
///
/// Capacidades:
/// <list type="bullet">
///   <item>Se conecta al servidor MCP de archivos hablando protocolo MCP de verdad (stdio)</item>
///   <item>Recibe peticiones de ejecución del Agente Coordinador vía A2A</item>
///   <item>Realiza operaciones de archivo (leer, escribir, listar, borrar, informar)</item>
/// </list>
///
/// Rol: Ejecutor de Tareas.
///
/// <para>
/// ORDEN DE EJECUCIÓN (los comentarios [n] siguen esta numeración):
/// <code>
///   [1]  Constructor            -> declara qué servidor MCP usará
///   [2]  Instrucciones          -> el system prompt del agente
///   [3]  ManejarMensajeAsync    -> ENTRADA A2A: llamada del Coordinador
///   [4]  ProcesarPeticion...    -> valida la petición y arma la respuesta A2A
///   [5]  ConstruirInstruccion   -> traduce la operación A2A a lenguaje natural
/// </code>
/// </para>
/// </remarks>
internal sealed class ExecutorAgent : AgenteConMcp
{
    // [1] 🔌 MCP: se declara el proyecto del servidor que este agente lanzará.
    public ExecutorAgent() : base("Scenario1.FileOperationsServer", "servidor_archivos")
    {
        Console.WriteLine($"✅ {Nombre} inicializado (ID: {AgenteId})");
        Console.WriteLine($"   Rol: {Rol}");
    }

    public override string AgenteId => "executor-agent";
    public override string Nombre => "Agente Ejecutor";
    public override string Rol => "Ejecutor de Tareas - Operaciones de Archivo";

    // [2] ⚙️ MFA: el system prompt del agente.
    //     ⚠️ Hay que pedir el español EXPLÍCITAMENTE o el modelo responde en inglés.
    protected override string Instrucciones =>
        """
        Eres un Agente Ejecutor especializado en operaciones de archivo.

        Tus responsabilidades:
        1. Ejecutar las tareas que te delegue el Agente Coordinador.
        2. Usar SIEMPRE las herramientas MCP para tocar archivos.
           Nunca simules ni inventes el resultado de una operación.
        3. Confirmar de forma breve y precisa qué se hizo.
        4. Si una operación falla, decir exactamente por qué.

        Herramientas MCP disponibles:
        - write_file(filename, content, append): escribe contenido en un archivo.
        - read_file(filename): lee el contenido de un archivo.
        - list_files(directory, pattern): lista archivos.
        - delete_file(filename): borra un archivo.
        - file_info(filename): datos de un archivo.

        Todas las rutas son relativas al espacio de trabajo del agente.
        Sé preciso y fiable: verifica que la operación se completó.

        RESPONDE SIEMPRE EN ESPAÑOL, sin excepción.
        """;

    // =========================================================================
    // [3] ENTRADA A2A — es la PRIMERA llamada que recibe el agente desde fuera
    // =========================================================================
    /// <summary>Buzón del agente: punto de entrada de todo mensaje A2A entrante.</summary>
    public override async Task<RespuestaA2A> ManejarMensajeAsync(
        MensajeA2A mensaje, CancellationToken ct = default)
    {
        // [3.1] Leer la cabecera del mensaje A2A.
        Console.WriteLine();
        Console.WriteLine($"📨 Mensaje recibido de {mensaje.Emisor}");
        Console.WriteLine($"   Tipo: {mensaje.Tipo}");

        // [3.2] CLASIFICACIÓN por tipo: es el "enrutador" del protocolo A2A.
        switch (mensaje.Tipo)
        {
            // [3.3] Rama 1 — petición de ejecución: el trabajo real (sigue en [4]).
            case TipoMensaje.PeticionEjecucion:
                return await ProcesarPeticionEjecucionAsync(mensaje, ct);

            // [3.4] Rama 2 — ping: comprobación de salud, no gasta tokens ni toca MCP.
            case TipoMensaje.Ping:
                Console.WriteLine($"   ✅ {Nombre}: activo");
                return RespuestaA2A.Pong(AgenteId);

            // [3.5] Rama 3 — tipo desconocido: error en vez de excepción.
            default:
                return RespuestaA2A.Fallida(AgenteId, $"Tipo de mensaje desconocido: {mensaje.Tipo}");
        }
    }

    // =========================================================================
    // [4] LÓGICA DE NEGOCIO — validar la petición y construir la respuesta A2A
    // =========================================================================
    private async Task<RespuestaA2A> ProcesarPeticionEjecucionAsync(
        MensajeA2A mensaje, CancellationToken ct)
    {
        // [4.1] Desempaquetar la carga útil que venía en `Datos`.
        var operacion = mensaje.Datos.GetValueOrDefault("operation")?.ToString() ?? "write_file";
        var archivo = mensaje.Datos.GetValueOrDefault("filename")?.ToString() ?? "informe.txt";
        var contenido = mensaje.Datos.GetValueOrDefault("content")?.ToString() ?? "";
        var directorio = mensaje.Datos.GetValueOrDefault("directory")?.ToString() ?? ".";
        var patron = mensaje.Datos.GetValueOrDefault("pattern")?.ToString() ?? "*";

        Console.WriteLine();
        Console.WriteLine($"⚙️  {Nombre} recibió una petición de ejecución:");
        Console.WriteLine($"   Operación: {operacion}");
        Console.WriteLine($"   Parámetros: archivo={archivo}");

        try
        {
            // [4.2] Traducir la operación a una instrucción y delegar en el modelo.
            var instruccion = ConstruirInstruccion(operacion, archivo, contenido, directorio, patron);

            Console.WriteLine("   🔧 Delegando la operación en el servidor MCP de archivos...");
            var resultado = await PreguntarAlAgenteAsync(instruccion, ct);

            // [4.3] Envolver el resultado en el sobre de respuesta A2A.
            return RespuestaA2A.Exitosa(AgenteId, resultado, operacion, new()
            {
                ["herramienta"] = "Servidor MCP de archivos (protocolo MCP real)",
            });
        }
        catch (Exception ex)
        {
            // [4.4] Un fallo se devuelve como respuesta A2A de error, no como excepción.
            Console.WriteLine($"❌ Error ejecutando la operación: {ex.Message}");
            return RespuestaA2A.Fallida(AgenteId, ex.Message, operacion);
        }
    }

    // =========================================================================
    // [5] TRADUCCIÓN — de operación A2A a instrucción en lenguaje natural
    // =========================================================================
    /// <remarks>
    /// Fíjate en que NO se nombra la herramienta MCP a llamar: es el modelo quien
    /// elige entre las cinco. Antes de usar MFA, esto habría sido un switch que
    /// invocaba la función correspondiente directamente.
    /// </remarks>
    private static string ConstruirInstruccion(
        string operacion, string archivo, string contenido, string directorio, string patron) =>
        operacion switch
        {
            "write_file" =>
                $"Escribe el siguiente contenido en el archivo '{archivo}'. " +
                $"Confirma el resultado.\n\nContenido:\n{contenido}",

            "read_file" =>
                $"Lee el archivo '{archivo}' y muéstrame su contenido.",

            "list_files" =>
                $"Lista los archivos del directorio '{directorio}' " +
                $"que coincidan con el patrón '{patron}'.",

            "delete_file" =>
                $"Borra el archivo '{archivo}' y confirma el resultado.",

            "file_info" =>
                $"Dame la información del archivo '{archivo}'.",

            // [5.1] Operación no contemplada: se lanza para que [4.4] la convierta
            //       en una respuesta A2A de error.
            _ => throw new ArgumentException($"Operación desconocida: {operacion}"),
        };
}
