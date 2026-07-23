using System.Text.Json;

namespace Scenario1.WeatherServer;

/// <summary>
/// Acceso a las APIs de Open-Meteo: llamada HTTP común y geocodificación.
/// </summary>
internal static class OpenMeteoService
{
    // =========================================================================
    // [2] CONSTANTES
    // =========================================================================
    // 🌍 API: endpoints de Open-Meteo (no requieren clave).
    private const string GeocodingApi = "https://geocoding-api.open-meteo.com/v1/search";
    public const string WeatherApi = "https://api.open-meteo.com/v1/forecast";
    private const string UserAgent = "MAF-A2A-Weather-Server/1.0";

    // 🔧 Infra: un único HttpClient reutilizado. Crear uno por llamada agota los
    //    sockets del sistema (el clásico "socket exhaustion" de .NET).
    private static readonly HttpClient Http = CrearCliente();

    private static HttpClient CrearCliente()
    {
        var http = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
        http.DefaultRequestHeaders.Add("User-Agent", UserAgent);
        return http;
    }

    // 🌍 API: códigos WMO de estado del tiempo, traducidos.
    // ⚠️ Un solo diccionario para el clima actual y para el pronóstico: si hubiera
    //    dos podrían desincronizarse. Sin emojis: los datos son datos, y del
    //    formato se encarga el agente.
    public static readonly Dictionary<int, string> CodigosTiempo = new()
    {
        [0] = "cielo despejado",
        [1] = "mayormente despejado",
        [2] = "parcialmente nublado",
        [3] = "cubierto",
        [45] = "niebla",
        [48] = "niebla con escarcha",
        [51] = "llovizna ligera",
        [53] = "llovizna",
        [55] = "llovizna intensa",
        [61] = "lluvia ligera",
        [63] = "lluvia",
        [65] = "lluvia intensa",
        [71] = "nevada ligera",
        [73] = "nevada",
        [75] = "nevada intensa",
        [77] = "granos de nieve",
        [80] = "chubascos ligeros",
        [81] = "chubascos",
        [82] = "chubascos fuertes",
        [85] = "chubascos de nieve ligeros",
        [86] = "chubascos de nieve",
        [95] = "tormenta eléctrica",
        [96] = "tormenta con granizo",
    };

    public static string DescribirTiempo(int codigo) =>
        CodigosTiempo.TryGetValue(codigo, out var d) ? d : "desconocido";

    // =========================================================================
    // [4] LLAMADA HTTP COMÚN
    // =========================================================================
    /// <summary>Realiza una petición a las APIs de Open-Meteo.</summary>
    /// <exception cref="HttpRequestException">Si la API no responde correctamente.</exception>
    public static async Task<JsonElement> PedirAsync(
        string url, Dictionary<string, string> parametros, CancellationToken ct = default)
    {
        var query = string.Join("&", parametros.Select(p =>
            $"{Uri.EscapeDataString(p.Key)}={Uri.EscapeDataString(p.Value)}"));

        // [4.1] Los errores se propagan como EXCEPCIÓN. MCP las transporta al cliente
        //       como error de herramienta y el agente puede explicárselas al usuario.
        //       Devolver null obligaría a cada herramienta a inventar un texto de
        //       error indistinguible de un resultado válido.
        using var respuesta = await Http.GetAsync($"{url}?{query}", ct);
        respuesta.EnsureSuccessStatusCode();

        await using var flujo = await respuesta.Content.ReadAsStreamAsync(ct);
        using var doc = await JsonDocument.ParseAsync(flujo, cancellationToken: ct);
        return doc.RootElement.Clone();
    }

    // =========================================================================
    // [5] GEOCODIFICACIÓN — ciudad -> coordenadas (la usan las TRES herramientas)
    // =========================================================================
    /// <summary>Obtiene las coordenadas de una ciudad.</summary>
    /// <exception cref="KeyNotFoundException">Si no se encuentra la ciudad.</exception>
    public static async Task<Ubicacion> GeocodificarAsync(
        string ciudad, string pais = "", CancellationToken ct = default)
    {
        // [5.1] ⚠️ La API de geocodificación de Open-Meteo **NO acepta un parámetro
        //       `country`**: lo ignora en silencio. Enviarlo y creer que filtra hace
        //       que "Tokio, Japón" devuelva Tokio (Dakota del Norte).
        //       Solución: pedir VARIOS candidatos y filtrar aquí.
        // [5.2] language=es permite buscar por el nombre en español ("Tokio",
        //       "Londres") y devuelve los países también en español.
        var datos = await PedirAsync(GeocodingApi, new()
        {
            ["name"] = ciudad,
            ["count"] = "10",
            ["language"] = "es",
            ["format"] = "json",
        }, ct);

        if (!datos.TryGetProperty("results", out var resultados) || resultados.GetArrayLength() == 0)
            throw new KeyNotFoundException($"No se encontró la ubicación '{ciudad}'. Revisa la ortografía.");

        var candidatos = resultados.EnumerateArray().ToList();

        // [5.3] Filtrar por país: se acepta el nombre ("Japón") o el código ISO ("JP"),
        //       sin distinguir mayúsculas.
        if (!string.IsNullOrWhiteSpace(pais))
        {
            var objetivo = pais.Trim();
            var coincidencias = candidatos.Where(r =>
                Texto(r, "country").Equals(objetivo, StringComparison.OrdinalIgnoreCase) ||
                Texto(r, "country_code").Equals(objetivo, StringComparison.OrdinalIgnoreCase)).ToList();

            // Si el país no coincide con ninguno se conserva el mejor resultado global,
            // en vez de fallar: es preferible responder algo a no responder.
            if (coincidencias.Count > 0) candidatos = coincidencias;
        }

        var elegido = candidatos[0];
        var nombre = Texto(elegido, "name");
        var paisNombre = Texto(elegido, "country");
        var region = Texto(elegido, "admin1");

        var nombreCompleto = string.IsNullOrEmpty(region)
            ? $"{nombre}, {paisNombre}"
            : $"{nombre}, {region}, {paisNombre}";

        return new Ubicacion(
            elegido.GetProperty("latitude").GetDouble(),
            elegido.GetProperty("longitude").GetDouble(),
            nombreCompleto);
    }

    // 🔧 Infra: helpers para leer JSON sin reventar cuando falta una propiedad.
    private static string Texto(JsonElement e, string prop) =>
        e.TryGetProperty(prop, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString()! : "";

    public static double Numero(JsonElement e, string prop) =>
        e.TryGetProperty(prop, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetDouble() : 0d;

    public static int Entero(JsonElement e, string prop) => (int)Math.Round(Numero(e, prop));
}
