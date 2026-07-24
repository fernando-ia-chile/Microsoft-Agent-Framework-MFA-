// =============================================================================
// ESCENARIO 2 (C#) — Agentes en Azure AI Foundry + MCP de Microsoft Learn
// =============================================================================
// Demo interactiva del Microsoft Agent Framework (MFA) que enseña, paso a paso:
//
//   1. Cómo se CREAN tres agentes (Investigación, Ejecutor, Coordinador).
//   2. Cómo se pasan MENSAJES A2A (Agent-to-Agent) entre ellos, en directo.
//   3. Cómo un agente usa HERRAMIENTAS MCP remotas (Microsoft Learn) y cómo se
//      APRUEBA cada llamada antes de que se ejecute (human-in-the-loop).
//
// -----------------------------------------------------------------------------
// MAPA DEL FLUJO  (el número de cada comentario del proyecto remite a esta tabla;
//                  sigue el ORDEN REAL DE EJECUCIÓN, no el orden de los archivos)
// -----------------------------------------------------------------------------
//  [0]   Arranque .................. UTF-8 y configuración        → Program.cs
//  [1]   Main() .................... punto de entrada             → Program.cs
//  [2]   Configuracion.DesdeEntorno() lee y VALIDA appsettings     → Configuracion.cs
//  [3]   Consola.Bienvenida() ...... portada de la demo           → Consola.cs
//  [4]   FabricaDeAgentes .......... crea el AIProjectClient      → FabricaDeAgentes.cs
//  [5]   FASE 1 — creación de agentes
//        [5.1] CrearAgenteInvestigacionAsync() . agente + MCP remoto + aprobación
//        [5.2] CrearAgenteEjecutorAsync() ...... agente sin herramientas
//        [5.3] CrearAgenteCoordinadorAsync() ... agente que delega
//  [6]   RedA2A.Registrar() ........ da de alta los tres buzones  → RedA2A.cs
//  [7]   Ficha JSON ................ agents_info_interactive.json → Program.cs
//  [8]   FASE 2 — DemostracionA2A.EjecutarAsync()                 → DemostracionA2A.cs
//        [8.1] PASO 1  Usuario ........ → Coordinador
//        [8.2] PASO 2  Coordinador .... → Investigación       (A2A)
//        [8.3] PASO 3  Investigación .. → MCP Microsoft Learn (con aprobación)
//        [8.4] PASO 4  Investigación .. → Coordinador         (A2A)
//        [8.5] PASO 5  Coordinador .... → Ejecutor            (A2A)
//        [8.6] PASO 6  Ejecutor ....... → Coordinador         (A2A)
//        [8.7] PASO 7  Coordinador .... → Usuario             (respuesta final)
//  [9]   Cierre .................... se cierra la sesión MCP      → Program.cs
//
// -----------------------------------------------------------------------------
// CÓMO LEER LOS COMENTARIOS
// -----------------------------------------------------------------------------
//   ⚙️  MFA    → instrucción propia del Microsoft Agent Framework (la materia)
//   🔌 MCP    → relativo al protocolo Model Context Protocol
//   📡 A2A    → relativo a la comunicación entre agentes
//   🏛️  SOLID  → decisión de diseño orientada a objetos (por qué está así)
//   🔧 Infra  → C#/entorno; andamiaje, no forma parte del framework
//
// -----------------------------------------------------------------------------
// REQUISITOS
// -----------------------------------------------------------------------------
//   * `az login` hecho (se autentica con DefaultAzureCredential).
//   * appsettings.Development.json (o variables de entorno) con el endpoint del
//     proyecto de Foundry y el nombre del modelo.
//   * Ejecutar:  dotnet run --project Scenario2.Host
//
// ⚠️  ESTE ESCENARIO LLAMA A MODELOS DE VERDAD: consume cuota y no es determinista.
//
// ✅ Los agentes son EFÍMEROS: viven en memoria mientras dura la ejecución y NO se
//    registran en el proyecto de Azure AI Foundry, así que no se acumulan.
//
// Autor: Fernando Valdés H.  ·  Gemelo en C# de interactive_maf_demo.py
// =============================================================================

using System.Text;
using System.Text.Json;
using Scenario2.Host;
using Scenario2.Host.A2A;

// ─────────────────────────────────────────────────────────────────────────────
// [0] ARRANQUE
// ─────────────────────────────────────────────────────────────────────────────
// 🔧 Infra [0.1] La consola de Windows usa cp1252 y destroza los emojis. Hay que
//    forzar UTF-8 antes de imprimir nada.
Console.OutputEncoding = Encoding.UTF8;

// [1] Punto de entrada: monta la red, la enseña y la desmonta.
// 🔧 Infra Console.IsInputRedirected es el equivalente de `not sys.stdin.isatty()`
//    en Python: detecta que no hay una terminal interactiva detrás.
var consola = new Consola(automatica: Console.IsInputRedirected);
var agentes = new List<IAgenteA2A>();

