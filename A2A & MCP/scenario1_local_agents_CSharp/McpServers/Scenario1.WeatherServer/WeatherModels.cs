using System.ComponentModel;

namespace Scenario1.WeatherServer;

// =============================================================================
// [3] MODELOS DE SALIDA ESTRUCTURADA
// =============================================================================
// 🔌 MCP: con salida estructurada, el servidor no devuelve un texto suelto sino un
//    objeto con esquema. El cliente recibe el JSON Schema junto con la herramienta,
//    así que el modelo sabe QUÉ campos va a recibir antes de llamarla, y puede
//    redactar el informe en el idioma y el formato que quiera.
//
// 🔧 Infra: en C# se usan `record` con `[Description]` en cada propiedad. El SDK
//    genera el esquema a partir de esos metadatos, igual que Pydantic en Python.

/// <summary>Condiciones meteorológicas actuales de una ubicación.</summary>
public sealed record ClimaActual(
    [property: Description("Nombre completo de la ubicación encontrada")] string Ubicacion,
    [property: Description("Hora local de la medición")] string HoraLocal,
    [property: Description("Temperatura en grados Celsius")] double TemperaturaC,
    [property: Description("Sensación térmica en grados Celsius")] double SensacionTermicaC,
    [property: Description("Descripción del estado del tiempo")] string Condicion,
    [property: Description("Humedad relativa en porcentaje")] int HumedadPct,
    [property: Description("Cobertura de nubes en porcentaje")] int NubosidadPct,
    [property: Description("Velocidad del viento en km/h")] double VientoKmh,
    [property: Description("Dirección del viento en grados")] int VientoDireccionGrados,
    [property: Description("Rachas máximas de viento en km/h")] double RachasKmh,
    [property: Description("Precipitación acumulada en mm")] double PrecipitacionMm);

/// <summary>Pronóstico de un día concreto.</summary>
public sealed record DiaPronostico(
    [property: Description("Fecha del pronóstico (AAAA-MM-DD)")] string Fecha,
    [property: Description("Temperatura mínima prevista")] double TemperaturaMinC,
    [property: Description("Temperatura máxima prevista")] double TemperaturaMaxC,
    [property: Description("Estado del tiempo previsto")] string Condicion,
    [property: Description("Precipitación total prevista en mm")] double PrecipitacionMm,
    [property: Description("Viento máximo previsto en km/h")] double VientoMaxKmh);

/// <summary>Pronóstico de varios días para una ubicación.</summary>
public sealed record Pronostico(
    [property: Description("Nombre completo de la ubicación encontrada")] string Ubicacion,
    [property: Description("Cantidad de días incluidos")] int Dias,
    [property: Description("Pronóstico día a día")] IReadOnlyList<DiaPronostico> Detalle);

/// <summary>Avisos derivados de las condiciones actuales.</summary>
public sealed record AvisosMeteorologicos(
    [property: Description("Nombre completo de la ubicación encontrada")] string Ubicacion,
    [property: Description("True si se detectó alguna condición adversa")] bool HayAvisos,
    [property: Description("Lista de avisos detectados")] IReadOnlyList<string> Avisos);

/// <summary>Resultado interno de la geocodificación (no se publica por MCP).</summary>
internal sealed record Ubicacion(double Latitud, double Longitud, string NombreCompleto);
