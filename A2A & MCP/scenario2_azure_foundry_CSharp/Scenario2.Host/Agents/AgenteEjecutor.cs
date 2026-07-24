using Microsoft.Agents.AI;
using Scenario2.Host.A2A;

namespace Scenario2.Host.Agents;

/// <summary>
/// [5.2] Agente Ejecutor — no busca nada: da forma a lo que otros encontraron.
/// </summary>
/// <remarks>
/// Ilustra que un agente NO necesita herramientas para aportar valor: su
/// especialidad está en las instrucciones.
/// </remarks>
public sealed class AgenteEjecutor : AgenteA2A
{
    public AgenteEjecutor(AIAgent agenteMfa, Consola consola)
        : base(
            nombre: "Agente Ejecutor",
            descripcion: "Estructura y resume la información que le envían.",
            agenteMfa: agenteMfa,
            consola: consola)
    {
    }

    public override IReadOnlySet<string> TiposAdmitidos { get; } =
        new HashSet<string> { TipoMensaje.SolicitudFormato };

    /// <summary>[8.5] Recibe el material en bruto y devuelve un informe legible.</summary>
    protected override async Task<string> ProcesarAsync(MensajeA2A mensaje, CancellationToken ct)
    {
        Consola.Info("🧱 Dando formato al material recibido…");
        Consola.Salto();
        return await ConversarAsync(mensaje.Contenido, ct);
    }
}
