"""Unit tests for quick_validate_versions.py script."""

import pytest
from _script_loader import load_script_module


@pytest.fixture
def validate_module():
    """Load quick_validate_versions script as module."""
    return load_script_module("quick_validate_versions")


@pytest.fixture
def valid_config():
    """Valid test configuration."""
    return {
        "version": "1.0.0",
        "languages": {
            "python": {
                "supported_versions": [
                    {
                        "version": "3.12.0",
                        "tags": ["latest"],
                        "end_of_life": "2028-10",
                    },
                    {
                        "version": "3.11.0",
                        "tags": ["stable"],
                        "end_of_life": "2027-10",
                    },
                ],
                "adapter": {
                    "package": "debugpy",
                    "version": "1.8.0",
                    "min_version": "1.6.0",
                },
            },
        },
    }


class TestValidateConfigFormat:
    """Test validate_config_format function."""

    def test_valid_config_no_errors(self, validate_module, valid_config):
        """Verify valid config passes format validation."""
        errors = validate_module.validate_config_format(valid_config)
        assert len(errors) == 0

    def test_missing_version_key(self, validate_module):
        """Verify error when version key is missing."""
        config: dict[str, dict] = {"languages": {}}
        errors = validate_module.validate_config_format(config)

        assert len(errors) >= 1
        assert any("Missing required key: version" in err for err in errors)

    def test_language_config_not_dict(self, validate_module):
        """Verify error when language config is not a dictionary."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": "not a dict",
            },
        }
        errors = validate_module.validate_config_format(config)

        assert len(errors) >= 1
        assert any("python" in err and "must be a dictionary" in err for err in errors)

    def test_missing_supported_versions(self, validate_module):
        """Verify error when supported_versions is missing."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {},
            },
        }
        errors = validate_module.validate_config_format(config)

        assert len(errors) >= 1
        assert any("python" in err and "supported_versions" in err for err in errors)

    def test_supported_versions_not_list(self, validate_module):
        """Verify error when supported_versions is not a list."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": "not a list",
                },
            },
        }
        errors = validate_module.validate_config_format(config)

        assert len(errors) >= 1
        assert any("must be a list" in err for err in errors)

    def test_version_entry_missing_version_field(self, validate_module):
        """Verify error when version entry missing version field."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"tags": ["latest"]},  # Missing version field
                    ],
                },
            },
        }
        errors = validate_module.validate_config_format(config)

        assert len(errors) >= 1
        assert any("missing version field" in err for err in errors)

    def test_invalid_version_format(self, validate_module):
        """Verify error for invalid version string format."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "not-a-version"},
                    ],
                },
            },
        }
        errors = validate_module.validate_config_format(config)

        assert len(errors) >= 1
        assert any("invalid version format" in err.lower() for err in errors)


class TestValidateVersionConsistency:
    """Test validate_version_consistency function."""

    def test_valid_consistency_no_errors(self, validate_module, valid_config):
        """Verify valid config passes consistency validation."""
        errors = validate_module.validate_version_consistency(valid_config)
        assert len(errors) == 0

    def test_duplicate_versions_detected(self, validate_module):
        """Verify error for duplicate versions."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "3.12.0", "tags": ["latest"]},
                        {"version": "3.12.0", "tags": ["stable"]},
                    ],
                },
            },
        }
        errors = validate_module.validate_version_consistency(config)

        assert len(errors) >= 1
        assert any("duplicate versions" in err for err in errors)
        assert any("3.12.0" in err for err in errors)

    def test_multiple_latest_tags(self, validate_module):
        """Verify error when multiple versions have 'latest' tag."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "3.12.0", "tags": ["latest"]},
                        {"version": "3.11.0", "tags": ["latest"]},
                    ],
                },
            },
        }
        errors = validate_module.validate_version_consistency(config)

        assert len(errors) >= 1
        assert any("multiple 'latest' tags" in err for err in errors)

    def test_no_latest_tag(self, validate_module):
        """Verify error when no version has 'latest' tag."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "3.12.0", "tags": ["stable"]},
                        {"version": "3.11.0", "tags": ["old"]},
                    ],
                },
            },
        }
        errors = validate_module.validate_version_consistency(config)

        assert len(errors) >= 1
        assert any("no 'latest' tag" in err for err in errors)

    def test_latest_not_on_highest_version(self, validate_module):
        """Verify error when 'latest' tag is not on highest version."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "3.12.0", "tags": []},
                        {"version": "3.11.0", "tags": ["latest"]},
                    ],
                },
            },
        }
        errors = validate_module.validate_version_consistency(config)

        assert len(errors) >= 1
        assert any("'latest' tag not on highest version" in err for err in errors)

    def test_empty_supported_versions_no_error(self, validate_module):
        """Verify no error for empty supported_versions (skipped)."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [],
                },
            },
        }
        errors = validate_module.validate_version_consistency(config)
        assert len(errors) == 0


