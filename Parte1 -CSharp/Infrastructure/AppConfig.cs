using Microsoft.Extensions.Configuration;

namespace MFA.CSharp.Infrastructure;

/// <summary>
/// Carga de configuración por demo. Cada ejemplo usa su propio archivo
/// appsettings0N.json (equivalente a los .env0N del proyecto de Python).
/// También lee variables de entorno como respaldo/override.
/// </summary>
internal static class AppConfig
{
    public static IConfiguration Load(string fileName)
    {
        string path = Path.Combine(AppContext.BaseDirectory, fileName);
        if (!File.Exists(path))
        {
            throw new FileNotFoundException(
                $"No se encontró '{fileName}'. Asegúrate de que exista y de que el .csproj lo copie a la salida.");
        }

        return new ConfigurationBuilder()
            .AddJsonFile(path, optional: false, reloadOnChange: false)
            .Build();
    }

    /// <summary>Obtiene un valor obligatorio; falla claro si falta o sigue siendo un placeholder.</summary>
    public static string Require(this IConfiguration config, string key)
    {
        string? value = config[key];
        if (string.IsNullOrWhiteSpace(value) || value.StartsWith('<'))
        {
            throw new InvalidOperationException(
                $"Falta configurar '{key}' en el appsettings correspondiente (o sigue con el valor placeholder).");
        }
        return value;
    }

    /// <summary>Obtiene un valor opcional (puede ser null o placeholder).</summary>
    public static string? Optional(this IConfiguration config, string key)
    {
        string? value = config[key];
        return string.IsNullOrWhiteSpace(value) || value.StartsWith('<') ? null : value;
    }
}
