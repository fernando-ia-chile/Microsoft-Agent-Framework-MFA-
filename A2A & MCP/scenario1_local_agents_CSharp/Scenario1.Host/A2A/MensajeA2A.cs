namespace Scenario1.Host.A2A;

// =============================================================================
// CONTRATO DEL PROTOCOLO AGENTE-A-AGENTE (A2A)
// =============================================================================
// 📡 A2A: estos dos tipos son el "sobre" que comparten los tres agentes.
//    Mientras todos hablen este mismo formato, son intercambiables como destinos:
//    el emisor no necesita saber nada del receptor más allá del contrato.
//
// 🔧 Infra: en Python esto eran diccionarios sueltos. En C# se modelan como
//    records, así el compilador comprueba la forma del mensaje.

/// <summary>Tipos de mensaje que entienden los agentes de este escenario.</summary>
public static class TipoMensaje
{
    public const string PeticionInvestigacion = "research_request";
    public const string PeticionEjecucion = "execution_request";
    public const string PeticionFlujo = "workflow_request";
    public const string Ping = "ping";
}

/// <summary>Estados posibles de una respuesta A2A.</summary>
public static class EstadoA2A
{
    public const string Exito = "success";
    public const string Error = "error";
    public const string Activo = "active";
}

/// <summary>
/// Mensaje A2A: el sobre que un agente envía a otro.
/// </summary>
public sealed record MensajeA2A
{
    /// <summary>Quién envía el mensaje.</summary>
    public required string Emisor { get; init; }

    /// <summary>Quién debe recibirlo.</summary>
    public required string Destinatario { get; init; }

    /// <summary>Tipo de petición (ver <see cref="TipoMensaje"/>).</summary>
    public required string Tipo { get; init; }

    /// <summary>Carga útil: los parámetros concretos de la petición.</summary>
    public Dictionary<string, object?> Datos { get; init; } = [];

    /// <summary>Marca temporal del envío.</summary>
    public DateTimeOffset MarcaTemporal { get; init; } = DateTimeOffset.UtcNow;
}

/// <summary>
/// Respuesta A2A: lo que el agente destino devuelve al emisor.
/// </summary>
public sealed record RespuestaA2A
{
    /// <summary>Quién responde.</summary>
    public required string AgenteId { get; init; }

    /// <summary>Resultado de la operación (ver <see cref="EstadoA2A"/>).</summary>
    public required string Estado { get; init; }

    /// <summary>Tarea u operación atendida.</summary>
    public string? Tarea { get; init; }

    /// <summary>Texto útil producido por el agente (lo que se encadena al siguiente).</summary>
    public string? Contenido { get; init; }

    /// <summary>Detalle del fallo, si lo hubo.</summary>
    public string? Error { get; init; }

    /// <summary>Información adicional (fuente de los datos, confianza, etc.).</summary>
    public Dictionary<string, string> Metadatos { get; init; } = [];

    public bool EsExito => Estado == EstadoA2A.Exito;

    public static RespuestaA2A Exitosa(string agenteId, string contenido, string? tarea = null,
        Dictionary<string, string>? metadatos = null) => new()
    {
        AgenteId = agenteId,
        Estado = EstadoA2A.Exito,
        Tarea = tarea,
        Contenido = contenido,
        Metadatos = metadatos ?? [],
    };

    public static RespuestaA2A Fallida(string agenteId, string error, string? tarea = null) => new()
    {
        AgenteId = agenteId,
        Estado = EstadoA2A.Error,
        Tarea = tarea,
        Error = error,
    };

    public static RespuestaA2A Pong(string agenteId) => new()
    {
        AgenteId = agenteId,
        Estado = EstadoA2A.Activo,
        Tarea = "pong",
    };
}

/// <summary>
/// Contrato común de los tres agentes.
/// </summary>
/// <remarks>
/// 📡 A2A: <b>este interfaz es la clave del escenario.</b> Todos los agentes exponen
/// el mismo buzón asíncrono, así que el Coordinador puede delegar en cualquiera de
/// ellos sin conocer su implementación. En Python esto era una convención (todos
/// tenían un método <c>handle_message</c>); en C# el compilador la hace obligatoria.
/// </remarks>
public interface IAgenteA2A : IAsyncDisposable
{
    /// <summary>Identificador del agente, usado como destinatario en los mensajes.</summary>
    string AgenteId { get; }

    /// <summary>Nombre legible del agente.</summary>
    string Nombre { get; }

    /// <summary>Rol que desempeña dentro del escenario.</summary>
    string Rol { get; }

    /// <summary>Buzón del agente: punto de entrada de todo mensaje A2A entrante.</summary>
    Task<RespuestaA2A> ManejarMensajeAsync(MensajeA2A mensaje, CancellationToken ct = default);
}
