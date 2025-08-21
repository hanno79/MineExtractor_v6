# ... existing code ...

def get_config(config_file: str = "default.json") -> Dict[str, Any]:
    """Lädt die Konfiguration aus der JSON-Datei"""
    # Prüfe ob es ein absoluter Pfad ist
    if os.path.isabs(config_file) or os.path.exists(config_file):
        config_path = config_file
    else:
        # Relativer Pfad - suche im config Verzeichnis
        config_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(config_dir, config_file)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Löse Umgebungsvariablen auf
        config = _resolve_environment_variables(config)
        
        return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # Fallback auf Standard-Konfiguration
        print(f"Warnung: Konfigurationsdatei {config_file} nicht gefunden oder ungültig: {e}")
        return {
            "pdf_directory": "pdfs",
            "txt_directory": "txt_files",
            "template_file": "template.csv",
            "output_file": "output.csv",
            "deepseek_api_key": "",
            "gemini_api_key": "",
            "openrouter_api_key": "",
            "max_files": 10,
            "primary_api": "DeepSeek",
            "backup_api": "Gemini",
            "use_openrouter_for_all": False,
            "use_chunks": True,
            "hardware_optimization": True,
            "timeout": 120,
            "retries": 2,
            "api_call_delay": 1.0,
            "vision_api_priority": "Gemini",
            "column_separator": ";",
            "cell_separator": "; ",
            "csv": {
                "separators": {
                    "column": ";",
                    "cell": "; ",
                    "line_terminator": "\n"
                },
                "quoting": {
                    "quote_char": "\"",
                    "escape_char": "\"",
                    "double_quote": True
                },
                "encoding": "utf-8"
            },
            "extraction_strategy": "hybrid",
            "max_retries": 3,
            "backoff_base_seconds": 1,
            "backoff_max_seconds": 60,
            "backoff_jitter": 0.1
        }

def _resolve_environment_variables(config: Dict[str, Any]) -> Dict[str, Any]:
    """Löst Umgebungsvariablen in der Konfiguration auf"""
    import os
    
    def resolve_value(value):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]  # Entferne ${ und }
            return os.getenv(env_var, value)
        return value
    
    def resolve_dict(d):
        if isinstance(d, dict):
            return {k: resolve_value(v) if isinstance(v, str) else resolve_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [resolve_dict(item) for item in d]
        else:
            return d
    
    return resolve_dict(config)

# ... existing code ...

# Erstelle Instanzen für Legacy-Kompatibilität
_processing_limits = ProcessingLimits()
_validation_limits = ValidationLimits()
_hardware_limits = HardwareLimits()
_api_limits = APILimits()
_gui_limits = GUILimits()

# CSV-Konfiguration
DEFAULT_CSV_DELIMITER = ','
DEFAULT_CSV_ENCODING = 'utf-8'
DEFAULT_CELL_SEPARATOR = ';'
AUTO_DEDUPLICATE_ON_SAVE = True
DEDUPLICATE_SOURCE_SEPARATOR = ' | '
DEFAULT_API_TIMEOUT = _api_limits.DEFAULT_TIMEOUT
DEFAULT_MAX_RETRIES = _api_limits.DEFAULT_MAX_RETRIES
API_RATE_LIMIT_DELAY = _api_limits.RATE_LIMIT_DELAY
DEFAULT_MAX_CHUNK_WORKERS = _hardware_limits.DEFAULT_MAX_CHUNK_WORKERS
DEFAULT_MIN_CHUNK_WORKERS = _hardware_limits.DEFAULT_MIN_CHUNK_WORKERS
PROCESSING_MAX_CHUNK_SIZE = _processing_limits.MAX_CHUNK_SIZE
PROCESSING_LARGE_FILE_CHUNK_SIZE = _processing_limits.LARGE_FILE_CHUNK_SIZE
MAX_CHUNKS_PER_FILE = _processing_limits.MAX_CHUNKS_PER_FILE
MIN_CHUNK_WORKERS = _hardware_limits.MIN_CHUNK_WORKERS
MAX_CHUNK_WORKERS = _hardware_limits.MAX_CHUNK_WORKERS

# Legacy-Kompatibilität
SUPPORTED_FILE_EXTENSIONS = _processing_limits.SUPPORTED_FILE_EXTENSIONS