try
{
    // [2] Configuración validada (falla pronto si falta algo).
    var configuracion = Configuracion.DesdeEntorno();

    // [3] Portada.
    consola.Bienvenida(configuracion);
    consola.Pausa("¿Empezamos? Pulsa Enter…");

    // [4] Fábrica: crea el cliente del proyecto una sola vez.
    var fabrica = new FabricaDeAgentes(configuracion, consola);

    try
    {
        // ── [5] FASE 1 ───────────────────────────────────────────────────────
        consola.Cabecera("FASE 1 — CREACIÓN DE LOS AGENTES");

        var investigacion = await fabrica.CrearAgenteInvestigacionAsync();
        agentes.Add(investigacion);
        consola.Pausa("Pulsa Enter para crear el siguiente agente…");

        var ejecutor = await fabrica.CrearAgenteEjecutorAsync();
        agentes.Add(ejecutor);
        consola.Pausa("Pulsa Enter para crear el siguiente agente…");

        var coordinador = await fabrica.CrearAgenteCoordinadorAsync();
        agentes.Add(coordinador);

        // ── [6] Alta en la red A2A ───────────────────────────────────────────
        var red = new RedA2A(consola);
        foreach (var agente in agentes)
            red.Registrar(agente);

        // ── [7] Ficha en disco ───────────────────────────────────────────────
        var ruta = GuardarFicha(agentes, configuracion);

        consola.Cabecera("RED A2A LISTA");
        consola.Info("Agentes activos:");
        foreach (var agente in agentes)
            consola.Info($"   • {agente.Nombre}");
        consola.Info("");
        consola.Info($"📄 Ficha guardada en: {Path.GetFileName(ruta)}");
        consola.Info("♻️  Son agentes EFÍMEROS: no queda nada registrado en Foundry.");
        consola.Pausa("¿Pasamos a la demostración A2A? Pulsa Enter…");

        // ── [8] FASE 2 ───────────────────────────────────────────────────────
        var correcto = await new DemostracionA2A(red, consola).EjecutarAsync();

        consola.Cabecera(correcto
            ? "🎉 DEMO COMPLETADA CORRECTAMENTE"
            : "⚠️  LA DEMO TERMINÓ CON INCIDENCIAS");
    }
    finally
    {
        // ── [9] Cierre ───────────────────────────────────────────────────────
        // 🔌 MCP Cerrar la sesión con el servidor MCP es obligatorio; si no, queda
        //    una conexión HTTP abierta. El `finally` garantiza que se cierre
        //    incluso si la demo revienta a mitad.
        foreach (var agente in agentes)
            await agente.DisposeAsync();
    }
}
catch (InvalidOperationException error)   // configuración incompleta
{
    Console.WriteLine($"\n\n❌ Configuración: {error.Message}");
    return 1;
}
catch (Exception error)
{
    Console.WriteLine($"\n\n❌ Error inesperado: {error.Message}");
    Console.WriteLine(error);
    return 1;
}

Console.WriteLine();
Console.WriteLine(new string('=', Consola.Ancho));
Console.WriteLine("Gracias por usar la demo del Microsoft Agent Framework.");
Console.WriteLine(new string('=', Consola.Ancho));
return 0;

// =============================================================================
// [7] FICHA JSON — deja constancia en disco de la red que se acaba de montar
// =============================================================================
static string GuardarFicha(IReadOnlyList<IAgenteA2A> agentes, Configuracion configuracion)
{
    // 🔧 Infra La ruta se ancla a la raíz de la solución, no al directorio de
    //    trabajo: así el archivo aparece siempre en el mismo sitio y no enterrado
    //    dentro de bin/Debug/net10.0.
    var destino = Path.Combine(RaizDeLaSolucion(), "agents_info_interactive.json");

    var ficha = new
    {
        generado_en = DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:sszzz"),
        proyecto_foundry = configuracion.EndpointProyecto,
        modelo = configuracion.Modelo,
        servidor_mcp = configuracion.UrlMcp,
        agentes = agentes.Select(a => a.Ficha()).ToList(),
    };

    var json = JsonSerializer.Serialize(ficha, new JsonSerializerOptions
    {
        WriteIndented = true,
        // 🔧 Infra: nombres en snake_case y acentos sin escapar, para que el archivo
        //    salga idéntico al que genera la versión Python.
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    });

    // 🔧 Infra: UTF8Encoding(false) = sin BOM. El Encoding.UTF8 de .NET sí lo escribe,
    //    y ese carácter invisible al principio molesta a muchos lectores de JSON.
    File.WriteAllText(destino, json, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
    return destino;
}

/// <summary>🔧 Infra Sube directorios hasta encontrar el archivo de solución.</summary>
static string RaizDeLaSolucion()
{
    // ⚠️ El SDK de .NET 10 genera el formato nuevo `.slnx`, no el clásico `.sln`.
    var dir = new DirectoryInfo(AppContext.BaseDirectory);
    while (dir is not null && dir.GetFiles("*.sln").Length == 0 && dir.GetFiles("*.slnx").Length == 0)
        dir = dir.Parent;

    return dir?.FullName ?? AppContext.BaseDirectory;
}
