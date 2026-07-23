using System.ClientModel;
using System.ComponentModel;
using Azure.AI.OpenAI;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using Scenario1.Host.A2A;

namespace Scenario1.Host.Agents;

/// <summary>
/// Agente Coordinador - Agente 2 del Escenario 1.
/// </summary>
/// <remarks>
/// Orquesta el trabajo entre el Agente de Investigación y el Agente Ejecutor.
///
/// Capacidades:
/// <list type="bullet">
///   <item>Recibe peticiones del usuario en lenguaje natural</item>
///   <item>Delega la investigación al Agente de Investigación (vía A2A)</item>
///   <item>Delega las operaciones de archivo al Agente Ejecutor (vía A2A)</item>
///   <item>Agrega los resultados y responde al usuario</item>
/// </list>
///
/// Rol: Orquestador de Flujos de Trabajo.
///
/// <para>
/// <b>Diferencia clave con los otros dos agentes:</b> este NO usa MCP. Sus
/// herramientas no consultan datos: <b>delegan en otros agentes</b>. Ese es el
/// mecanismo A2A de esta demo.
/// </para>
///
/// <para>
/// ORDEN DE EJECUCIÓN (los comentarios [n] siguen esta numeración):
/// <code>
///   [1]  Constructor              -> cliente + herramientas de delegación + agente
///   [2]  Instrucciones            -> el system prompt del agente
///   [3]  ManejarMensajeAsync      -> ENTRADA A2A (desde otros agentes)
///   [4]  ProcesarPeticionUsuario  -> ENTRADA DEL USUARIO (desde el orquestador)
///   [5]  agente.RunStreamingAsync -> el LLM planifica y decide a quién delegar
///   [6]  DelegarPorA2AAsync       -> envía el mensaje A2A y muestra su estructura
///   [7]  Herramienta investigar_clima
///   [8]  Herramienta guardar_en_archivo
///   [9]  AgregarResultados        -> arma la respuesta final para el usuario
/// </code>
/// </para>
/// </remarks>
internal sealed class CoordinatorAgent : IAgenteA2A
{
    private const int AnchoCaja = 60;

    private readonly IAgenteA2A? _agenteInvestigacion;
    private readonly IAgenteA2A? _agenteEjecutor;
    private readonly AIAgent _agente;

    // 🔧 Infra: bitácora de los pasos que el LLM decida ejecutar. Se rellena dentro
    //    de las herramientas y se usa en [9] para el informe final.
    private readonly List<RespuestaA2A> _pasos = [];

    public string AgenteId => "coordinator-agent";
    public string Nombre => "Agente Coordinador";
    public string Rol => "Orquestador de Flujos de Trabajo";

    // =========================================================================
    // [1] CONSTRUCCIÓN — se ejecuta una vez, al crear el agente
    // =========================================================================
    public CoordinatorAgent(IAgenteA2A? agenteInvestigacion = null, IAgenteA2A? agenteEjecutor = null)
    {
        // [1.1] 📡 A2A: referencias a los agentes destino. Son los "contactos" a los
        //       que este agente puede enviar mensajes A2A. Si faltan, las herramientas
        //       responden con error en vez de simular (ver [7] y [8]).
        _agenteInvestigacion = agenteInvestigacion;
        _agenteEjecutor = agenteEjecutor;

        // [1.2] ⚙️ MFA: el ChatClient es el CANAL hacia el modelo; todavía no es agente.
        //       ⚠️ El endpoint debe ser SOLO la base (sin /openai/...).
        ChatClient clienteChat = new AzureOpenAIClient(
                new Uri(Configuracion.Endpoint),
                new ApiKeyCredential(Configuracion.ApiKey))
            .GetChatClient(Configuracion.Deployment);

        // [1.3] ⚙️ MFA: AIFunctionFactory convierte un método normal en una herramienta
        //       que el modelo puede invocar. La descripción y los [Description] de cada
        //       parámetro son lo que el modelo LEE para decidir cuándo llamarla y con
        //       qué argumentos: por eso son tan explícitos.
        AITool herramientaInvestigar = AIFunctionFactory.Create(
            InvestigarClimaAsync,
            name: "investigar_clima",
            description: "Delega en el Agente de Investigación la consulta del clima de " +
                         "cualquier ciudad del mundo. Devuelve el informe meteorológico.");

        AITool herramientaGuardar = AIFunctionFactory.Create(
            GuardarEnArchivoAsync,
            name: "guardar_en_archivo",
            description: "Delega en el Agente Ejecutor el guardado de un texto en un archivo " +
                         "del espacio de trabajo. Úsala cuando el usuario pida guardar o " +
                         "generar un informe.");

        // [1.4] ⚙️ MFA: el agente une cliente + instrucciones + herramientas.
        //       Es el framework quien enseña su esquema al modelo y ejecuta la que el
        //       modelo decida invocar, con los argumentos que el modelo extraiga.
        _agente = clienteChat.AsAIAgent(
            instructions: Instrucciones,
            name: AgenteId,
            tools: [herramientaInvestigar, herramientaGuardar]);

        Console.WriteLine($"✅ {Nombre} inicializado (ID: {AgenteId})");
        Console.WriteLine($"   Rol: {Rol}");
    }

