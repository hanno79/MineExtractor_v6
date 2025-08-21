@dataclass
class ExtractionConfig:
    """Konfigurationsdatenmodell für Extraktion"""
    max_files: Optional[int] = None
    process_all_files: bool = True
    pdf_directory: str = ""
    txt_directory: str = ""
    template_file: str = ""
    output_file: str = ""
    
    # API-Konfiguration
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    gemini_model: str = "gemini-1.5-flash-latest"
    primary_api: str = "DeepSeek"
    backup_api: str = "Gemini"
    use_openrouter_for_all: bool = False
    model_order: Optional[List[str]] = None
    extraction_strategy: str = "hybrid"
    
    # Prompts-Konfiguration
    prompts: Optional[Dict[str, str]] = None
    
    # Verarbeitungsoptionen
    max_retries: int = 3
    timeout: int = 180
    timeout_seconds: int = 180  # Alias für Kompatibilität
    async_chunks_enabled: bool = True
    hardware_optimization_enabled: bool = True
    enhanced_error_recovery: bool = True
    auto_retry_on_error: bool = True
    
    # CSV-Optionen
    column_separator: str = "|"
    cell_separator: str = "; "
    # Exponential Backoff Konfiguration
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 30.0
    backoff_jitter: float = 0.1
    # Legacy-Kompatibilität
    api_call_delay_seconds: float = 0.5
    vision_model_priority: str = "Gemini" # Neu hinzugefügt
    max_workers: Optional[int] = None # Neu hinzugefügt
    
    def __post_init__(self):
        """Initialisiert Standard-Prompts falls nicht gesetzt"""
        if self.prompts is None:
            self.prompts = {
                "extraction": "Extrahiere alle verfügbaren Informationen über Minen aus dem folgenden Text. Fokussiere dich auf: Minenname, Standort, Produktion, Kosten, Datum, und andere relevante Details.",
                "validation": "Validiere und korrigiere die extrahierten Minendaten. Stelle sicher, dass alle Werte korrekt formatiert und vollständig sind.",
                "deduplication": "Identifiziere und entferne doppelte Einträge basierend auf Minenname und Standort.",
                "json_extraction": "Analysiere den folgenden Text und extrahiere alle Informationen über Minen. Gib die Informationen in einem strukturierten Format zurück. Fokussiere dich auf: Minenname, Standort, Produktion, Kosten, Datum und andere relevante Details.\n\nText: {content}",
                "mine_extraction": "Analysiere den folgenden Text und extrahiere alle Informationen über Minen. Fokussiere dich auf Minenname, Standort, Produktion, Kosten und Datum.",
                "data_extraction": "Extrahiere strukturierte Daten über Minen aus dem folgenden Text. Gib die Informationen in einem klaren, strukturierten Format zurück."
            }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ExtractionConfig':
        """Erstellt ExtractionConfig aus Dictionary"""
        # Bestimme use_openrouter_for_all basierend auf API-Key
        openrouter_api_key = config_dict.get('openrouter_api_key', '')
        use_openrouter_for_all = config_dict.get('use_openrouter_for_all', bool(openrouter_api_key))
        
        # Standard-Modellliste für OpenRouter
        model_order = config_dict.get('model_order')
        if not model_order and openrouter_api_key:
            model_order = [
                "openai/gpt-4o-mini",
                "anthropic/claude-3-haiku",
                "meta-llama/llama-3.1-8b-instruct",
                "google/gemini-flash-1.5"
            ]
        
        return cls(
            max_files=config_dict.get('max_files'),
            process_all_files=config_dict.get('process_all_files', True),
            pdf_directory=config_dict.get('pdf_directory', ''),
            txt_directory=config_dict.get('txt_directory', ''),
            template_file=config_dict.get('template_file', ''),
            output_file=config_dict.get('output_file', ''),
            deepseek_api_key=config_dict.get('deepseek_api_key', ''),
            gemini_api_key=config_dict.get('gemini_api_key', ''),
            openrouter_api_key=openrouter_api_key,
            deepseek_model=config_dict.get('deepseek_model', 'deepseek-chat'),
            gemini_model=config_dict.get('gemini_model', 'gemini-1.5-flash-latest'),
            primary_api=config_dict.get('primary_api', 'DeepSeek'),
            backup_api=config_dict.get('backup_api', 'Gemini'),
            use_openrouter_for_all=use_openrouter_for_all,
            model_order=model_order,
            extraction_strategy=config_dict.get('extraction_strategy', 'hybrid'),
            prompts=config_dict.get('prompts'),
            max_retries=config_dict.get('max_retries', 3),
            timeout=config_dict.get('timeout', 180),
            timeout_seconds=config_dict.get('timeout_seconds', 180),
            async_chunks_enabled=config_dict.get('async_chunks_enabled', True),
            hardware_optimization_enabled=config_dict.get('hardware_optimization_enabled', True),
            enhanced_error_recovery=config_dict.get('enhanced_error_recovery', True),
            auto_retry_on_error=config_dict.get('auto_retry_on_error', True),
            column_separator=config_dict.get('column_separator', '|'),
            cell_separator=config_dict.get('cell_separator', '; '),
            backoff_base_seconds=config_dict.get('backoff_base_seconds', 0.5),
            backoff_max_seconds=config_dict.get('backoff_max_seconds', 30.0),
            backoff_jitter=config_dict.get('backoff_jitter', 0.1),
            api_call_delay_seconds=config_dict.get('api_call_delay_seconds', 0.5),
            vision_model_priority=config_dict.get('vision_model_priority', 'Gemini'),
            max_workers=config_dict.get('max_workers')
        )