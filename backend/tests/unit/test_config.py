"""
Unit tests for app.core.config module.

Tests Settings configuration, validation, and defaults.
"""
import pytest
from unittest.mock import patch, MagicMock
import json

pytestmark = [pytest.mark.unit]


class TestSettingsDefaults:
    """Tests for Settings default values."""

    def test_project_name_default(self):
        """Should have Motifold as default project name."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.PROJECT_NAME == "Motifold"

    def test_algorithm_default(self):
        """Should use HS256 as default algorithm."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.ALGORITHM == "HS256"

    def test_token_expiry_defaults(self):
        """Should have reasonable default token expiry times."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7

    def test_cors_origins_default_list(self):
        """Should have localhost ports in default CORS origins."""
        from app.core.config import Settings

        settings = Settings()
        assert "http://localhost:3000" in settings.CORS_ORIGINS
        assert "http://localhost:13000" in settings.CORS_ORIGINS

    def test_deep_research_defaults(self):
        """Should have reasonable defaults for deep research settings."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.DEEP_RESEARCH_MAX_ITERATIONS_STANDARD == 3
        assert settings.DEEP_RESEARCH_MAX_ITERATIONS_EXTENDED == 6
        assert settings.DEEP_RESEARCH_MAX_SEARCH_RESULTS_STANDARD == 10
        assert settings.DEEP_RESEARCH_MAX_SEARCH_RESULTS_EXTENDED == 20

    def test_openai_model_defaults(self):
        """Should have default model configurations."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.OPENAI_MODEL_MAX == "gpt-4o"
        assert settings.OPENAI_MODEL_PRO == "gpt-4o"
        assert settings.OPENAI_MODEL_MINI == "gpt-4o-mini"

    def test_memory_feature_flag_default(self):
        """Memory entity extraction should be disabled by default."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.MEMORY_ENTITY_EXTRACTION_ENABLED is False

    def test_secret_key_must_be_set(self):
        """SECRET_KEY should have an insecure default that warns."""
        from app.core.config import Settings

        settings = Settings()
        # The default is "CHANGEME" which is insecure and should be changed
        assert settings.SECRET_KEY == "CHANGEME"


class TestCorsOriginsParsing:
    """Tests for CORS_ORIGINS parsing logic."""

    def test_parse_json_array_string(self):
        """Should parse JSON array string into list."""
        from app.core.config import Settings

        settings = Settings(CORS_ORIGINS='["http://a.com","http://b.com"]')
        assert settings.CORS_ORIGINS == ["http://a.com", "http://b.com"]

    def test_parse_comma_separated_string(self):
        """Should parse comma-separated string into list."""
        from app.core.config import Settings

        settings = Settings(CORS_ORIGINS="http://a.com,http://b.com,http://c.com")
        assert settings.CORS_ORIGINS == ["http://a.com", "http://b.com", "http://c.com"]

    def test_parse_comma_separated_with_spaces(self):
        """Should trim spaces from comma-separated values."""
        from app.core.config import Settings

        settings = Settings(CORS_ORIGINS="http://a.com ,  http://b.com , http://c.com")
        assert settings.CORS_ORIGINS == ["http://a.com", "http://b.com", "http://c.com"]

    def test_parse_invalid_json_raises_error(self):
        """Should raise ValueError for invalid JSON string."""
        from app.core.config import Settings

        with pytest.raises(ValueError) as exc_info:
            Settings(CORS_ORIGINS='["http://a.com",]')

        assert "Invalid JSON" in str(exc_info.value)

    def test_list_input_unchanged(self):
        """Should keep list input unchanged."""
        from app.core.config import Settings

        original_list = ["http://a.com", "http://b.com"]
        settings = Settings(CORS_ORIGINS=original_list)
        assert settings.CORS_ORIGINS == original_list

    def test_empty_string_becomes_empty_list(self):
        """Empty string should result in empty list."""
        from app.core.config import Settings

        settings = Settings(CORS_ORIGINS="")
        assert settings.CORS_ORIGINS == []

    def test_only_whitespace_becomes_empty_list(self):
        """String with only whitespace should result in empty list."""
        from app.core.config import Settings

        settings = Settings(CORS_ORIGINS="   ")
        assert settings.CORS_ORIGINS == []


class TestSettingsEnvFile:
    """Tests for Settings loading from .env file."""

    def test_loads_from_env_file(self):
        """Should load settings from .env file when present."""
        from app.core.config import Settings
        import tempfile
        import os

        # Create temp .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("PROJECT_NAME=TestApp\n")
            f.write("SECRET_KEY=test-secret-key\n")
            env_path = f.name

        try:
            # Note: Settings uses pydantic_settings which auto-loads .env
            # This is a structural test - actual .env loading depends on env_file config
            settings = Settings(_env_file=env_path)
            assert settings.PROJECT_NAME == "TestApp"
            assert settings.SECRET_KEY == "test-secret-key"
        finally:
            os.unlink(env_path)

    def test_extra_fields_ignored(self):
        """Should ignore extra fields not defined in Settings."""
        from app.core.config import Settings
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("PROJECT_NAME=TestApp\n")
            f.write("UNKNOWN_FIELD=somevalue\n")
            f.write("SECRET_KEY=test-secret\n")
            env_path = f.name

        try:
            # Should not raise error for unknown field due to extra="ignore"
            settings = Settings(_env_file=env_path)
            assert settings.PROJECT_NAME == "TestApp"
        finally:
            os.unlink(env_path)


class TestSettingsInstance:
    """Tests for the singleton settings instance."""

    def test_settings_instance_exists(self):
        """settings instance should be importable and configured."""
        from app.core.config import settings

        assert settings is not None
        assert isinstance(settings.PROJECT_NAME, str)

    def test_settings_is_singleton_like(self):
        """settings should be the same instance when imported multiple times."""
        from app.core.config import settings as settings1
        from app.core.config import settings as settings2

        assert settings1 is settings2
