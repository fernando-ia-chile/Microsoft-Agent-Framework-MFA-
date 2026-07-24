using Scenario2.Host.A2A;

namespace Scenario2.Host;

// =============================================================================
// CAPA 2 — PRESENTACIÓN
// =============================================================================
// 🏛️ SOLID (SRP + DIP): TODO lo que se imprime vive aquí. Los agentes no llaman
//    a Console.Write: reciben una Consola. Así la lógica multiagente no depende
//    de la interfaz, y cambiar la terminal por una web o por logs no obligaría a
//    tocar un solo agente.

/// <summary>Interfaz de terminal de la demo: cabeceras, pasos, sobres A2A y pausas.</summary>
public sealed class Consola
{
    /// <summary>Ancho de las líneas decorativas.</summary>
    public const int Ancho = 78;

    /// <summary>
    /// Modo automático: sin terminal interactiva (por ejemplo, con la entrada
    /// redirigida) no se puede esperar a que el usuario pulse Enter.
    /// </summary>
    public bool Automatica { get; }

    public Consola(bool automatica) => Automatica = automatica;

    // ── Bloques de texto ─────────────────────────────────────────────────────
    public void Cabecera(string titulo)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', Ancho));
        Console.WriteLine(titulo);
        Console.WriteLine(new string('=', Ancho));
    }

    public void Paso(int numero, int total, string descripcion)
    {
        Console.WriteLine();
        Console.WriteLine($"[{numero}/{total}] {descripcion}");
        Console.WriteLine(new string('-', Ancho));
    }

    public void Info(string texto) => Console.WriteLine($"   {texto}");

    public void Exito(string texto) => Console.WriteLine($"\n✅ {texto}");

    public void Aviso(string texto) => Console.WriteLine($"\n⚠️  {texto}");

    public void Error(string texto) => Console.WriteLine($"\n❌ {texto}");

    /// <summary>Escribe SIN salto de línea: se usa para la salida en streaming.</summary>
    public void Fragmento(string texto) => Console.Write(texto);

    public void Salto() => Console.WriteLine();

    // ── El sobre A2A: la caja que enseña el mecanismo ────────────────────────
    /// <summary>
    /// 📡 A2A Dibuja el "sobre" de un mensaje entre agentes.
    /// </summary>
    /// <remarks>
    /// Es el elemento didáctico central del escenario: hace VISIBLE algo que
    /// normalmente ocurre en silencio. Emisor, destinatario, tipo y carga útil son
    /// exactamente los cuatro campos que necesita cualquier protocolo agente-a-agente.
    /// </remarks>
    public void SobreA2A(MensajeA2A mensaje)
    {
        var linea = new string('▔', Ancho);
        Console.WriteLine();
        Console.WriteLine(linea);
        Console.WriteLine("📨 MENSAJE A2A");
        Console.WriteLine(linea);
        Console.WriteLine($"  De:        {mensaje.Emisor}");
        Console.WriteLine($"  Para:      {mensaje.Destinatario}");
        Console.WriteLine($"  Tipo:      {mensaje.Tipo}");
        Console.WriteLine($"  Enviado:   {mensaje.EnviadoEn:yyyy-MM-ddTHH:mm:sszzz}");
        Console.WriteLine($"  Contenido: {Recortar(mensaje.Contenido)}");
        Console.WriteLine(linea);
    }

    /// <summary>🔧 Infra Deja el texto en una línea y lo acorta para que quepa en la caja.</summary>
    public static string Recortar(string? texto, int limite = 160)
    {
        var limpio = string.Join(' ', (texto ?? "").Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        return limpio.Length <= limite ? limpio : string.Concat(limpio.AsSpan(0, limite), "…");
    }

    // ── Interacción ──────────────────────────────────────────────────────────
    public void Pausa(string mensaje = "Pulsa Enter para continuar…")
    {
        if (Automatica)
        {
            Console.WriteLine($"\n{mensaje} [modo automático]");
            return;
        }

        Console.WriteLine();
        Console.Write(mensaje);
        Console.ReadLine();
    }

    public string Preguntar(string mensaje, string porDefecto)
    {
        if (Automatica)
        {
            Console.WriteLine($"\n{mensaje}");
            Console.WriteLine($"🤔 [modo automático] {porDefecto}");
            return porDefecto;
        }

        Console.WriteLine();
        Console.Write(mensaje);
        var respuesta = Console.ReadLine()?.Trim();

        if (string.IsNullOrWhiteSpace(respuesta))
        {
            Console.WriteLine($"⚠️  Sin respuesta: uso la pregunta por defecto → {porDefecto}");
            return porDefecto;
        }

        return respuesta;
    }

    public bool Confirmar(string mensaje)
    {
        if (Automatica)
        {
            Console.WriteLine($"{mensaje} [modo automático: SÍ]");
            return true;
        }

        Console.Write($"{mensaje} [S/n]: ");
        var respuesta = (Console.ReadLine() ?? "").Trim().ToLowerInvariant();
        return respuesta is "" or "s" or "si" or "sí" or "y" or "yes";
    }

    // ── Portada ──────────────────────────────────────────────────────────────
    /// <summary>[3] Portada: qué se va a ver y contra qué se está trabajando.</summary>
    public void Bienvenida(Configuracion configuracion)
    {
        Cabecera("Microsoft Agent Framework (MFA) — Demo interactiva A2A + MCP (C#)");
        Console.WriteLine("\nEn esta demo vas a ver, en este orden:");
        Console.WriteLine("  1. Cómo se crean tres agentes con MFA sobre Azure AI Foundry.");
        Console.WriteLine("  2. Cómo se envían mensajes A2A entre ellos, uno a uno.");
        Console.WriteLine("  3. Cómo el Agente de Investigación consulta Microsoft Learn por MCP,");
        Console.WriteLine("     pidiéndote permiso antes de cada llamada.");
        Console.WriteLine($"\n🔗 Proyecto Foundry: {configuracion.EndpointProyecto}");
        Console.WriteLine($"🧠 Modelo: {configuracion.Modelo}");
        Console.WriteLine($"🔌 Servidor MCP: {configuracion.UrlMcp}");

        if (Automatica)
            Console.WriteLine("\n[INFO] Sin terminal interactiva: la demo avanzará sola.");
    }
}
