using System.Text;
using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using Scenario2.Host.A2A;
using Scenario2.Host.Aprobacion;

namespace Scenario2.Host.Agents;

// =============================================================================
// CAPA 5 — LOS AGENTES
// =============================================================================
// 🏛️ SOLID (LSP): los tres agentes heredan de esta clase y exponen el MISMO
//    método AtenderAsync(). Por eso la red A2A puede tratarlos como equivalentes
//    y entregar un mensaje sin saber a quién se lo está dando.

/// <summary>Base común de todo agente que participa en la red A2A.</summary>
/// <remarks>
/// Implementa el patrón <b>método plantilla</b>: <see cref="AtenderAsync"/> (el buzón)
/// es igual para todos, y cada agente concreto solo rellena <see cref="ProcesarAsync"/>.
/// </remarks>
public abstract class AgenteA2A : IAgenteA2A
{
    /// <summary>Nº máximo de rondas de aprobación antes de rendirse (evita bucles).</summary>
    protected const int MaximoRondas = 6;

    private readonly AIAgent _agente;
    private AgentSession? _sesion;

    protected AgenteA2A(
        string nombre,
        string descripcion,
        AIAgent agenteMfa,
        Consola consola,
        IPoliticaDeAprobacion? politica = null)
    {
        Nombre = nombre;
        Descripcion = descripcion;
        Consola = consola;
        Politica = politica;
        _agente = agenteMfa;
    }

    public string Nombre { get; }

    public string Descripcion { get; }

    /// <summary>📡 A2A Las capacidades que este agente publica hacia los demás.</summary>
    public abstract IReadOnlySet<string> TiposAdmitidos { get; }

    /// <summary>Consola inyectada: los agentes NO llaman a Console directamente.</summary>
    protected Consola Consola { get; }

    /// <summary>Política de aprobación de herramientas. Null = no hay herramientas.</summary>
    protected IPoliticaDeAprobacion? Politica { get; }

    // =========================================================================
    // [8.x] EL BUZÓN A2A: única puerta de entrada al agente
    // =========================================================================
    /// <summary>📡 A2A Recibe un sobre y decide qué hacer con él.</summary>
    /// <remarks>
    /// Tres ramas:
    /// <list type="bullet">
    ///   <item><c>ping</c> → prueba de vida, no gasta tokens.</item>
    ///   <item>tipo conocido → lo procesa el agente concreto.</item>
    ///   <item>tipo desconocido → error explícito (NUNCA una respuesta inventada).</item>
    /// </list>
    /// </remarks>
    public async Task<RespuestaA2A> AtenderAsync(MensajeA2A mensaje, CancellationToken ct = default)
    {
        if (mensaje.Tipo == TipoMensaje.Ping)
            return Responder(mensaje, $"{Nombre} operativo. {Descripcion}");

        if (!TiposAdmitidos.Contains(mensaje.Tipo))
            return Responder(mensaje, $"{Nombre} no atiende mensajes de tipo '{mensaje.Tipo}'.", exito: false);

        var texto = await ProcesarAsync(mensaje, ct);
        return Responder(mensaje, texto);
    }

    private RespuestaA2A Responder(MensajeA2A mensaje, string contenido, bool exito = true) => new()
    {
        Emisor = Nombre,
        Destinatario = mensaje.Emisor,
        Tipo = $"{mensaje.Tipo}_respuesta",
        Contenido = contenido,
        Exito = exito,
    };

    /// <summary>Lo único que cada agente concreto tiene que implementar.</summary>
    protected abstract Task<string> ProcesarAsync(MensajeA2A mensaje, CancellationToken ct);