    // [2] ⚙️ MFA: las instrucciones explican QUÉ agentes tiene disponibles y CÓMO
    //     encadenarlos. Sin MFA, esta lógica sería un árbol de `if` con palabras clave.
    private static string Instrucciones =>
        """
        Eres un Agente Coordinador que orquesta flujos de trabajo entre otros agentes.

        Tus responsabilidades:
        1. Analizar la petición del usuario y decidir qué agentes intervienen.
        2. Delegar cada subtarea al agente adecuado usando tus herramientas.
        3. Encadenar los resultados: lo que devuelve un agente puede ser la entrada
           del siguiente.
        4. Resumir al usuario lo que se hizo.

        Agentes disponibles (a través de tus herramientas):
        - Agente de Investigación -> herramienta `investigar_clima`.
          Úsala SIEMPRE que pidan clima, temperatura, pronóstico o alertas.
          Extrae tú la ciudad y el país de la petición del usuario, sea cual sea:
          funciona con CUALQUIER ciudad del mundo.
        - Agente Ejecutor -> herramienta `guardar_en_archivo`.
          Úsala solo si el usuario pide guardar, escribir, archivar o generar
          un informe o documento. Pásale el texto ya obtenido de la investigación.

        Reglas:
        - No inventes datos meteorológicos: siempre pásalos por `investigar_clima`.
        - Si el usuario pide clima Y guardar, llama primero a `investigar_clima`
          y después a `guardar_en_archivo` con el resultado.
        - Si la petición no requiere ningún agente, respóndela directamente.

        RESPONDE SIEMPRE EN ESPAÑOL, sin excepción.
        """;

    // =========================================================================
    // [3] ENTRADA A2A — mensajes que llegan DESDE otros agentes
    // =========================================================================
    /// <summary>
    /// Buzón del agente para OTROS AGENTES. Las peticiones del usuario final entran
    /// por <see cref="ProcesarPeticionUsuarioAsync"/> ([4]).
    /// </summary>
    public async Task<RespuestaA2A> ManejarMensajeAsync(MensajeA2A mensaje, CancellationToken ct = default)
    {
        // [3.1] Leer la cabecera del mensaje A2A.
        Console.WriteLine();
        Console.WriteLine($"📨 Mensaje recibido de {mensaje.Emisor}");
        Console.WriteLine($"   Tipo: {mensaje.Tipo}");

        // [3.2] CLASIFICACIÓN por tipo: es el enrutador del protocolo A2A.
        switch (mensaje.Tipo)
        {
            // [3.3] Rama 1 — ping: comprobación de salud, no gasta tokens.
            case TipoMensaje.Ping:
                Console.WriteLine($"   ✅ {Nombre}: activo");
                return RespuestaA2A.Pong(AgenteId);

            // [3.4] Rama 2 — otro agente le delega un flujo completo: se trata igual
            //       que una petición de usuario y se resuelve con el LLM ([4]).
            case TipoMensaje.PeticionFlujo:
                var peticion = mensaje.Datos.GetValueOrDefault("request")?.ToString() ?? "";
                Console.WriteLine($"   📋 Flujo de trabajo delegado por {mensaje.Emisor}");
                var informe = await ProcesarPeticionUsuarioAsync(peticion, ct);
                return RespuestaA2A.Exitosa(AgenteId, informe.Resumen, TipoMensaje.PeticionFlujo);

            // [3.5] Rama 3 — tipo desconocido: error en vez de excepción.
            default:
                return RespuestaA2A.Fallida(AgenteId, $"Tipo de mensaje desconocido: {mensaje.Tipo}");
        }
    }

