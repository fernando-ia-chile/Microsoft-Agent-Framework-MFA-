using Scenario2.Host.A2A;

namespace Scenario2.Host;

// =============================================================================
// CAPA 8 — EL GUION DE LA DEMOSTRACIÓN
// =============================================================================
// 🏛️ SOLID (SRP): esta clase solo sabe CONTAR la historia de los 7 pasos. No
//    construye agentes ni imprime cajas: pide a la red que entregue mensajes y a
//    la consola que los muestre.

/// <summary>[8] Los siete pasos del flujo multiagente, uno a uno y con pausas.</summary>
public sealed class DemostracionA2A
{
    private const string Usuario = "Usuario";

    /// <summary>Pregunta que se usa si el usuario no escribe ninguna.</summary>
    public const string PreguntaPorDefecto =
        "¿Qué niveles de servicio admiten servidores MCP en Azure API Management?";

    private readonly RedA2A _red;
    private readonly Consola _consola;

    public DemostracionA2A(RedA2A red, Consola consola)
    {
        _red = red;
        _consola = consola;
    }

    public async Task<bool> EjecutarAsync(CancellationToken ct = default)
    {
        _consola.Cabecera("FASE 2 — DEMOSTRACIÓN DE COMUNICACIÓN A2A");

        _consola.Info("🌐 Red de agentes registrada:");
        foreach (var agente in _red.Agentes)
            _consola.Info($"   • {agente.Nombre} — {agente.Descripcion}");

        // [8.1] La pregunta del usuario.
        _consola.Cabecera("HAZ UNA PREGUNTA");
        var pregunta = _consola.Preguntar("🤔 Escribe tu pregunta sobre Microsoft/Azure: ", PreguntaPorDefecto);
        _consola.Pausa("Pulsa Enter para arrancar el flujo…");

        // ── [8.2] PASO 1 — Usuario → Coordinador ─────────────────────────────
        _consola.Cabecera("PASO 1/7 — Usuario → Agente Coordinador");
        var respuestaCoordinador = await _red.EntregarAsync(new MensajeA2A
        {
            Emisor = Usuario,
            Destinatario = "Agente Coordinador",
            Tipo = TipoMensaje.PeticionUsuario,
            Contenido = pregunta,
        }, ct);

        if (!respuestaCoordinador.Exito)
        {
            _consola.Error("El Coordinador no pudo procesar la petición.");
            return false;
        }

        // 📌 Ojo al detalle: el encargo que redacta el Coordinador SE USA en el paso
        //    siguiente. En la versión antigua de esta demo se lanzaba el run del
        //    Coordinador y su respuesta se descartaba sin leerla.
        var encargo = string.IsNullOrWhiteSpace(respuestaCoordinador.Contenido)
            ? pregunta
            : respuestaCoordinador.Contenido;

        _consola.Exito("El Coordinador ha redactado el encargo de investigación");
        _consola.Pausa("Pulsa Enter para ver la delegación A2A…");

        // ── [8.3] PASO 2 — Coordinador → Investigación ───────────────────────
        _consola.Cabecera("PASO 2/7 — Agente Coordinador → Agente de Investigación (A2A)");
        _consola.Info("El Coordinador delega: él no tiene documentación, el otro sí.");

        // ── [8.4] PASO 3 — Investigación → MCP (ocurre DENTRO de la entrega) ──
        _consola.Info("Durante esta entrega verás el PASO 3: las llamadas MCP y su aprobación.");
        var respuestaInvestigacion = await _red.EntregarAsync(new MensajeA2A
        {
            Emisor = "Agente Coordinador",
            Destinatario = "Agente de Investigación",
            Tipo = TipoMensaje.SolicitudInvestigacion,
            Contenido = encargo,
            Datos = new Dictionary<string, string> { ["pregunta_original"] = pregunta },
        }, ct);

        if (!respuestaInvestigacion.Exito || string.IsNullOrWhiteSpace(respuestaInvestigacion.Contenido))
        {
            _consola.Error("El Agente de Investigación no devolvió resultados.");
            return false;
        }

        // ── [8.5] PASO 4 — Investigación → Coordinador ───────────────────────
        _consola.Cabecera("PASO 4/7 — Agente de Investigación → Agente Coordinador (A2A)");
        _consola.Exito($"Investigación completada: {respuestaInvestigacion.Contenido.Length} caracteres");
        _consola.Pausa("Pulsa Enter para pasar el material al Agente Ejecutor…");

        // ── [8.6] PASO 5 — Coordinador → Ejecutor ────────────────────────────
        _consola.Cabecera("PASO 5/7 — Agente Coordinador → Agente Ejecutor (A2A)");
        var respuestaEjecutor = await _red.EntregarAsync(new MensajeA2A
        {
            Emisor = "Agente Coordinador",
            Destinatario = "Agente Ejecutor",
            Tipo = TipoMensaje.SolicitudFormato,
            Contenido =
                $"Da formato y resume este material de investigación para el usuario, " +
                $"que preguntó: «{pregunta}».\n\n{respuestaInvestigacion.Contenido}",
        }, ct);

        if (!respuestaEjecutor.Exito || string.IsNullOrWhiteSpace(respuestaEjecutor.Contenido))
        {
            _consola.Error("El Agente Ejecutor no devolvió resultados.");
            return false;
        }

        // ── [8.7] PASO 6 — Ejecutor → Coordinador ────────────────────────────
        _consola.Cabecera("PASO 6/7 — Agente Ejecutor → Agente Coordinador (A2A)");
        _consola.Exito("Formato aplicado");
        _consola.Pausa("Pulsa Enter para ver la respuesta final…");

        // ── [8.8] PASO 7 — Coordinador → Usuario ─────────────────────────────
        _consola.Cabecera("PASO 7/7 — Agente Coordinador → Usuario");
        var respuestaFinal = await _red.EntregarAsync(new MensajeA2A
        {
            Emisor = Usuario,
            Destinatario = "Agente Coordinador",
            Tipo = TipoMensaje.CierreFinal,
            Contenido = respuestaEjecutor.Contenido,
        }, ct);

        if (!respuestaFinal.Exito)
        {
            _consola.Error("El Coordinador no pudo redactar la respuesta final.");
            return false;
        }

        Resumen();
        return true;
    }

    private void Resumen()
    {
        _consola.Cabecera("RESUMEN DEL FLUJO A2A");
        Console.WriteLine("  1. ✅ Usuario                 → Agente Coordinador");
        Console.WriteLine("  2. ✅ Agente Coordinador      → Agente de Investigación   (A2A)");
        Console.WriteLine("  3. ✅ Agente de Investigación → Microsoft Learn           (MCP)");
        Console.WriteLine("  4. ✅ Agente de Investigación → Agente Coordinador        (A2A)");
        Console.WriteLine("  5. ✅ Agente Coordinador      → Agente Ejecutor           (A2A)");
        Console.WriteLine("  6. ✅ Agente Ejecutor         → Agente Coordinador        (A2A)");
        Console.WriteLine("  7. ✅ Agente Coordinador      → Usuario");
        Console.WriteLine("\n🎉 Flujo multiagente completo demostrado de principio a fin.");
    }
}
