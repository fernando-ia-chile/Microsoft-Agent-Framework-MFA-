// =============================================================================
// Escenario 1 - Programa Principal de Orquestación (C#)
// =============================================================================
// Demuestra el flujo completo de tres agentes locales que se comunican por A2A
// y usan servidores MCP locales.
//
// Flujo:
// 1. El usuario escribe una petición
// 2. El Agente Coordinador la analiza y planifica el flujo
// 3. El Coordinador delega en el Agente de Investigación (MCP de clima)
// 4. El Coordinador delega en el Agente Ejecutor (MCP de archivos)
// 5. El Coordinador agrega los resultados y responde al usuario
//
// Ejecutar:
//     dotnet run --project Scenario1.Host
//
// -----------------------------------------------------------------------------
// ORDEN DE EJECUCIÓN (los comentarios [n] siguen esta numeración)
// -----------------------------------------------------------------------------
//   [1]  Program.cs                -> punto de entrada, UTF-8 y bienvenida
//   [2]  Orquestador.CrearAsync    -> construye los agentes y abre las sesiones MCP
//   [3]  Bucle de comandos del usuario
//   [4]  EjecutarFlujoCompletoAsync-> delega en el Coordinador
//   [5]  Pantallas de ayuda
//
// Convención de los comentarios:
//   ⚙️ MFA   = instrucción propia del Microsoft Agent Framework
//   📡 A2A   = relativo a la comunicación Agente-a-Agente
//   🔌 MCP   = relativo al Model Context Protocol
//   🔧 Infra = .NET/entorno, no es del framework
// -----------------------------------------------------------------------------

using Scenario1.Host;

// [1.1] 🔧 Infra: forzar UTF-8. La consola de Windows usa cp1252 por defecto y
//       rompería los emojis y los caracteres de las cajas del mensaje A2A.
Console.OutputEncoding = System.Text.Encoding.UTF8;

Console.WriteLine("""

    ╔═══════════════════════════════════════════════════════════╗
    ║   Microsoft Agent Framework - Escenario 1 (C#)            ║
    ║   Agentes locales con comunicación A2A y servidores MCP   ║
    ╚═══════════════════════════════════════════════════════════╝
""");

Console.WriteLine();
Console.WriteLine(new string('=', 70));
Console.WriteLine("🚀 BIENVENIDO AL ESCENARIO 1");
Console.WriteLine("Asistente meteorológico multiagente con comunicación A2A");
Console.WriteLine(new string('=', 70));
Console.WriteLine();
Console.WriteLine("🎮 Iniciando el modo interactivo...");
Console.WriteLine("💡 Verás las estructuras de los mensajes A2A en tiempo real.");

try
{
    await ModoInteractivoAsync();
}
catch (Exception ex)
{
    Console.WriteLine();
    Console.WriteLine($"❌ Error: {ex.Message}");
    Console.WriteLine(ex.StackTrace);
}

Console.WriteLine("""

    ✅ Se ha demostrado:
       • Tres agentes locales (Investigación, Coordinación, Ejecución)
       • Comunicación Agente-a-Agente (A2A)
       • Integración con servidores MCP reales (clima y archivos)
       • Orquestación de flujos multiagente decidida por el modelo
       • Uso de modelos de Azure OpenAI a través de Microsoft Agent Framework

    📚 Siguientes pasos:
       • Modifica las instrucciones de los agentes y observa el cambio
       • Añade herramientas nuevas a los servidores MCP
       • Compara este proyecto con su gemelo en Python

    💡 Consejos:
       • Los archivos generados quedan en agent_workspace/
       • Cambia el modelo en Scenario1.Host/appsettings.json
""");

