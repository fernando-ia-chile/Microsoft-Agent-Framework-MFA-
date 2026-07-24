using Microsoft.Extensions.Configuration;

namespace Scenario2.Host;

// =============================================================================
// CAPA 1 — CONFIGURACIÓN
// =============================================================================
// 🏛️ SOLID (SRP): una única clase se encarga de leer y validar la configuración.
//    Nadie más consulta appsettings.json ni variables de entorno; el resto del
//    programa recibe un objeto ya validado y no puede arrancar a medio configurar.
//
// 🔧 Infra: equivale al bloque `load_dotenv(...)` + clase `Configuracion` del
//    proyecto Python. Las mismas variables del .env viven aquí en appsettings.json.

/// <summary>Datos de conexión al proyecto de Azure AI Foundry.</summary>
public sealed record Configuracion
{
    /// <summary>URL del servidor MCP si no se indica ninguna en la configuración.</summary>
    public const string UrlMcpPorDefecto = "https://learn.microsoft.com/api/mcp";

    /// <summary>Endpoint completo del PROYECTO de Foundry.</summary>
    public required string EndpointProyecto { get; init; }

    /// <summary>Nombre del modelo desplegado en Foundry.</summary>
    public required string Modelo { get; init; }

    /// <summary>URL del servidor MCP remoto de Microsoft Learn.</summary>
    public required string UrlMcp { get; init; }

    // =========================================================================
    // [2] Lectura y validación
    // =========================================================================
    /// <summary>
    /// Lee la configuración, compone lo que falte y falla pronto si algo no está.
    /// </summary>
    /// <exception cref="InvalidOperationException">Si falta algún dato obligatorio.</exception>
    public static Configuracion DesdeEntorno()
    {
        // [2.1] 🔧 Infra: el orden importa — lo último registrado MANDA.
        //       appsettings.json (ejemplo) → appsettings.Development.json (tus
        //       valores reales, en .gitignore) → variables de entorno.
        IConfigurationRoot raiz = new ConfigurationBuilder()
            .SetBasePath(AppContext.BaseDirectory)
            .AddJsonFile("appsettings.json", optional: false, reloadOnChange: false)
            .AddJsonFile("appsettings.Development.json", optional: true, reloadOnChange: false)
            .AddEnvironmentVariables()
            .Build();

        // [2.2] El endpoint puede venir entero...
        var endpoint = Leer(raiz, "AZURE_AI_PROJECT_ENDPOINT");

        // [2.3] ...o componerse a partir del recurso + el nombre del proyecto.
        if (EsPlaceholderOVacio(endpoint))
        {
            var recurso = Leer(raiz, "AZURE_AI_FOUNDRY_ENDPOINT");
            var proyecto = Leer(raiz, "AZURE_AI_FOUNDRY_PROJECT");
            endpoint = !EsPlaceholderOVacio(recurso) && !EsPlaceholderOVacio(proyecto)
                ? $"{recurso.TrimEnd('/')}/api/projects/{proyecto}"
                : "";
        }

        if (EsPlaceholderOVacio(endpoint))
        {
            throw new InvalidOperationException(
                "Falta AZURE_AI_PROJECT_ENDPOINT (o bien AZURE_AI_FOUNDRY_ENDPOINT + " +
                "AZURE_AI_FOUNDRY_PROJECT).\n" +
                "Ponlo en appsettings.Development.json o como variable de entorno.");
        }

        // [2.4] ⚠️ Aquí AZURE_OPENAI_DEPLOYMENT_NAME nombra al MODELO DE FOUNDRY,
        //       no a un deployment de Azure OpenAI. El nombre de la variable se
        //       conserva por compatibilidad con el .env del ejercicio original.
        var modelo = Leer(raiz, "AZURE_OPENAI_DEPLOYMENT_NAME");
        if (EsPlaceholderOVacio(modelo))
            throw new InvalidOperationException("Falta AZURE_OPENAI_DEPLOYMENT_NAME.");

        // [2.5] 🔌 MCP: la versión Python tiene esta URL como constante del módulo;
        //       aquí además se puede sobrescribir por configuración.
        var urlMcp = Leer(raiz, "MCP_MS_LEARN_SERVER_URL");
        if (EsPlaceholderOVacio(urlMcp)) urlMcp = UrlMcpPorDefecto;

        return new Configuracion
        {
            EndpointProyecto = endpoint,
            Modelo = modelo,
            UrlMcp = urlMcp,
        };
    }

    private static string Leer(IConfiguration raiz, string clave) => raiz[clave] ?? "";

    /// <summary>Detecta valores vacíos o los placeholders `&lt;...&gt;` del archivo de ejemplo.</summary>
    private static bool EsPlaceholderOVacio(string valor) =>
        string.IsNullOrWhiteSpace(valor) || valor.Contains('<') || valor.Contains('>');
}
