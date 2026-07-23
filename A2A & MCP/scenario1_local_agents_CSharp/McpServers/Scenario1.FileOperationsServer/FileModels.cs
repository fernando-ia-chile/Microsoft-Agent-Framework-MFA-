using System.ComponentModel;

namespace Scenario1.FileOperationsServer;

// =============================================================================
// [3] MODELOS DE SALIDA ESTRUCTURADA
// =============================================================================
// 🔌 MCP: con salida estructurada, el servidor no devuelve un texto suelto sino un
//    objeto con esquema. El cliente recibe el JSON Schema junto con la herramienta,
//    así que el modelo sabe QUÉ campos va a recibir antes de llamarla.

/// <summary>Resultado de una operación que modifica un archivo.</summary>
public sealed record ResultadoOperacion(
    [property: Description("Nombre del archivo afectado")] string Archivo,
    [property: Description("Indica si la operación se completó")] bool Exito,
    [property: Description("Descripción legible de lo ocurrido")] string Mensaje,
    [property: Description("Número de caracteres escritos")] int Caracteres = 0);

/// <summary>Una entrada dentro de un listado de directorio.</summary>
public sealed record ArchivoListado(
    [property: Description("Ruta relativa al espacio de trabajo")] string Nombre,
    [property: Description("ARCHIVO o DIRECTORIO")] string Tipo,
    [property: Description("Tamaño en bytes")] long TamanoBytes,
    [property: Description("Fecha de última modificación")] string Modificado);

/// <summary>Resultado de listar un directorio.</summary>
public sealed record ListadoArchivos(
    [property: Description("Directorio consultado")] string Directorio,
    [property: Description("Patrón de búsqueda aplicado")] string Patron,
    [property: Description("Cantidad de coincidencias encontradas")] int Total,
    [property: Description("Entradas encontradas")] IReadOnlyList<ArchivoListado> Archivos);

/// <summary>Información detallada de un archivo.</summary>
public sealed record InfoArchivo(
    [property: Description("Nombre del archivo")] string Nombre,
    [property: Description("ARCHIVO o DIRECTORIO")] string Tipo,
    [property: Description("Tamaño en bytes")] long TamanoBytes,
    [property: Description("Fecha de creación")] string Creado,
    [property: Description("Fecha de última modificación")] string Modificado,
    [property: Description("Fecha de último acceso")] string Accedido,
    [property: Description("Ruta absoluta en el disco")] string RutaAbsoluta);
