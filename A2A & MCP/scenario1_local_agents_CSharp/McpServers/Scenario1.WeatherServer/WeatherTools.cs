using System.ComponentModel;
using System.Text.Json;
using ModelContextProtocol.Server;

namespace Scenario1.WeatherServer;

/// <summary>
/// Las tres herramientas que este servidor publica por MCP.
/// </summary>
// 🔌 MCP: [McpServerToolType] marca la clase para que el SDK descubra sus
//    herramientas automáticamente al arrancar (WithToolsFromAssembly en Program.cs).
[McpServerToolType]
public static class WeatherTools
{
    // 🌍 API: umbrales que disparan un aviso. Como constantes con nombre se entienden
    //    y se ajustan; escritos a mano dentro del método serían números mágicos.
    private const double UmbralRachasFuertesKmh = 60;
    private const double UmbralVientoFuerteKmh = 40;
    private const double UmbralLluviaIntensaMm = 20;

    // 🌍 API: rango admitido por Open-Meteo para el pronóstico.
    private const int DiasMin = 1;
    private const int DiasMax = 16;

    // =========================================================================
    // [6] HERRAMIENTA MCP: clima actual
    // =========================================================================
    // 🔌 MCP: las propiedades del atributo son PISTAS DE COMPORTAMIENTO para el
    //    cliente. No cambian lo que hace el método: describen qué efectos tiene.
    //      ReadOnly    -> no modifica nada
    //      Destructive -> puede destruir datos
    //      Idempotent  -> repetirla no provoca efectos adicionales
    //      OpenWorld   -> toca sistemas externos (internet, etc.)
    //    ⚠️ Aquí OpenWorld = true, al contrario que en el servidor de archivos:
    //    estas herramientas consultan un sistema EXTERNO (Open-Meteo), pueden fallar
    //    por red y su resultado cambia con el tiempo aunque los argumentos sean iguales.
    // 🔌 MCP: UseStructuredContent = true activa la salida estructurada; sin él, el
    //    resultado viajaría serializado como texto plano.
    [McpServerTool(
        Name = "get_weather",
        Title = "Clima actual",
        ReadOnly = true,
        Idempotent = true,
        OpenWorld = true,
        UseStructuredContent = true)]
    [Description("Consulta las condiciones meteorológicas actuales de cualquier ciudad del mundo. Indicar el país mejora la precisión.")]
    public static async Task<ClimaActual> GetWeatherAsync(
        [Description("Nombre de la ciudad, p. ej. 'Tokio' o 'Londres'")] string city,
        [Description("País o código ISO, p. ej. 'Japón' o 'JP'")] string country = "",
        CancellationToken ct = default)
    {
        // [6.1] Traducir el nombre de la ciudad a coordenadas (ver [5]).
        var ubicacion = await OpenMeteoService.GeocodificarAsync(city, country, ct);

        // [6.2] 🌍 API: pedir las variables actuales que interesan.
        var datos = await OpenMeteoService.PedirAsync(OpenMeteoService.WeatherApi, new()
        {
            ["latitude"] = ubicacion.Latitud.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["longitude"] = ubicacion.Longitud.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["current"] = "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation," +
                          "rain,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            ["timezone"] = "auto",
        }, ct);

        if (!datos.TryGetProperty("current", out var actual))
            throw new InvalidOperationException($"La API no devolvió datos actuales para {ubicacion.NombreCompleto}");

        // [6.3] 🔌 MCP: devolver el record. El cliente recibe además su esquema, y el
        //       agente redacta el informe con los campos que necesite.
        return new ClimaActual(
            Ubicacion: ubicacion.NombreCompleto,
            HoraLocal: actual.TryGetProperty("time", out var t) ? t.GetString() ?? "" : "",
            TemperaturaC: OpenMeteoService.Numero(actual, "temperature_2m"),
            SensacionTermicaC: OpenMeteoService.Numero(actual, "apparent_temperature"),
            Condicion: OpenMeteoService.DescribirTiempo(OpenMeteoService.Entero(actual, "weather_code")),
            HumedadPct: OpenMeteoService.Entero(actual, "relative_humidity_2m"),
            NubosidadPct: OpenMeteoService.Entero(actual, "cloud_cover"),
            VientoKmh: OpenMeteoService.Numero(actual, "wind_speed_10m"),
            VientoDireccionGrados: OpenMeteoService.Entero(actual, "wind_direction_10m"),
            RachasKmh: OpenMeteoService.Numero(actual, "wind_gusts_10m"),
            PrecipitacionMm: OpenMeteoService.Numero(actual, "precipitation"));
    }

