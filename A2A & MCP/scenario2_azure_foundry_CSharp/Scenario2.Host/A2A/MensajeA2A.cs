namespace Scenario2.Host.A2A;

// =============================================================================
// CAPA 3 — EL CONTRATO A2A
// =============================================================================
// 🏛️ SOLID: los mensajes son objetos INMUTABLES, no diccionarios sueltos. En
//    Python un typo como mensaje["remitente"] era un error silencioso en tiempo
//    de ejecución; aquí el compilador lo caza antes de compilar.

/// <summary>📡 A2A Vocabulario del protocolo. Constantes con nombre, no cadenas sueltas.</summary>
public static class TipoMensaje
{
    /// <summary>El usuario plantea su pregunta al Coordinador.</summary>
    public const string PeticionUsuario = "peticion_usuario";

    /// <summary>El Coordinador encarga una búsqueda al Agente de Investigación.</summary>
    public const string SolicitudInvestigacion = "solicitud_investigacion";

    /// <summary>El Coordinador encarga dar formato al Agente Ejecutor.</summary>
    public const string SolicitudFormato = "solicitud_formato";

    /// <summary>El Coordinador redacta la respuesta final para el usuario.</summary>
    public const string CierreFinal = "cierre_final";

    /// <summary>Prueba de vida: no gasta tokens.</summary>
    public const string Ping = "ping";
}

/// <summary>📡 A2A El sobre que viaja de un agente a otro.</summary>
public sealed record MensajeA2A
{
    /// <summary>Quién envía el mensaje.</summary>
    public required string Emisor { get; init; }

    /// <summary>Quién debe recibirlo.</summary>
    public required string Destinatario { get; init; }

    /// <summary>Tipo de petición (ver <see cref="TipoMensaje"/>).</summary>
    public required string Tipo { get; init; }

    /// <summary>Carga útil en texto: lo que el destinatario tiene que procesar.</summary>
    public required string Contenido { get; init; }

    /// <summary>Datos adicionales de contexto (opcional).</summary>
    public IReadOnlyDictionary<string, string> Datos { get; init; } =
        new Dictionary<string, string>();

    /// <summary>Marca temporal del envío.</summary>
    public DateTimeOffset EnviadoEn { get; init; } = DateTimeOffset.UtcNow;
}

/// <summary>📡 A2A Lo que el destinatario devuelve al emisor.</summary>
public sealed record RespuestaA2A
{
    /// <summary>Quién responde.</summary>
    public required string Emisor { get; init; }

    /// <summary>A quién responde.</summary>
    public required string Destinatario { get; init; }

    /// <summary>Tipo de la respuesta (normalmente el tipo entrante + "_respuesta").</summary>
    public required string Tipo { get; init; }

    /// <summary>Texto producido por el agente: lo que se encadena al siguiente paso.</summary>
    public required string Contenido { get; init; }

    /// <summary>Indica si el agente pudo atender el mensaje.</summary>
    public bool Exito { get; init; } = true;
}

// =============================================================================
// EL CONTRATO COMÚN DE LOS AGENTES
// =============================================================================
/// <summary>Contrato que convierte a un objeto en un destino A2A válido.</summary>
/// <remarks>
/// 🏛️ SOLID (LSP + ISP): <b>este interfaz es la clave del escenario.</b> Todos los
/// agentes exponen el mismo buzón asíncrono, así que la red puede entregarles un
/// mensaje sin saber a quién se lo está dando. En Python esto era una convención
/// (todos <i>tenían</i> un método <c>atender</c>); en C# el compilador la exige.
/// </remarks>
public interface IAgenteA2A : IAsyncDisposable
{
    /// <summary>Nombre del agente. Se usa como dirección en los mensajes.</summary>
    string Nombre { get; }

    /// <summary>Qué sabe hacer, en una frase.</summary>
    string Descripcion { get; }

    /// <summary>📡 A2A Las capacidades que este agente publica hacia los demás.</summary>
    IReadOnlySet<string> TiposAdmitidos { get; }

    /// <summary>Buzón del agente: única puerta de entrada de todo mensaje A2A.</summary>
    Task<RespuestaA2A> AtenderAsync(MensajeA2A mensaje, CancellationToken ct = default);

    /// <summary>Datos del agente para la ficha JSON.</summary>
    FichaAgente Ficha();
}

/// <summary>Resumen de un agente, tal como se guarda en la ficha JSON.</summary>
/// <param name="Nombre">Nombre del agente.</param>
/// <param name="Descripcion">Qué sabe hacer.</param>
/// <param name="TiposAdmitidos">Mensajes que atiende.</param>
/// <param name="Persistencia">Aclara que el agente no queda registrado en Foundry.</param>
public sealed record FichaAgente(
    string Nombre,
    string Descripcion,
    IReadOnlyList<string> TiposAdmitidos,
    string Persistencia);
