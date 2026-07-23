using Scenario1.Host.A2A;
using Scenario1.Host.Agents;

namespace Scenario1.Host;

/// <summary>
/// Orquestador del Escenario 1: agentes locales con MCP y A2A.
/// </summary>
/// <remarks>
/// <para>
/// ORDEN DE EJECUCIÓN (los comentarios [n] siguen esta numeración):
/// <code>
///   [1]  CrearAsync                   -> construye los tres agentes
///   [2]  AbrirSesionesMcpAsync        -> abre las sesiones MCP (una vez por sesión)
///   [3]  VerificarConfiguracion       -> comprueba las credenciales
///   [4]  EjecutarFlujoCompletoAsync   -> delega en el Coordinador
///   [5]  DemostrarComunicacionA2AAsync-> mensajes A2A directos, sin Coordinador
///   [6]  DisposeAsync                 -> cierra las sesiones MCP
/// </code>
/// </para>
/// </remarks>
internal sealed class Orquestador : IAsyncDisposable
{
    private readonly ResearchAgent _investigacion;
    private readonly ExecutorAgent _ejecutor;
    private readonly CoordinatorAgent _coordinador;

    // =========================================================================
    // [1] CONSTRUCCIÓN — crea los tres agentes y los conecta entre sí
    // =========================================================================
    private Orquestador()
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("🚀 ESCENARIO 1: Agentes locales con Azure OpenAI y servidores MCP");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine();
        Console.WriteLine("📋 Inicializando agentes...");

        // [1.1] Los agentes especializados se crean primero: el Coordinador necesita
        //       una referencia a cada uno para poder delegarles trabajo por A2A.
        _investigacion = new ResearchAgent();
        _ejecutor = new ExecutorAgent();

        // [1.2] 📡 A2A: el Coordinador recibe a sus dos "contactos". Sin ellos, sus
        //       herramientas devolverían un error en vez de delegar.
        _coordinador = new CoordinatorAgent(_investigacion, _ejecutor);

