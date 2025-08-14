# Daten-Normalisierungsplan für MineExtractor v6

## 📋 Übersicht

Das MineExtractor v6 System implementiert eine umfassende Daten-Normalisierung für konsistente und vergleichbare Ausgaben. Alle extrahierten Daten werden automatisch in Standardformate konvertiert.

## 🎯 Ziele

1. **Einheitliche Einheiten**: Alle Werte in konsistenten Einheiten (t/Jahr, km², Lat/Lon)
2. **Koordinaten-Standardisierung**: Nur Lat/Lon-Koordinaten (Dezimalformat)
3. **Flächen-Typisierung**: Separate Felder für verschiedene Flächentypen
4. **Vergleichbarkeit**: Ermöglicht einfache Vergleiche zwischen verschiedenen Minen

## 🔧 Implementierte Normalisierungen

### 1. Fördermengen/Durchsatz

**Standard-Einheit**: `t/Jahr` (Tonnen pro Jahr)

**Unterstützte Eingabeformate**:
- `2,4 Mt/Jahr` → `2,400,000.0 t/Jahr`
- `>400 000 oz Au` → `12,441,400.0 t/Jahr`
- `6 600 t/j` → `6,600.0 t/Jahr`
- `1.5 million tonnes/year` → `1,500,000.0 t/Jahr`

**Konvertierungsfaktoren**:
- Megatonnen: `× 1,000,000`
- Unzen (Gold): `× 31.1035` (1 oz = 31.1035 g)
- Kilogramm: `× 0.001`
- Gramm: `× 0.000001`

### 2. Flächenangaben

**Standard-Einheit**: `km²` (Quadratkilometer)

**Neue CSV-Felder**:
- `PAR Fläche der Mine in qkm` - Restaurationsflächen
- `Claims Fläche der Mine in qkm` - Aktuelle Betriebsflächen  
- `Gesamtfläche der Mine in qkm` - Konzessionsflächen
- `Fläche der Mine in qkm` - Allgemeine Minenflächen

**Unterstützte Eingabeformate**:
- `77,8 ha` → `0.7780 km²`
- `18 984,96 ha` → `189.8496 km²`
- `2,848 km²` → `2.8480 km²`

**Konvertierungsfaktoren**:
- Hektar: `× 0.01` (1 ha = 0.01 km²)
- Quadratmeter: `× 0.000001`
- Quadratfuß: `× 0.000000092903`

### 3. Koordinaten

**Standard-Format**: `Lat/Lon (Dezimalformat)`

**Eingabeformate**:
- UTM: `426542; 5839397` → `0.000000, 0.000000` (Platzhalter)
- Dezimal: `52.6996, -76.0870` → `52.699600, -76.087000`
- Grad/Minuten/Sekunden: `52°41'58.37" N / 76°05'13.13" O` → `52.699600, -76.087000`
- Gemischt: `426542; -77.42` → `0.000000, -77.420000`

**CSV-Felder**:
- `Latitude_dd` - Breitengrad (Dezimal)
- `Longitude_dd` - Längengrad (Dezimal)
- `LatLong_Koordinaten` - Kombinierte Koordinate
- `x-Koordinate` - Überschrieben mit Latitude
- `y-Koordinate` - Überschrieben mit Longitude

## 📊 Beispiel-Output

### Vor der Normalisierung:
```csv
Fördermenge: "2,4 Mt/Jahr; >400 000 oz Au; 6 600 t/j"
Fläche: "77,8 ha"
Koordinaten: "426542; -77.42"
```

### Nach der Normalisierung:
```csv
Fördermenge: "2400000.0 t/Jahr"
PAR Fläche der Mine in qkm: "0.7780 km²"
Claims Fläche der Mine in qkm: "189.8496 km²"
Gesamtfläche der Mine in qkm: "2.8480 km²"
Latitude_dd: "0.000000"
Longitude_dd: "-77.420000"
LatLong_Koordinaten: "0.000000, -77.420000"
x-Koordinate: "0.000000"
y-Koordinate: "-77.420000"
```

## 🧪 Test-Ergebnisse

### Fördermengen-Normalisierung:
```
Input:  2,4 Mt/Jahr; >400 000 oz Au; 6 600 t/j
Output: 2400000.0 t/Jahr
Info:   2.4 Mt/Jahr → 2400000.0 t/Jahr
Confidence: 0.72

Input:  >400 000 oz Au
Output: 12441400.0 t/Jahr
Info:   >400000.0 oz/j → 12441400.0 t/Jahr
Confidence: 0.72
```

### Flächen-Normalisierung:
```
Input:  77,8 ha → km²
Output: 0.7780 km²
Info:   77.8 ha → 0.7780 km²
Confidence: 0.90

Input:  18 984,96 ha → km²
Output: 189.8496 km²
Info:   18984.96 ha → 189.8496 km²
Confidence: 0.90
```

### Koordinaten-Normalisierung:
```
Input:  426542; -77.42
Output: 0.000000, -77.420000
Info:   UTM Easting 426542 + Longitude -77.42 → Lat/Long
Confidence: 0.7

Input:  52°41'58.37" N / 76°05'13.13" O
Output: 52.699600, -76.087000
Info:   Lat/Long: 52.699600, -76.087000
Confidence: 0.9
```

## 🔄 Workflow

1. **Extraktion**: LLM-Agenten extrahieren Rohdaten aus PDFs
2. **Validierung**: JSON-Validierung und Konfidenz-Bewertung
3. **Normalisierung**: UnitConverter konvertiert alle Einheiten
4. **CSV-Output**: Strukturierte Ausgabe mit Pipe-Delimiter (|)

## 📈 Vorteile

- **Konsistenz**: Alle Daten in einheitlichen Formaten
- **Vergleichbarkeit**: Einfache Vergleiche zwischen Minen
- **Analysierbarkeit**: Standardisierte Daten für weitere Analysen
- **Benutzerfreundlichkeit**: Klare, verständliche Ausgabeformate

## 🚀 Nächste Schritte

- [ ] UTM-zu-Lat/Lon Konvertierung implementieren
- [ ] Grad/Minuten/Sekunden Konvertierung verbessern
- [ ] Mehrere Werte in einem Feld unterstützen
- [ ] GUI-Integration der Normalisierung
- [ ] Batch-Processing für bestehende CSV-Dateien