    // =========================================================================
    // [4] ENTRADA DEL USUARIO — la llama el orquestador
    // =========================================================================
    /// <summary>Procesa una petición del usuario y orquesta el flujo entre agentes.</summary>
    public async Task<InformeFlujo> ProcesarPeticionUsuarioAsync(
        string peticionUsuario, CancellationToken ct = default)
    {
        Console.WriteLine();
        Console.WriteLine($"👤 Petición del usuario: {peticionUsuario}");
        Console.WriteLine("🤔 Analizando la petición y planificando el flujo de trabajo...");

        // [4.1] Vaciar la bitácora: cada petición es un flujo independiente.
        _pasos.Clear();

        var resumen = new System.Text.StringBuilder();

        try
        {
            Console.WriteLine();
            Console.WriteLine("   🤖 Respuesta del Coordinador:");
            Console.Write("   ");

            // [5] ⚙️ MFA: aquí ocurre TODA la orquestación en un único bucle.
            //     El modelo lee la petición, decide qué herramientas llamar y en qué
            //     orden, extrae los argumentos (ciudad, país, nombre de archivo) y
            //     encadena los resultados. El framework ejecuta cada herramienta y le
            //     devuelve la salida al modelo hasta que este redacta el cierre.
            //     ➜ Esto sustituye por completo a un planificador escrito a mano.
            await foreach (var fragmento in _agente.RunStreamingAsync(peticionUsuario, cancellationToken: ct))
            {
                if (string.IsNullOrEmpty(fragmento.Text)) continue;
                resumen.Append(fragmento.Text);
                Console.Write(fragmento.Text);
            }
            Console.WriteLine();
        }
        catch (Exception ex)
        {
            Console.WriteLine();
            Console.WriteLine($"❌ Error orquestando el flujo: {ex.Message}");
            resumen.Append($"El flujo falló: {ex.Message}");
        }

        // [9] Agregar lo ocurrido en un informe para el usuario.
        return AgregarResultados(resumen.ToString());
    }

    // =========================================================================
    // [6] CANAL A2A — envío del mensaje y visualización de su estructura
    // =========================================================================
    /// <summary>Envía un mensaje A2A a otro agente y devuelve su respuesta.</summary>
    /// <remarks>
    /// Concentra el "protocolo": construir el sobre, mostrarlo y entregarlo al buzón
    /// (<c>ManejarMensajeAsync</c>) del agente destino.
    /// </remarks>
    private async Task<RespuestaA2A> DelegarPorA2AAsync(
        IAgenteA2A destino, string tipo, Dictionary<string, object?> datos, CancellationToken ct)
    {
        // [6.1] 📡 A2A: construir el SOBRE del mensaje. Estos campos son el contrato
        //       que comparten los tres agentes del escenario.
        var mensaje = new MensajeA2A
        {
            Emisor = AgenteId,
            Destinatario = destino.AgenteId,
            Tipo = tipo,
            Datos = datos,
        };

        // [6.2] Mostrar la estructura del mensaje: es el objetivo didáctico del bloque.
        var resumenDatos = string.Join(", ", datos.Take(2).Select(d => $"{d.Key}={Recortar(d.Value?.ToString(), 18)}"));

        Console.WriteLine();
        Console.WriteLine($"   📤 Enviando mensaje A2A a {mensaje.Destinatario}...");
        Console.WriteLine();
        Console.WriteLine("   📨 ESTRUCTURA DEL MENSAJE A2A:");
        Console.WriteLine($"   ┌{new string('─', AnchoCaja)}┐");
        Console.WriteLine($"   │ Emisor:     {Ajustar(mensaje.Emisor)}│");
        Console.WriteLine($"   │ Destino:    {Ajustar(mensaje.Destinatario)}│");
        Console.WriteLine($"   │ Tipo:       {Ajustar(mensaje.Tipo)}│");
        Console.WriteLine($"   │ Datos:      {Ajustar(resumenDatos)}│");
        Console.WriteLine($"   └{new string('─', AnchoCaja)}┘");

        // [6.3] 📡 A2A: entregar el mensaje en el buzón del agente destino.
        //       Los tres agentes implementan IAgenteA2A, así que este método no
        //       necesita saber nada de quién recibe: ese contrato común es lo que
        //       los hace intercambiables como destinos.
        var respuesta = await destino.ManejarMensajeAsync(mensaje, ct);

        // [6.4] Mostrar el acuse de recibo.
        Console.WriteLine();
        Console.WriteLine("   📨 RESPUESTA A2A RECIBIDA:");
        Console.WriteLine($"   ┌{new string('─', AnchoCaja)}┐");
        Console.WriteLine($"   │ De:         {Ajustar(respuesta.AgenteId)}│");
        Console.WriteLine($"   │ Estado:     {Ajustar(respuesta.Estado)}│");
        Console.WriteLine($"   └{new string('─', AnchoCaja)}┘");

        // [6.5] Registrar el paso para el informe final ([9]).
        _pasos.Add(respuesta);

        return respuesta;
    }

