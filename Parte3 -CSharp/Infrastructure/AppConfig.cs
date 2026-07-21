using Microsoft.Extensions.Configuration;

namespace MFA.CSharp.Part3.Infrastructure;

/// <summary>
/// Carga de configuración. Equivalente C# del <c>load_dotenv('.env03')</c> de Python.
///
/// <para>
/// Las demos 16-20 NO usan ningún LLM: son cálculo local puro y funcionan aunque
/// el archivo tenga valores de marcador. Solo el ejemplo 21 necesita credenciales
/// reales (sección "AzureAI").
/// </para>
/// </summary>
internal static class AppConfig
{
    private static IConfiguration? s_cached;

    /// <summary>Carga (y cachea) appsettings03.json desde el directorio de salida.</summary>
    public static IConfiguration Load(string fileName = "appsettings03.json")
    {
        if (s_cached is not null) return s_cached;

        string path = Path.Combine(AppContext.BaseDirectory, fileName);
        if (!File.Exists(path))
        {
            throw new FileNotFoundException(
                $"No se encontró '{fileName}'. Asegúrate de que exista y de que el .csproj lo copie a la salida.");
        }

        s_cached = new ConfigurationBuilder()
            .AddJsonFile(path, optional: false, reloadOnChange: false)
            .Build();

        return s_cached;
    }

    /// <summary>
    /// Obtiene un valor obligatorio; falla con un mensaje claro si falta o si
    /// sigue siendo un marcador de posición del tipo &lt;recurso&gt;.
    /// </summary>
    public static string Require(this IConfiguration config, string key)
    {
        string? value = config[key];
        if (string.IsNullOrWhiteSpace(value) || value.StartsWith('<'))
        {
            throw new InvalidOperationException(
                $"Falta configurar '{key}' en appsettings03.json (o sigue con el valor de marcador).");
        }
        return value;
    }

    /// <summary>Devuelve el valor si está configurado de verdad, o null si falta o es un marcador.</summary>
    public static string? GetOptional(this IConfiguration config, string key)
    {
        string? value = config[key];
        return string.IsNullOrWhiteSpace(value) || value.StartsWith('<') ? null : value;
    }
}
