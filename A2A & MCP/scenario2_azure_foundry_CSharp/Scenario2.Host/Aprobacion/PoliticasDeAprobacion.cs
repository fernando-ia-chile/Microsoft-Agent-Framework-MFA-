namespace Scenario2.Host.Aprobacion;

// =============================================================================
// CAPA 4 — POLÍTICA DE APROBACIÓN DE HERRAMIENTAS MCP
// =============================================================================
// 🏛️ SOLID (OCP + DIP): "quién decide si una herramienta puede ejecutarse" es una
//    pieza intercambiable. Hoy hay dos implementaciones; mañana podría haber una
//    que consulte una lista blanca o pida el visto bueno a un supervisor, sin
//    tocar ni una línea de los agentes.

/// <summary>Decide si se autoriza la ejecución de una herramienta MCP.</summary>
public interface IPoliticaDeAprobacion
{
    /// <summary>Autoriza (o no) una llamada concreta.</summary>
    /// <param name="herramienta">Nombre de la herramienta que el modelo quiere usar.</param>
    /// <param name="argumentos">Argumentos con los que la quiere llamar.</param>
    Task<bool> DecidirAsync(string herramienta, string argumentos, CancellationToken ct = default);
}

/// <summary>🔌 MCP Pregunta al usuario por cada llamada. Es el "human-in-the-loop".</summary>
public sealed class AprobacionInteractiva : IPoliticaDeAprobacion
{
    private readonly Consola _consola;

    public AprobacionInteractiva(Consola consola) => _consola = consola;

    public Task<bool> DecidirAsync(string herramienta, string argumentos, CancellationToken ct = default)
    {
        var borde = new string('─', Consola.Ancho - 6);
        Console.WriteLine();
        Console.WriteLine($"  ┌{borde}┐");
        Console.WriteLine("  │ 🔐 SOLICITUD DE APROBACIÓN DE HERRAMIENTA MCP");
        Console.WriteLine($"  │ {new string('─', Consola.Ancho - 8)}");
        Console.WriteLine($"  │ Herramienta: {herramienta}");
        Console.WriteLine($"  │ Argumentos:  {Consola.Recortar(argumentos, Consola.Ancho - 24)}");
        Console.WriteLine($"  └{borde}┘");

        return Task.FromResult(_consola.Confirmar("  ¿Autorizas esta llamada?"));
    }
}

/// <summary>🔌 MCP Autoriza siempre, pero deja constancia en pantalla.</summary>
public sealed class AprobacionAutomatica : IPoliticaDeAprobacion
{
    private readonly Consola _consola;

    public AprobacionAutomatica(Consola consola) => _consola = consola;

    public Task<bool> DecidirAsync(string herramienta, string argumentos, CancellationToken ct = default)
    {
        _consola.Info($"🔐 Aprobación automática → {herramienta}");
        return Task.FromResult(true);
    }
}