// =============================================================================
// [3] BUCLE INTERACTIVO
// =============================================================================
static async Task ModoInteractivoAsync()
{
    Console.WriteLine();
    Console.WriteLine(new string('=', 70));
    Console.WriteLine("🎮 MODO INTERACTIVO");
    Console.WriteLine(new string('=', 70));

    // [2] Crear el orquestador y abrir las sesiones MCP.
    //     `await using` garantiza que los subprocesos de los servidores MCP se
    //     cierren aunque el usuario interrumpa la sesión.
    await using var orquestador = await Orquestador.CrearAsync();

    Orquestador.ImprimirDiagramaArquitectura();

    Console.WriteLine();
    Console.WriteLine(new string('=', 70));
    Console.WriteLine("💡 ASISTENTE METEOROLÓGICO MULTIAGENTE");
    Console.WriteLine(new string('=', 70));
    Console.WriteLine();
    Console.WriteLine("🌍 ¡Pregúntame por el clima de cualquier ciudad del mundo!");
    Console.WriteLine();
    Console.WriteLine("📝 Ejemplos:");
    Console.WriteLine("   • ¿Qué tiempo hace en Santiago, Chile?");
    Console.WriteLine("   • Dame el pronóstico de Tokio, Japón");
    Console.WriteLine("   • Clima en Londres y guárdalo en un archivo");
    Console.WriteLine();
    Console.WriteLine("🎯 Comandos rápidos:");
    Console.WriteLine("   • 'ciudades' | 'demo' | 'a2a' | 'a2a-directo' | 'arquitectura'");
    Console.WriteLine("   • 'ayuda' para más información");
    Console.WriteLine("   • 'salir' para terminar");
    Console.WriteLine();

    // [3.1] Bucle principal: leer, clasificar y ejecutar.
    while (true)
    {
        Console.WriteLine();
        Console.WriteLine(new string('-', 70));
        Console.Write("🤔 Tu pregunta: ");

        var entrada = Console.ReadLine()?.Trim();

        // 🔧 Infra: null significa fin de la entrada estándar (por ejemplo, si se
        //    alimenta el programa desde un archivo). Se sale igual que con 'salir'.
        if (entrada is null)
        {
            Console.WriteLine();
            Console.WriteLine("👋 Fin de la entrada. Cerrando...");
            break;
        }

        if (entrada.Length == 0)
        {
            Console.WriteLine("⚠️  Escribe una pregunta.");
            continue;
        }

        var comando = entrada.ToLowerInvariant();

        // [3.2] Comandos de salida.
        if (comando is "salir" or "quit" or "exit" or "q")
        {
            Console.WriteLine();
            Console.WriteLine("👋 ¡Gracias por usar el asistente multiagente!");
            break;
        }

        // [3.3] Comandos de la interfaz (no consumen tokens).
        switch (comando)
        {
            case "demo":
                await EjecutarEjemplosDemoAsync(orquestador);
                continue;

            case "ciudades":
                MostrarCiudadesPopulares();
                continue;

            case "ayuda" or "help":
                MostrarAyuda();
                continue;

            case "a2a":
                MostrarProtocoloA2A();
                continue;

            // [3.4] Demostración A2A sin Coordinador.
            case "a2a-directo" or "a2a-direct":
                await orquestador.DemostrarComunicacionA2AAsync();
                continue;

            case "arquitectura" or "arch":
                Orquestador.ImprimirDiagramaArquitectura();
                continue;
        }

        // [3.5] Cualquier otra cosa es una petición para el flujo multiagente.
        Console.WriteLine();
        Console.WriteLine(new string('=', 70));
        Console.WriteLine("🔄 Procesando tu petición...");
        Console.WriteLine(new string('=', 70));

        try
        {
            await orquestador.EjecutarFlujoCompletoAsync(entrada);
            Console.WriteLine();
            Console.WriteLine("✨ ¡Listo! Haz otra pregunta o escribe 'salir'.");
        }
        catch (Exception ex)
        {
            Console.WriteLine();
            Console.WriteLine($"❌ Error procesando la petición: {ex.Message}");
            Console.WriteLine("💡 Comprueba que has indicado una ciudad.");
        }
    }
}

// =============================================================================
// EJEMPLOS AUTOMÁTICOS
// =============================================================================
static async Task EjecutarEjemplosDemoAsync(Orquestador orquestador)
{
    Console.WriteLine();
    Console.WriteLine(new string('=', 70));
    Console.WriteLine("🎬 EJECUTANDO EJEMPLOS AUTOMÁTICOS");
    Console.WriteLine(new string('=', 70));

    string[] peticiones =
    [
        "¿Qué tiempo hace en Santiago, Chile? Guárdalo en informe_santiago.txt",
        "Dame el pronóstico de 3 días de Madrid, España",
        "¿Hay avisos meteorológicos en Melbourne, Australia?",
    ];

    for (var i = 0; i < peticiones.Length; i++)
    {
        Console.WriteLine();
        Console.WriteLine(new string('#', 70));
        Console.WriteLine($"# EJEMPLO {i + 1}/{peticiones.Length}");
        Console.WriteLine(new string('#', 70));

        await orquestador.EjecutarFlujoCompletoAsync(peticiones[i]);

        if (i < peticiones.Length - 1)
        {
            Console.WriteLine();
            Console.WriteLine("⏸️  Pulsa Enter para pasar al siguiente ejemplo...");
            Console.ReadLine();
        }
    }

    Console.WriteLine();
    Console.WriteLine("✅ Ejemplos completados.");
}

