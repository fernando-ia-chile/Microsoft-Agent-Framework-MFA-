using Microsoft.Agents.AI;
using Scenario2.Host.A2A;

namespace Scenario2.Host.Agents;

/// <summary>
/// [5.3] Agente Coordinador — la puerta de entrada del usuario.
/// </summary>
/// <remarks>
/// No tiene herramientas ni documentación: su trabajo es DELEGAR. Interviene dos
/// veces en el flujo:
/// <list type="bullet">
///   <item>al principio (<c>peticion_usuario</c>), traduciendo la pregunta en un
///         encargo concreto para el Agente de Investigación;</item>
///   <item>al final (<c>cierre_final</c>), redactando la respuesta que lee el usuario.</item>
/// </list>
/// </remarks>
public sealed class AgenteCoordinador : AgenteA2A
{
    public AgenteCoordinador(AIAgent agenteMfa, Consola consola)
        : base(
            nombre: "Agente Coordinador",
            descripcion: "Orquesta el trabajo de los demás agentes por A2A.",
            agenteMfa: agenteMfa,
            consola: consola)
    {
    }

    public override IReadOnlySet<string> TiposAdmitidos { get; } =
        new HashSet<string> { TipoMensaje.PeticionUsuario, TipoMensaje.CierreFinal };

    protected override async Task<string> ProcesarAsync(MensajeA2A mensaje, CancellationToken ct)
    {
        string indicacion;

        if (mensaje.Tipo == TipoMensaje.PeticionUsuario)
        {
            Consola.Info("🧭 Preparando el encargo para el Agente de Investigación…");
            Consola.Salto();
            indicacion =
                $"""
                Un usuario pregunta lo siguiente:
                «{mensaje.Contenido}»

                Tú NO tienes documentación ni herramientas. Redacta el encargo que le
                enviarás al Agente de Investigación para que busque la respuesta en
                Microsoft Learn. Responde ÚNICAMENTE con el texto del encargo, en
                español, en una o dos frases, sin saludos ni explicaciones.
                """;
        }
        else
        {
            Consola.Info("🧭 Redactando la respuesta final para el usuario…");
            Consola.Salto();
            indicacion =
                $"""
                El Agente Ejecutor te devuelve este informe ya formateado:

                {mensaje.Contenido}

                Preséntaselo al usuario como respuesta final a su pregunta original.
                Sé fiel al contenido, no inventes datos y responde en español.
                """;
        }

        return await ConversarAsync(indicacion, ct);
    }
}