        Console.WriteLine();
        Console.WriteLine("✅ ¡Los tres agentes se inicializaron correctamente!");
    }

    /// <summary>Crea el orquestador y abre las sesiones MCP.</summary>
    public static async Task<Orquestador> CrearAsync(CancellationToken ct = default)
    {
        // [3] Comprobar las credenciales antes de construir nada.
        VerificarConfiguracion();

        var orquestador = new Orquestador();
        await orquestador.AbrirSesionesMcpAsync(ct);
        return orquestador;
    }

    // =========================================================================
    // [2] CICLO DE VIDA MCP — abrir las sesiones de los servidores
    // =========================================================================
    /// <remarks>
    /// ⚙️ MFA + 🔌 MCP: cada agente lanza su servidor MCP como subproceso. Abrirlos
    /// aquí, una sola vez para toda la sesión interactiva, evita arrancar y matar los
    /// subprocesos en cada pregunta del usuario.
    /// </remarks>
    private async Task AbrirSesionesMcpAsync(CancellationToken ct)
    {
        Console.WriteLine();
        Console.WriteLine("🔌 Abriendo las sesiones MCP de los agentes...");
        await _investigacion.ConectarAsync(ct);
        await _ejecutor.ConectarAsync(ct);
    }

    // =========================================================================
    // [3] VERIFICACIÓN DE CONFIGURACIÓN
    // =========================================================================
    private static void VerificarConfiguracion()
    {
        // ⚠️ Los tres agentes llaman al modelo de verdad: sin credenciales válidas
        //    el escenario no funciona.
        var faltantes = Configuracion.VariablesFaltantes();

        if (faltantes.Count > 0)
        {
            Console.WriteLine();
            Console.WriteLine($"⚠️  Faltan variables de configuración: {string.Join(", ", faltantes)}");
            Console.WriteLine("   Edita Scenario1.Host/appsettings.json antes de continuar.");
            return;
        }

        Console.WriteLine();
        Console.WriteLine("✅ Configuración de Azure OpenAI verificada");
        Console.WriteLine($"   Endpoint: {Configuracion.Endpoint}");
        Console.WriteLine($"   Modelo:   {Configuracion.Deployment}");
    }

    // =========================================================================
    // [4] FLUJO COMPLETO — el camino normal: todo pasa por el Coordinador
    // =========================================================================
    /// <summary>Ejecuta el flujo multiagente completo para una petición del usuario.</summary>
    public async Task<InformeFlujo> EjecutarFlujoCompletoAsync(string peticion, CancellationToken ct = default)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("🎯 Iniciando el flujo de trabajo completo");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine();
        Console.WriteLine("👤 Petición del usuario:");
        Console.WriteLine($"   \"{peticion}\"");
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("📍 PASO 1: el Agente Coordinador planifica el flujo");
        Console.WriteLine(new string('=', 70));

        // [4.1] 📡 A2A: el orquestador NO habla con los agentes especializados. Solo
        //       entrega la petición al Coordinador, que decide y delega.
        var informe = await _coordinador.ProcesarPeticionUsuarioAsync(peticion, ct);

        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("✅ FLUJO COMPLETADO");
        Console.WriteLine(new string('=', 70));
        Console.WriteLine();
        Console.WriteLine("📊 Resultados finales:");
        Console.WriteLine($"   Estado: {informe.Estado}");
        Console.WriteLine($"   Pasos completados: {informe.PasosExitosos}/{informe.PasosTotales}");

        // [4.2] Detallar qué agente atendió cada paso delegado.
        for (var i = 0; i < informe.Pasos.Count; i++)
        {
            var paso = informe.Pasos[i];
            var icono = paso.EsExito ? "✅" : "❌";
            Console.WriteLine($"   {icono} Paso {i + 1}: {paso.AgenteId}");
        }

        return informe;
    }

    // =========================================================================
    // [5] DEMOSTRACIÓN A2A DIRECTA — sin pasar por el Coordinador
    // =========================================================================
    /// <summary>
    /// Envía mensajes A2A directos a cada agente, saltándose al Coordinador.
    /// </summary>
    /// <remarks>
    /// Sirve para ver el protocolo "desnudo": qué mensaje entra y qué respuesta sale,
    /// sin que un LLM decida nada por el camino.
    /// </remarks>
    public async Task DemostrarComunicacionA2AAsync(CancellationToken ct = default)
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("🔄 Demostración de comunicación Agente-a-Agente (A2A)");
        Console.WriteLine(new string('=', 70));

        // [5.1] Demo 1 — mensaje directo al Agente de Investigación.
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("📡 Demo 1: mensaje directo -> Agente de Investigación");
        Console.WriteLine(new string('=', 70));

        var respuestaInvestigacion = await _investigacion.ManejarMensajeAsync(new MensajeA2A
        {
            Emisor = "orquestador",
            Destinatario = _investigacion.AgenteId,
            Tipo = TipoMensaje.PeticionInvestigacion,
            Datos = new() { ["task"] = "weather_lookup", ["city"] = "Valparaíso", ["country"] = "Chile" },
        }, ct);

        Console.WriteLine();
        Console.WriteLine($"✅ Estado devuelto: {respuestaInvestigacion.Estado}");

        // [5.2] Demo 2 — mensaje directo al Agente Ejecutor, encadenando el resultado
        //       anterior. Es A2A a mano: aquí no hay LLM decidiendo el encadenamiento.
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("📡 Demo 2: mensaje directo -> Agente Ejecutor");
        Console.WriteLine(new string('=', 70));

        var respuestaEjecucion = await _ejecutor.ManejarMensajeAsync(new MensajeA2A
        {
            Emisor = "orquestador",
            Destinatario = _ejecutor.AgenteId,
            Tipo = TipoMensaje.PeticionEjecucion,
            Datos = new()
            {
                ["operation"] = "write_file",
                ["filename"] = "demo_a2a.txt",
                ["content"] = respuestaInvestigacion.Contenido ?? "Sin datos",
            },
        }, ct);

        Console.WriteLine();
        Console.WriteLine($"✅ Estado devuelto: {respuestaEjecucion.Estado}");

        // [5.3] Demo 3 — ping a los tres agentes. El mensaje `ping` no gasta tokens ni
        //       toca MCP: solo comprueba que el buzón del agente responde.
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("📡 Demo 3: comprobación de salud (ping a los tres agentes)");
        Console.WriteLine(new string('=', 70));

        // 📡 A2A: los tres implementan IAgenteA2A, así que se recorren como una lista
        //    homogénea aunque por dentro sean muy distintos.
        IAgenteA2A[] agentes = [_investigacion, _coordinador, _ejecutor];

        foreach (var agente in agentes)
        {
            var respuesta = await agente.ManejarMensajeAsync(new MensajeA2A
            {
                Emisor = "orquestador",
                Destinatario = agente.AgenteId,
                Tipo = TipoMensaje.Ping,
            }, ct);

            var icono = respuesta.Estado == EstadoA2A.Activo ? "✅" : "❌";
            Console.WriteLine($"   {icono} {agente.Nombre}: {respuesta.Estado}");
        }
    }

    // =========================================================================
    // DIAGRAMA DE ARQUITECTURA
    // =========================================================================
    public static void ImprimirDiagramaArquitectura()
    {
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("🏗️  ARQUITECTURA DEL ESCENARIO 1");
        Console.WriteLine(new string('=', 70));
        // ⚠️ Los servidores MCP NO escuchan en ningún puerto: el transporte es stdio
        //    y cada servidor es un SUBPROCESO del agente que lo usa.
        Console.WriteLine("""

    ┌──────────────────────────────────────────────────────────┐
    │                    Entorno local                         │
    │                                                          │
    │                    👤 Usuario                            │
    │                        │                                 │
    │                        ▼                                 │
    │              ┌───────────────────┐                       │
    │              │  Agente 2         │                       │
    │              │  COORDINADOR      │  (decide y delega)    │
    │              └─────────┬─────────┘                       │
    │                        │ A2A                             │
    │            ┌───────────┴───────────┐                     │
    │            ▼                       ▼                     │
    │   ┌─────────────────┐    ┌──────────────────┐            │
    │   │   Agente 1      │    │   Agente 3       │            │
    │   │   INVESTIGACIÓN │    │   EJECUTOR       │            │
    │   └────────┬────────┘    └─────────┬────────┘            │
    │            │ MCP (stdio)           │ MCP (stdio)         │
    │            ▼                       ▼                     │
    │   ┌─────────────────┐    ┌──────────────────┐            │
    │   │ Servidor MCP    │    │ Servidor MCP     │            │
    │   │ Clima           │    │ Archivos         │            │
    │   │ (subproceso)    │    │ (subproceso)     │            │
    │   └────────┬────────┘    └─────────┬────────┘            │
    │            │                       │                     │
    └────────────┼───────────────────────┼─────────────────────┘
                 ▼                       ▼
        🌍 API Open-Meteo        📂 agent_workspace/

    Los tres agentes usan Azure OpenAI como modelo.
""");
    }

    // =========================================================================
    // [6] CIERRE — liberar las sesiones MCP y los subprocesos
    // =========================================================================
    public async ValueTask DisposeAsync()
    {
        Console.WriteLine();
        Console.WriteLine("🔌 Cerrando las sesiones MCP...");
        await _ejecutor.DisposeAsync();
        await _investigacion.DisposeAsync();
        await _coordinador.DisposeAsync();
    }
}
