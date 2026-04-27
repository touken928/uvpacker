from __future__ import annotations

import pytest

from uvpacker.domain.errors import (
    BuildError,
    CacheError,
    ConfigError,
    RuntimeResolveError,
    UvPackError,
)


class TestErrorHierarchy:
    def test_uv_pack_error_is_base(self) -> None:
        assert issubclass(UvPackError, RuntimeError)

    def test_config_error_extends_uv_pack_error(self) -> None:
        assert issubclass(ConfigError, UvPackError)

    def test_cache_error_extends_uv_pack_error(self) -> None:
        assert issubclass(CacheError, UvPackError)

    def test_build_error_extends_uv_pack_error(self) -> None:
        assert issubclass(BuildError, UvPackError)

    def test_runtime_resolve_error_extends_uv_pack_error(self) -> None:
        assert issubclass(RuntimeResolveError, UvPackError)

    def test_config_error_can_be_raised(self) -> None:
        with pytest.raises(ConfigError, match="invalid"):
            raise ConfigError("invalid config")

    def test_cache_error_can_be_raised(self) -> None:
        with pytest.raises(CacheError, match="cache issue"):
            raise CacheError("cache issue")

    def test_build_error_can_be_raised(self) -> None:
        with pytest.raises(BuildError, match="build fail"):
            raise BuildError("build fail")

    def test_runtime_resolve_error_can_be_raised(self) -> None:
        with pytest.raises(RuntimeResolveError, match="resolve fail"):
            raise RuntimeResolveError("resolve fail")

    def test_config_error_is_runtime_error(self) -> None:
        with pytest.raises(RuntimeError):
            raise ConfigError("test")