// =============================================================================
// [5] PANTALLAS DE AYUDA DE LA INTERFAZ
// =============================================================================
static void MostrarCiudadesPopulares()
{
    Console.WriteLine();
    Console.WriteLine(new string('=', 70));
    Console.WriteLine("🌆 CIUDADES POPULARES POR REGIÓN");
    Console.WriteLine(new string('=', 70));

    // ✅ El Coordinador extrae la ciudad con el modelo, así que funciona cualquier
    //    ciudad del mundo: no hay una lista fija que limite las opciones.
    var ciudades = new Dictionary<string, string[]>
    {
        ["Sudamérica"] = ["Santiago", "Buenos Aires", "Lima", "Bogotá", "São Paulo"],
        ["Norteamérica"] = ["Ciudad de México", "Nueva York", "Toronto", "Los Ángeles"],
        ["Europa"] = ["Madrid", "Londres", "París", "Berlín", "Roma"],
        ["Asia"] = ["Tokio", "Singapur", "Bangkok", "Seúl", "Bombay"],
        ["Oceanía"] = ["Melbourne", "Sídney", "Auckland", "Brisbane"],
        ["África"] = ["El Cairo", "Lagos", "Ciudad del Cabo", "Nairobi"],
    };

    foreach (var (region, lista) in ciudades)
    {
        Console.WriteLine();
        Console.WriteLine($"🌍 {region}:");
        Console.WriteLine($"   {string.Join(", ", lista)}");
    }

    Console.WriteLine();
    Console.WriteLine("💡 Puedes escribir el nombre en español o en inglés.");
    Console.WriteLine("   Ejemplo: '¿Qué tiempo hace en Tokio, Japón?'");
}

static void MostrarProtocoloA2A()
{
    Console.WriteLine();
    Console.WriteLine(new string('=', 70));
    Console.WriteLine("📡 EL PROTOCOLO AGENTE-A-AGENTE (A2A)");
    Console.WriteLine(new string('=', 70));
    Console.WriteLine("""

🔄 ¿Qué es la comunicación A2A?
   Permite que unos agentes deleguen tareas en otros, compartan
   información y colaboren en flujos de trabajo complejos.

📨 Estructura del mensaje A2A (record MensajeA2A):

   new MensajeA2A
   {
       Emisor       = "coordinator-agent",   // quién envía
       Destinatario = "research-agent",      // quién recibe
       Tipo         = "research_request",    // tipo de petición
       Datos        = new()                  // carga útil
       {
           ["task"]    = "weather_lookup",
           ["city"]    = "Tokio",
           ["country"] = "Japón",
       },
   }

📬 Estructura de la respuesta A2A (record RespuestaA2A):

   new RespuestaA2A
   {
       AgenteId  = "research-agent",   // quién responde
       Estado    = "success",          // success | error | active
       Tarea     = "weather_lookup",
       Contenido = "...",              // el resultado real
       Metadatos = { ["fuente"] = "..." },
   }

🎯 Tipos de mensaje admitidos:
   • research_request   - pedir información (Agente de Investigación)
   • execution_request  - pedir una acción  (Agente Ejecutor)
   • workflow_request   - delegar un flujo completo (Coordinador)
   • ping               - comprobación de salud (los tres)

🔑 La clave: los tres agentes implementan IAgenteA2A, el mismo interfaz.
   Por eso son intercambiables como destinos, y el Coordinador puede
   delegar sin saber nada de su implementación interna.

🔍 Cómo verlo en vivo:
   • Haz una pregunta normal: verás las cajas del mensaje A2A.
   • Escribe 'a2a-directo' para enviar mensajes sin pasar por el
     Coordinador, es decir, sin ningún LLM decidiendo por el camino.
""");
}

static void MostrarAyuda()
{
    Console.WriteLine();
    Console.WriteLine(new string('=', 70));
    Console.WriteLine("❓ AYUDA - CÓMO USAR EL ASISTENTE");
    Console.WriteLine(new string('=', 70));
    Console.WriteLine("""

📖 Qué puedes pedir:
   • Clima actual:  '¿Qué tiempo hace en Santiago?'
   • Pronóstico:    'Dame el pronóstico de 5 días de Lima'
   • Avisos:        '¿Hay avisos meteorológicos en Melbourne?'
   • Guardar:       '...y guárdalo en un archivo'

🎯 Cómo formular la petición:
   • Indica la ciudad (obligatorio)
   • Añade el país para mayor precisión (recomendado)
   • Menciona 'guardar' o 'archivo' para generar un informe

✅ Buenos ejemplos:
   ✓ 'Clima en Valparaíso, Chile'
   ✓ 'Pronóstico de Tokio y guárdalo en un archivo'
   ✓ '¿Qué temperatura hace en Londres?'

❌ Qué no va a funcionar:
   ✗ 'Clima' (no indicas ciudad)
   ✗ 'Cuéntame un chiste' (no es meteorológico)

🔧 Comandos especiales:
   • 'ciudades'    - ver ciudades de ejemplo
   • 'demo'        - ejecutar ejemplos automáticos
   • 'a2a'         - explicación del protocolo A2A
   • 'a2a-directo' - mensajes A2A sin pasar por el Coordinador
   • 'arquitectura'- ver el diagrama del escenario
   • 'salir'       - terminar la sesión
""");
}
