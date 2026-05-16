from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from incognito.core.exceptions import DetectionError


def test_load_model_calls_from_pretrained_with_correct_model_name() -> None:
    from incognito.core import config
    from incognito.gliner import loader

    fake_model = MagicMock()
    with (
        patch.object(loader, "_model", None),
        patch("incognito.gliner.loader.GLiNER.from_pretrained", return_value=fake_model) as mock_fp,
    ):
        result = loader.load_model()

    mock_fp.assert_called_once_with(config.GLINER_MODEL)
    assert result is fake_model


def test_load_model_returns_singleton_on_second_call() -> None:
    from incognito.gliner import loader

    fake_model = MagicMock()
    with (
        patch.object(loader, "_model", None),
        patch("incognito.gliner.loader.GLiNER.from_pretrained", return_value=fake_model) as mock_fp,
    ):
        first = loader.load_model()
        second = loader.load_model()

    assert first is second
    mock_fp.assert_called_once()


def test_load_model_returns_cached_without_calling_from_pretrained() -> None:
    from incognito.gliner import loader

    cached = MagicMock()
    with (
        patch.object(loader, "_model", cached),
        patch("incognito.gliner.loader.GLiNER.from_pretrained") as mock_fp,
    ):
        result = loader.load_model()

    mock_fp.assert_not_called()
    assert result is cached


def test_load_model_raises_detection_error_on_os_error() -> None:
    from incognito.gliner import loader

    with (
        patch.object(loader, "_model", None),
        patch(
            "incognito.gliner.loader.GLiNER.from_pretrained",
            side_effect=OSError("model files not found"),
        ),
        pytest.raises(DetectionError),
    ):
        loader.load_model()


def test_load_model_preserves_original_exception_as_cause() -> None:
    from incognito.gliner import loader

    original = OSError("model files not found")
    with (
        patch.object(loader, "_model", None),
        patch(
            "incognito.gliner.loader.GLiNER.from_pretrained",
            side_effect=original,
        ),
        pytest.raises(DetectionError) as exc_info,
    ):
        loader.load_model()

    assert exc_info.value.__cause__ is original


def test_load_model_does_not_cache_on_failure() -> None:
    from incognito.gliner import loader

    with (
        patch.object(loader, "_model", None) as _model_attr,
        patch(
            "incognito.gliner.loader.GLiNER.from_pretrained",
            side_effect=OSError("offline"),
        ),
    ):
        with pytest.raises(DetectionError):
            loader.load_model()

        assert loader._model is None


def test_config_gliner_model_constant_exists() -> None:
    from incognito.core import config

    assert hasattr(config, "GLINER_MODEL")
    assert config.GLINER_MODEL == "urchade/gliner_multi-v2.1"


def test_config_gliner_labels_constant_exists() -> None:
    from incognito.core import config

    assert hasattr(config, "GLINER_LABELS")
    assert isinstance(config.GLINER_LABELS, list | tuple | frozenset)
    assert len(config.GLINER_LABELS) > 0


def test_config_gliner_threshold_person_is_correct() -> None:
    from incognito.core import config

    assert hasattr(config, "GLINER_THRESHOLD_PERSON")
    assert pytest.approx(0.5) == config.GLINER_THRESHOLD_PERSON


def test_config_gliner_threshold_address_is_correct() -> None:
    from incognito.core import config

    assert hasattr(config, "GLINER_THRESHOLD_ADDRESS")
    assert pytest.approx(0.3) == config.GLINER_THRESHOLD_ADDRESS