    // =========================================================================
    // EL TURNO DE CONVERSACIÓN CON EL MODELO (compartido por los tres agentes)
    // =========================================================================
    /// <summary>⚙️ MFA Ejecuta un turno completo contra el modelo y devuelve el texto.</summary>
    /// <remarks>
    /// Dentro de este método ocurre TODO esto:
    /// <list type="number">
    ///   <item>MFA envía instrucciones + historial + catálogo de herramientas.</item>
    ///   <item>El modelo decide si responde o si llama a una herramienta.</item>
    ///   <item>Si la herramienta exige aprobación, el framework NO la ejecuta:
    ///         emite un <c>ToolApprovalRequestContent</c> y se detiene.</item>
    ///   <item>Nosotros aprobamos (o no) y volvemos a llamar con esas respuestas.</item>
    ///   <item>MFA ejecuta la herramienta por MCP y el modelo redacta con el resultado.</item>
    /// </list>
    /// El bucle <c>for</c> es exactamente ese ida y vuelta de aprobaciones.
    /// </remarks>
    protected async Task<string> ConversarAsync(string entrada, CancellationToken ct)
    {
        // ⚙️ MFA La SESIÓN es el hilo de conversación. Mantenerla viva es lo que
        //    hace que el agente recuerde los turnos anteriores. En el SDK antiguo
        //    esto eran los "threads" que había que crear a mano contra el servicio.
        _sesion ??= await _agente.CreateSessionAsync(ct);

        var partes = new StringBuilder();
        List<ChatMessage> mensajes = [new(ChatRole.User, entrada)];

        for (var ronda = 0; ronda < MaximoRondas; ronda++)
        {
            var pendientes = new List<ToolApprovalRequestContent>();

            // ⚙️ MFA RunStreamingAsync devuelve un flujo asíncrono de fragmentos: el
            //    texto se ve aparecer en vivo, como en un chat, en lugar de saltar
            //    de golpe al final. (La variante sin streaming es RunAsync.)
            await foreach (var actualizacion in _agente.RunStreamingAsync(mensajes, _sesion, cancellationToken: ct))
            {
                if (!string.IsNullOrEmpty(actualizacion.Text))
                {
                    Consola.Fragmento(actualizacion.Text);
                    partes.Append(actualizacion.Text);
                }

                // ⚙️ MFA Las solicitudes de aprobación viajan como un contenido más
                //    dentro del flujo, junto al texto.
                pendientes.AddRange(actualizacion.Contents.OfType<ToolApprovalRequestContent>());
            }

            if (pendientes.Count == 0) break;

            Consola.Salto();
            mensajes = [new ChatMessage(ChatRole.User, await ResolverAprobacionesAsync(pendientes, ct))];
        }

        Consola.Salto();
        return partes.ToString().Trim();
    }

    /// <summary>🔌 MCP Convierte cada solicitud pendiente en un sí o un no.</summary>
    private async Task<IList<AIContent>> ResolverAprobacionesAsync(
        IEnumerable<ToolApprovalRequestContent> solicitudes, CancellationToken ct)
    {
        var respuestas = new List<AIContent>();

        foreach (var solicitud in solicitudes)
        {
            var llamada = solicitud.ToolCall as FunctionCallContent;
            var nombre = llamada?.Name ?? "(desconocida)";
            var argumentos = llamada?.Arguments is { } args
                ? JsonSerializer.Serialize(args)
                : "{}";

            var aprobar = Politica is null || await Politica.DecidirAsync(nombre, argumentos, ct);
            if (!aprobar) Consola.Aviso($"Llamada RECHAZADA: {nombre}");

            // ⚙️ MFA Esta es la respuesta que el framework espera de vuelta.
            respuestas.Add(solicitud.CreateResponse(aprobar));
        }

        return respuestas;
    }

    // =========================================================================
    // CICLO DE VIDA
    // =========================================================================
    /// <summary>[7] Datos del agente para la ficha JSON.</summary>
    public FichaAgente Ficha() => new(
        Nombre,
        Descripcion,
        [.. TiposAdmitidos.OrderBy(t => t, StringComparer.Ordinal)],
        "efímero (vive solo durante esta ejecución)");

    /// <summary>[9] Por defecto no hay nada que cerrar; el Investigador lo redefine.</summary>
    public virtual ValueTask DisposeAsync() => ValueTask.CompletedTask;
}