    // =========================================================================
    // [7] HERRAMIENTA 1 — delegar en el Agente de Investigación
    // =========================================================================
    /// <remarks>
    /// ⚙️ MFA: este método se publica al modelo como la herramienta `investigar_clima`
    /// (ver [1.3]). Los [Description] son lo que el modelo lee para decidir.
    /// </remarks>
    [Description("Consulta el clima de una ciudad delegando en el Agente de Investigación.")]
    private async Task<string> InvestigarClimaAsync(
        [Description("Nombre de la ciudad, p. ej. 'Tokio'")] string ciudad,
        [Description("País de la ciudad, p. ej. 'Japón'")] string pais = "",
        CancellationToken ct = default)
    {
        // [7.1] Sin contacto no hay delegación posible: se informa del error en vez
        //       de simular una respuesta.
        if (_agenteInvestigacion is null)
            return "ERROR: el Agente de Investigación no está conectado.";

        // [7.2] 📡 A2A: delegar con el tipo de mensaje que ese agente entiende.
        var respuesta = await DelegarPorA2AAsync(
            _agenteInvestigacion,
            TipoMensaje.PeticionInvestigacion,
            new() { ["task"] = "weather_lookup", ["city"] = ciudad, ["country"] = pais },
            ct);

        // [7.3] Devolver al modelo SOLO el texto útil: es lo que él encadenará hacia
        //       la siguiente herramienta.
        return respuesta.EsExito
            ? respuesta.Contenido ?? ""
            : $"ERROR: {respuesta.Error}";
    }

    // =========================================================================
    // [8] HERRAMIENTA 2 — delegar en el Agente Ejecutor
    // =========================================================================
    [Description("Guarda un texto en un archivo delegando en el Agente Ejecutor.")]
    private async Task<string> GuardarEnArchivoAsync(
        [Description("Texto completo a guardar")] string contenido,
        [Description("Nombre del archivo, p. ej. 'informe_clima.txt'")] string nombreArchivo = "informe_clima.txt",
        CancellationToken ct = default)
    {
        if (_agenteEjecutor is null)
            return "ERROR: el Agente Ejecutor no está conectado.";

        // [8.1] 📡 A2A: el Ejecutor espera `operation`, `filename` y `content`.
        var respuesta = await DelegarPorA2AAsync(
            _agenteEjecutor,
            TipoMensaje.PeticionEjecucion,
            new() { ["operation"] = "write_file", ["filename"] = nombreArchivo, ["content"] = contenido },
            ct);

        return respuesta.EsExito
            ? respuesta.Contenido ?? $"Guardado en {nombreArchivo}"
            : $"ERROR: {respuesta.Error}";
    }

    // =========================================================================
    // [9] AGREGACIÓN — construir el informe final para el usuario
    // =========================================================================
    private InformeFlujo AgregarResultados(string resumenModelo)
    {
        var total = _pasos.Count;
        var exitosos = _pasos.Count(p => p.EsExito);

        Console.WriteLine();
        Console.WriteLine($"📊 Agregando resultados de {total} paso(s) delegado(s)...");

        return new InformeFlujo(
            // Sin pasos delegados el flujo igual se considera completado: el modelo
            // pudo haber respondido directamente (p. ej. un saludo).
            Estado: exitosos == total ? "completado" : "parcial",
            PasosTotales: total,
            PasosExitosos: exitosos,
            Pasos: [.. _pasos],
            Resumen: string.IsNullOrWhiteSpace(resumenModelo) ? "Flujo completado." : resumenModelo.Trim());
    }

    // 🔧 Infra: helpers de formato para las cajas del mensaje A2A.
    private static string Ajustar(string texto) => Recortar(texto, AnchoCaja - 13)!.PadRight(AnchoCaja - 13);

    private static string? Recortar(string? texto, int max) =>
        texto is null ? "" : texto.Length <= max ? texto : texto[..max];

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}

/// <summary>Informe agregado de un flujo de trabajo completo.</summary>
internal sealed record InformeFlujo(
    string Estado,
    int PasosTotales,
    int PasosExitosos,
    IReadOnlyList<RespuestaA2A> Pasos,
    string Resumen);
