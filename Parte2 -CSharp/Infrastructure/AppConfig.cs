using Microsoft.Extensions.Configuration;

namespace MFA.CSharp.Part2.Infrastructure;

/// <summary>
/// Carga de configuración. Todos los ejemplos de la Parte 2 usan Azure OpenAI
/// directo, así que comparten un único appsettings03.json (equivalente al .env03
/// del proyecto de Python).
/// </summary>
internal static class AppConfig
{
    public static IConfiguration Load(string fileName = "appsettings03.json")
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
                $"Falta configurar '{key}' en appsettings03.json (o sigue con el valor placeholder).");
        }
        return value;
    }
}