    // =========================================================================
    // [7] HERRAMIENTA MCP: pronóstico
    // =========================================================================
    [McpServerTool(
        Name = "get_forecast",
        Title = "Pronóstico del tiempo",
        ReadOnly = true,
        Idempotent = true,
        OpenWorld = true,
        UseStructuredContent = true)]
    [Description("Consulta el pronóstico de los próximos días de cualquier ciudad del mundo.")]
    public static async Task<Pronostico> GetForecastAsync(
        [Description("Nombre de la ciudad, p. ej. 'Santiago'")] string city,
        [Description("País o código ISO, p. ej. 'Chile' o 'CL'")] string country = "",
        [Description("Número de días a pronosticar (1 a 16)")] int days = 5,
        CancellationToken ct = default)
    {
        var ubicacion = await OpenMeteoService.GeocodificarAsync(city, country, ct);

        // [7.1] Ajustar al rango admitido por la API en vez de fallar.
        days = Math.Clamp(days, DiasMin, DiasMax);

        var datos = await OpenMeteoService.PedirAsync(OpenMeteoService.WeatherApi, new()
        {
            ["latitude"] = ubicacion.Latitud.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["longitude"] = ubicacion.Longitud.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["daily"] = "temperature_2m_max,temperature_2m_min,precipitation_sum," +
                        "wind_speed_10m_max,weather_code",
            ["timezone"] = "auto",
            ["forecast_days"] = days.ToString(),
        }, ct);

        if (!datos.TryGetProperty("daily", out var diario))
            throw new InvalidOperationException($"La API no devolvió pronóstico para {ubicacion.NombreCompleto}");

        // [7.2] Convertir las listas paralelas que devuelve la API en objetos por día.
        var fechas = diario.GetProperty("time").EnumerateArray().ToList();
        var minimas = diario.GetProperty("temperature_2m_min").EnumerateArray().ToList();
        var maximas = diario.GetProperty("temperature_2m_max").EnumerateArray().ToList();
        var lluvias = diario.GetProperty("precipitation_sum").EnumerateArray().ToList();
        var vientos = diario.GetProperty("wind_speed_10m_max").EnumerateArray().ToList();
        var codigos = diario.GetProperty("weather_code").EnumerateArray().ToList();

        var detalle = new List<DiaPronostico>();
        for (var i = 0; i < fechas.Count; i++)
        {
            detalle.Add(new DiaPronostico(
                Fecha: fechas[i].GetString() ?? "",
                TemperaturaMinC: minimas[i].GetDouble(),
                TemperaturaMaxC: maximas[i].GetDouble(),
                Condicion: OpenMeteoService.DescribirTiempo(codigos[i].GetInt32()),
                PrecipitacionMm: lluvias[i].GetDouble(),
                VientoMaxKmh: vientos[i].GetDouble()));
        }

        return new Pronostico(ubicacion.NombreCompleto, detalle.Count, detalle);
    }

    // =========================================================================
    // [8] HERRAMIENTA MCP: avisos meteorológicos
    // =========================================================================
    [McpServerTool(
        Name = "get_alerts",
        Title = "Avisos meteorológicos",
        ReadOnly = true,
        Idempotent = true,
        OpenWorld = true,
        UseStructuredContent = true)]
    [Description("Revisa las condiciones actuales de una ciudad y devuelve avisos por viento fuerte o lluvia intensa. Open-Meteo no publica alertas oficiales: los avisos se derivan de los valores medidos.")]
    public static async Task<AvisosMeteorologicos> GetAlertsAsync(
        [Description("Nombre de la ciudad, p. ej. 'Melbourne'")] string city,
        [Description("País o código ISO, p. ej. 'Australia' o 'AU'")] string country = "",
        CancellationToken ct = default)
    {
        var ubicacion = await OpenMeteoService.GeocodificarAsync(city, country, ct);

        var datos = await OpenMeteoService.PedirAsync(OpenMeteoService.WeatherApi, new()
        {
            ["latitude"] = ubicacion.Latitud.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["longitude"] = ubicacion.Longitud.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["current"] = "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m",
            ["timezone"] = "auto",
        }, ct);

        var actual = datos.TryGetProperty("current", out var c) ? c : default;

        var viento = OpenMeteoService.Numero(actual, "wind_speed_10m");
        var rachas = OpenMeteoService.Numero(actual, "wind_gusts_10m");
        var precipitacion = OpenMeteoService.Numero(actual, "precipitation");

        // [8.1] Comparar contra los umbrales con nombre definidos arriba.
        var avisos = new List<string>();

        if (rachas > UmbralRachasFuertesKmh)
            avisos.Add($"AVISO POR VIENTO FUERTE: rachas de hasta {rachas} km/h");
        else if (viento > UmbralVientoFuerteKmh)
            avisos.Add($"AVISO POR VIENTO: viento sostenido de {viento} km/h");

        if (precipitacion > UmbralLluviaIntensaMm)
            avisos.Add($"AVISO POR LLUVIA INTENSA: {precipitacion} mm de precipitación");

        // [8.2] `HayAvisos` viaja explícito: el agente no tiene que deducir la
        //       ausencia de avisos a partir de una frase en prosa.
        return new AvisosMeteorologicos(ubicacion.NombreCompleto, avisos.Count > 0, avisos);
    }
}
