// =============================================================================
// Servidor MCP de Clima - Escenario 1 (C#)
// =============================================================================
// Este servidor publica herramientas meteorológicas para los agentes,
// mediante el Model Context Protocol (MCP).
//
// Herramientas publicadas:
// - get_weather:  clima actual de una ciudad (mundial)
// - get_forecast: pronóstico de varios días (mundial)
// - get_alerts:   avisos meteorológicos derivados de las condiciones actuales
//
// Usa la API de Open-Meteo (gratuita, sin clave): https://open-meteo.com/
//
// Ejecutar:
//     dotnet run --project McpServers/Scenario1.WeatherServer
//
// Normalmente NO se ejecuta a mano: lo lanza el Agente de Investigación como
// subproceso a través de StdioClientTransport.
//
// -----------------------------------------------------------------------------
// ORDEN DE EJECUCIÓN (los comentarios [n] siguen esta numeración)
// -----------------------------------------------------------------------------
//   [1]      Program.cs        -> construir el host y arrancar el servidor
//   [2]      OpenMeteoService  -> constantes: endpoints, códigos WMO
//   [3]      WeatherModels     -> modelos de salida estructurada
//   [4]      PedirAsync        -> llamada HTTP común
//   [5]      GeocodificarAsync -> ciudad -> coordenadas (la usan las TRES tools)
//   [6]-[8]  WeatherTools      -> las tres herramientas publicadas por MCP
//
// Convención de los comentarios:
//   🔌 MCP   = instrucción propia del Model Context Protocol (materia de estudio)
//   🌍 API   = relativo a la API externa de Open-Meteo
//   🔧 Infra = .NET/entorno, no es del protocolo
// -----------------------------------------------------------------------------

using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// [1.1] 🔧 Infra: forzar UTF-8 en la salida. La consola de Windows usa cp1252
//       y rompería los emojis de los mensajes informativos.
Console.OutputEncoding = System.Text.Encoding.UTF8;

var builder = Host.CreateApplicationBuilder(args);

// [1.2] 🚨 EN TRANSPORTE STDIO, **STDOUT ES EL CANAL JSON-RPC**.
//       Cualquier escritura a stdout corrompe el protocolo y el cliente corta con
//       un error de conexión. Por eso TODO el logging se redirige a stderr.
//       Es la trampa número uno al escribir servidores MCP.
builder.Logging.AddConsole(opciones =>
{
    opciones.LogToStandardErrorThreshold = LogLevel.Trace;
});

// [1.3] 🔧 Infra: bajar el nivel de log. Al correr como subproceso, el stderr del
//       servidor se mezcla con la interfaz del agente y taparía la demostración.
builder.Logging.SetMinimumLevel(LogLevel.Warning);

// [1.4] 🔌 MCP: registrar el servidor.
//       - WithStdioServerTransport() -> transporte por entrada/salida estándar,
//         el que se usa cuando el servidor es un subproceso del agente.
//         (Existen también transportes HTTP para servidores remotos.)
//       - WithToolsFromAssembly()    -> descubre por reflexión todas las clases
//         marcadas con [McpServerToolType] y sus métodos [McpServerTool].
builder.Services
    .AddMcpServer(opciones =>
    {
        opciones.ServerInfo = new() { Name = "weather-server", Version = "1.0.0" };

        // 🔌 MCP: son las instrucciones que el servidor anuncia al cliente durante
        //    el handshake: le explican al agente para qué sirve este servidor en
        //    conjunto, más allá de cada herramienta suelta.
        opciones.ServerInstructions =
            "Servidor meteorológico para agentes. Proporciona clima actual, pronóstico " +
            "y avisos de cualquier ciudad del mundo usando la API de Open-Meteo. " +
            "Acepta nombres de ciudad en español o en inglés; indicar el país mejora " +
            "la precisión cuando el nombre se repite en varios lugares.";
    })
    .WithStdioServerTransport()
    .WithToolsFromAssembly();

// [1.5] Mensajes informativos a stderr (nunca a stdout, ver [1.2]).
Console.Error.WriteLine("🌤️  Servidor MCP de Clima iniciando (transporte: stdio)");
Console.Error.WriteLine("📡 Nombre del servidor: weather-server");
Console.Error.WriteLine("🔧 Herramientas: get_weather, get_forecast, get_alerts");
Console.Error.WriteLine("🌍 Fuente de datos: API de Open-Meteo (sin clave)");
Console.Error.WriteLine("🚀 Listo para recibir conexiones de agentes...");

// [1.6] 🔌 MCP: ejecutar el servidor. Se queda escuchando mensajes JSON-RPC por
//       stdin hasta que el cliente cierra la conexión.
await builder.Build().RunAsync();
