// =============================================================================
// Servidor MCP de Operaciones de Archivo - Escenario 1 (C#)
// =============================================================================
// Este servidor publica herramientas de manejo de archivos para los agentes,
// mediante el Model Context Protocol (MCP).
//
// Herramientas publicadas:
// - read_file:   leer el contenido de un archivo
// - write_file:  escribir contenido en un archivo
// - list_files:  listar archivos de un directorio
// - delete_file: borrar un archivo
// - file_info:   obtener información de un archivo
//
// Ejecutar:
//     dotnet run --project McpServers/Scenario1.FileOperationsServer
//
// Normalmente NO se ejecuta a mano: lo lanza el Agente Ejecutor como subproceso
// a través de StdioClientTransport.
//
// -----------------------------------------------------------------------------
// ORDEN DE EJECUCIÓN (los comentarios [n] siguen esta numeración)
// -----------------------------------------------------------------------------
//   [1]      Program.cs   -> construir el host y arrancar el servidor
//   [2]      Workspace    -> anclar el espacio de trabajo aislado
//   [3]      FileModels   -> modelos de salida estructurada
//   [4]      RutaSegura   -> guardián de seguridad, se ejecuta en CADA herramienta
//   [5]-[9]  FileTools    -> las cinco herramientas publicadas por MCP
//
// Convención de los comentarios:
//   🔌 MCP   = instrucción propia del Model Context Protocol (materia de estudio)
//   🔒 Seg.  = control de seguridad
//   🔧 Infra = .NET/entorno, no es del protocolo
// -----------------------------------------------------------------------------

using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Scenario1.FileOperationsServer;

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
//       - WithToolsFromAssembly()    -> descubre por reflexión todas las clases
//         marcadas con [McpServerToolType] y sus métodos [McpServerTool].
builder.Services
    .AddMcpServer(opciones =>
    {
        opciones.ServerInfo = new() { Name = "file-operations-server", Version = "1.0.0" };

        // 🔌 MCP: instrucciones que el servidor anuncia al cliente en el handshake.
        opciones.ServerInstructions =
            "Servidor de operaciones de archivo para agentes. Permite leer, escribir, " +
            "listar, borrar y consultar archivos dentro de un espacio de trabajo aislado. " +
            "Todas las rutas son relativas a ese espacio: no se puede salir de él.";
    })
    .WithStdioServerTransport()
    .WithToolsFromAssembly();

// [1.5] Mensajes informativos a stderr (nunca a stdout, ver [1.2]).
Console.Error.WriteLine("📁 Servidor MCP de Archivos iniciando (transporte: stdio)");
Console.Error.WriteLine("📡 Nombre del servidor: file-operations-server");
Console.Error.WriteLine($"📂 Espacio de trabajo: {Workspace.BaseDir}");
Console.Error.WriteLine("🔧 Herramientas: read_file, write_file, list_files, delete_file, file_info");
Console.Error.WriteLine("🚀 Listo para recibir conexiones de agentes...");

// [1.6] 🔌 MCP: ejecutar el servidor. Se queda escuchando mensajes JSON-RPC por
//       stdin hasta que el cliente cierra la conexión.
await builder.Build().RunAsync();
