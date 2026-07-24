namespace Scenario2.Host.A2A;

// =============================================================================
// CAPA 6 — LA RED A2A
// =============================================================================
// 🏛️ SOLID (OCP): dar de alta un cuarto agente es UNA línea de Registrar(). Ni la
//    red ni la demo necesitan un `if` nuevo por cada agente.

/// <summary>📡 A2A Directorio de agentes + entrega de mensajes.</summary>
public sealed class RedA2A
{
    private readonly Consola _consola;
    private readonly Dictionary<string, IAgenteA2A> _buzones = [];

    public RedA2A(Consola consola) => _consola = consola;

    /// <summary>[6] Da de alta el buzón de un agente.</summary>
    public void Registrar(IAgenteA2A agente) => _buzones[agente.Nombre] = agente;

    /// <summary>Agentes registrados, en el orden en que se dieron de alta.</summary>
    public IReadOnlyCollection<IAgenteA2A> Agentes => [.. _buzones.Values];

    /// <summary>📡 A2A Muestra el sobre y lo deposita en el buzón del destinatario.</summary>
    /// <remarks>
    /// Este método <b>es</b> el protocolo: el emisor no llama a un método del
    /// destinatario, entrega un mensaje a la red y la red lo enruta. Si el día de
    /// mañana esto viajara por HTTP, solo cambiaría aquí dentro.
    /// </remarks>
    public async Task<RespuestaA2A> EntregarAsync(MensajeA2A mensaje, CancellationToken ct = default)
    {
        _consola.SobreA2A(mensaje);

        if (!_buzones.TryGetValue(mensaje.Destinatario, out var destino))
        {
            _consola.Error($"Destinatario desconocido: {mensaje.Destinatario}");
            return new RespuestaA2A
            {
                Emisor = "RedA2A",
                Destinatario = mensaje.Emisor,
                Tipo = "error_de_entrega",
                Contenido = $"No hay ningún agente registrado como '{mensaje.Destinatario}'.",
                Exito = false,
            };
        }

        return await destino.AtenderAsync(mensaje, ct);
    }
}
