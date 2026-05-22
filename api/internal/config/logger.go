package config

import (
	"log"
	"os"
	"strings"
)

// SetupLogger configures logging based on the configuration
func SetupLogger(cfg *Config) {
	// Set log flags for better debugging
	if cfg.IsDevelopment() {
		// In development, show file and line numbers
		log.SetFlags(log.LstdFlags | log.Lshortfile)
	} else {
		// In production, use standard flags
		log.SetFlags(log.LstdFlags)
	}

	// Set log level (note: Go's standard log doesn't support levels natively,
	// but we can at least configure output format and verbosity)
	
	// Set output destination
	switch strings.ToLower(cfg.Logging.Output) {
	case "stdout":
		log.SetOutput(os.Stdout)
	case "stderr":
		log.SetOutput(os.Stderr)
	case "file":
		if cfg.Logging.FilePath != "" {
			file, err := os.OpenFile(cfg.Logging.FilePath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
			if err != nil {
				log.Printf("Failed to open log file %s: %v", cfg.Logging.FilePath, err)
				return
			}
			log.SetOutput(file)
		}
	default:
		log.SetOutput(os.Stdout)
	}

	// Log configuration details in debug mode
	if cfg.IsDevelopment() {
		log.Printf("Logger configured - Level: %s, Format: %s, Output: %s", 
			cfg.Logging.Level, cfg.Logging.Format, cfg.Logging.Output)
		log.Printf("Environment: %s", cfg.Environment)
		log.Printf("Debug mode: %t", cfg.IsDevelopment())
	}
}

// LogError logs an error with context
func LogError(correlationID, component, message string, err error) {
	if correlationID != "" {
		log.Printf("ERROR [%s] [%s]: %s - %v", correlationID, component, message, err)
	} else {
		log.Printf("ERROR [%s]: %s - %v", component, message, err)
	}
}

// LogInfo logs an info message with context
func LogInfo(correlationID, component, message string) {
	if correlationID != "" {
		log.Printf("INFO [%s] [%s]: %s", correlationID, component, message)
	} else {
		log.Printf("INFO [%s]: %s", component, message)
	}
}

// LogDebug logs a debug message (only in development)
func LogDebug(correlationID, component, message string) {
	// Only log debug in development or when level is debug
	if correlationID != "" {
		log.Printf("DEBUG [%s] [%s]: %s", correlationID, component, message)
	} else {
		log.Printf("DEBUG [%s]: %s", component, message)
	}
} 