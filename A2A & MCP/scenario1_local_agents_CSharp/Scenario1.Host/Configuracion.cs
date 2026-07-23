using Microsoft.Extensions.Configuration;

namespace Scenario1.Host;

/// <summary>
/// Carga de configuración y resolución de rutas de los servidores MCP.
/// </summary>
/// <remarks>
/// 🔧 Infra: equivale al bloque `load_dotenv(...)` del proyecto Python. Aquí las
/// mismas variables viven en appsettings.json, y pueden sobrescribirse con
/// variables de entorno del sistema (útil en CI o en despliegues).
/// </remarks>
internal static class Configuracion
{
    private static readonly IConfigurationRoot Raiz = Construir();

    private static IConfigurationRoot Construir() =>
        new ConfigurationBuilder()
            .SetBasePath(AppContext.BaseDirectory)
            // [1.1] appsettings.json es la fuente principal (equivale al .env).
            //       Se versiona con valores de EJEMPLO.
            .AddJsonFile("appsettings.json", optional: false, reloadOnChange: false)
            // [1.2] Archivo opcional para tus credenciales reales. Está en .gitignore,
            //       así que nunca se sube al repositorio. Es el sitio recomendado.
            .AddJsonFile("appsettings.Development.json", optional: true, reloadOnChange: false)
            // [1.3] Las variables de entorno MANDAN sobre los archivos: lo último que
            //       se registra tiene prioridad. Útil en CI o en despliegues.
            .AddEnvironmentVariables()
            .Build();

    public static string Endpoint => Leer("AZURE_OPENAI_ENDPOINT");
    public static string ApiKey => Leer("AZURE_OPENAI_API_KEY");
    public static string Deployment => Leer("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o");
    public static string ApiVersion => Leer("AZURE_OPENAI_API_VERSION", "preview");
    public static string LogLevel => Leer("LOG_LEVEL", "Warning");

    private static string Leer(string clave, string porDefecto = "") =>
        Raiz[clave] is { Length: > 0 } valor ? valor : porDefecto;

    /// <summary>Devuelve las variables obligatorias que faltan o siguen con el valor de ejemplo.</summary>
    public static IReadOnlyList<string> VariablesFaltantes()
    {
        var faltantes = new List<string>();

        if (string.IsNullOrWhiteSpace(Endpoint) || Endpoint.Contains("TU-RECURSO"))
            faltantes.Add("AZURE_OPENAI_ENDPOINT");
        if (string.IsNullOrWhiteSpace(ApiKey) || ApiKey.Contains("tu-clave"))
            faltantes.Add("AZURE_OPENAI_API_KEY");
        if (string.IsNullOrWhiteSpace(Deployment))
            faltantes.Add("AZURE_OPENAI_DEPLOYMENT_NAME");

        return faltantes;
    }

    // =========================================================================
    // RUTAS DE LOS SERVIDORES MCP
    // =========================================================================
    // 🔌 MCP: cada servidor es un EJECUTABLE aparte. El agente lo lanza como
    //    subproceso, así que necesita la ruta de su DLL compilado.
    //    ⚠️ Se resuelve subiendo hasta encontrar Scenario1.sln, no con rutas
    //    relativas al directorio actual: al lanzarse como subproceso, el
    //    "directorio actual" depende de quién lo lance.

    public static string RaizSolucion { get; } = ResolverRaiz();

    private static string ResolverRaiz()
    {
        // 🔧 Infra: se busca cualquier archivo de solución. Ojo: el SDK de .NET 10
        //    genera el formato nuevo `.slnx`, no el clásico `.sln`.
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null &&
               dir.GetFiles("*.sln").Length == 0 &&
               dir.GetFiles("*.slnx").Length == 0)
        {
            dir = dir.Parent;
        }

        return dir?.FullName ?? AppContext.BaseDirectory;
    }

    /// <summary>Ruta del DLL compilado de un servidor MCP.</summary>
    public static string RutaServidorMcp(string nombreProyecto)
    {
        // 🔧 Infra: se reutiliza la misma configuración (Debug/Release) y el mismo
        //    target framework con los que se compiló este host. AppContext.BaseDirectory
        //    apunta a ".../bin/<Configuración>/<TFM>/".
        var salida = new DirectoryInfo(AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar));
        var tfm = salida.Name;                       // p. ej. net10.0
        var configuracion = salida.Parent?.Name ?? "Debug";  // p. ej. Debug

        var ruta = Path.Combine(
            RaizSolucion, "McpServers", nombreProyecto, "bin", configuracion, tfm, $"{nombreProyecto}.dll");

        if (!File.Exists(ruta))
        {
            throw new FileNotFoundException(
                $"No se encontró el servidor MCP '{nombreProyecto}'.\n" +
                $"Ruta esperada: {ruta}\n" +
                $"Compila la solución primero:  dotnet build");
        }

        return ruta;
    }

    /// <summary>Espacio de trabajo compartido donde el Agente Ejecutor guarda archivos.</summary>
    public static string EspacioDeTrabajo => Path.Combine(RaizSolucion, "agent_workspace");
}