class TestValidateEolDates:
    """Test validate_eol_dates function."""

    def test_valid_eol_dates_no_errors(self, validate_module):
        """Verify valid EOL date formats pass validation."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "3.12.0", "end_of_life": "2028-10-31"},
                        {"version": "3.11.0", "end_of_life": "2027-10"},
                        {"version": "3.10.0", "end_of_life": "2026"},
                    ],
                },
            },
        }
        errors = validate_module.validate_eol_dates(config)
        assert len(errors) == 0

    def test_invalid_eol_date_format(self, validate_module):
        """Verify error for invalid EOL date format."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "3.12.0", "end_of_life": "not-a-date"},
                    ],
                },
            },
        }
        errors = validate_module.validate_eol_dates(config)

        assert len(errors) >= 1
        assert any("invalid EOL date format" in err for err in errors)

    def test_missing_eol_date_no_error(self, validate_module):
        """Verify no error when EOL date is missing (optional field)."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "3.12.0"},  # No end_of_life field
                    ],
                },
            },
        }
        errors = validate_module.validate_eol_dates(config)
        assert len(errors) == 0


class TestValidateAdapterConfigs:
    """Test validate_adapter_configs function."""

    def test_valid_adapter_config_no_errors(self, validate_module, valid_config):
        """Verify valid adapter config passes validation."""
        errors = validate_module.validate_adapter_configs(valid_config)
        assert len(errors) == 0

    def test_missing_package_field(self, validate_module):
        """Verify error when adapter missing package field."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "adapter": {
                        "version": "1.8.0",
                    },
                },
            },
        }
        errors = validate_module.validate_adapter_configs(config)

        assert len(errors) >= 1
        assert any("missing package field" in err for err in errors)

    def test_missing_version_field(self, validate_module):
        """Verify error when adapter missing version field."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "adapter": {
                        "package": "debugpy",
                    },
                },
            },
        }
        errors = validate_module.validate_adapter_configs(config)

        assert len(errors) >= 1
        assert any("missing version field" in err for err in errors)

    def test_invalid_adapter_version_format(self, validate_module):
        """Verify error for invalid adapter version format."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "adapter": {
                        "package": "debugpy",
                        "version": "not-valid",
                    },
                },
            },
        }
        errors = validate_module.validate_adapter_configs(config)

        assert len(errors) >= 1
        assert any("invalid version format" in err for err in errors)

    def test_latest_version_accepted(self, validate_module):
        """Verify 'latest' is accepted as valid version."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "adapter": {
                        "package": "debugpy",
                        "version": "latest",
                    },
                },
            },
        }
        errors = validate_module.validate_adapter_configs(config)
        assert len(errors) == 0

    def test_version_below_minimum(self, validate_module):
        """Verify error when adapter version is below minimum."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "adapter": {
                        "package": "debugpy",
                        "version": "1.5.0",
                        "min_version": "1.6.0",
                    },
                },
            },
        }
        errors = validate_module.validate_adapter_configs(config)

        assert len(errors) >= 1
        assert any("below minimum" in err for err in errors)

    def test_invalid_min_version_format(self, validate_module):
        """Verify error for invalid min_version format."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "adapter": {
                        "package": "debugpy",
                        "version": "1.8.0",
                        "min_version": "not-valid",
                    },
                },
            },
        }
        errors = validate_module.validate_adapter_configs(config)

        assert len(errors) >= 1
        assert any("invalid min_version format" in err for err in errors)

    def test_no_adapter_config_no_error(self, validate_module):
        """Verify no error when adapter config is missing (optional)."""
        config = {
            "version": "1.0.0",
            "languages": {
                "python": {
                    "supported_versions": [
                        {"version": "3.12.0", "tags": ["latest"]},
                    ],
                },
            },
        }
        errors = validate_module.validate_adapter_configs(config)
        assert len(errors) == 0
