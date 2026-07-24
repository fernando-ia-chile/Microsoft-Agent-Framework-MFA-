using Microsoft.Agents.AI;
using ModelContextProtocol.Client;
using Scenario2.Host.A2A;
using Scenario2.Host.Aprobacion;

namespace Scenario2.Host.Agents;

/// <summary>
/// [5.1] Agente de Investigación — el ÚNICO que tiene herramientas.
/// </summary>
/// <remarks>
/// Consulta la documentación oficial a través del servidor MCP remoto de
/// Microsoft Learn. No inventa: busca, lee y cita.
/// </remarks>
public sealed class AgenteInvestigacion : AgenteA2A
{
    private readonly McpClient _clienteMcp;
    private readonly IReadOnlyList<McpClientTool> _herramientas;

    public AgenteInvestigacion(
        AIAgent agenteMfa,
        McpClient clienteMcp,
        IReadOnlyList<McpClientTool> herramientas,
        Consola consola,
        IPoliticaDeAprobacion politica)
        : base(
            nombre: "Agente de Investigación",
            descripcion: "Busca en la documentación de Microsoft Learn vía MCP.",
            agenteMfa: agenteMfa,
            consola: consola,
            politica: politica)
    {
        _clienteMcp = clienteMcp;
        _herramientas = herramientas;
    }

    public override IReadOnlySet<string> TiposAdmitidos { get; } =
        new HashSet<string> { TipoMensaje.SolicitudInvestigacion };

    /// <summary>[8.3] Traduce el encargo A2A a una consulta y deja decidir al modelo.</summary>
    protected override async Task<string> ProcesarAsync(MensajeA2A mensaje, CancellationToken ct)
    {
        Consola.Info("📡 Investigando en Microsoft Learn…");
        Consola.Salto();
        return await ConversarAsync(mensaje.Contenido, ct);
    }

    /// <summary>🔌 MCP Nombres de las herramientas que publica el servidor.</summary>
    /// <remarks>
    /// Nadie las escribió a mano: llegaron en el handshake del protocolo. Si
    /// Microsoft añade una herramienta mañana, aparece aquí sin tocar el código.
    /// </remarks>
    public IReadOnlyList<string> HerramientasDescubiertas() =>
        [.. _herramientas.Select(h => h.Name)];

    /// <summary>[9] 🔌 MCP Cierra la sesión HTTP con el servidor MCP.</summary>
    public override async ValueTask DisposeAsync() => await _clienteMcp.DisposeAsync();
}
