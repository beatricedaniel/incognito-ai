from __future__ import annotations


class IncognitoError(Exception):
    status_code: int = 500
    error: str = "Internal error"

    def __init__(self: IncognitoError, detail: str = "", *, error: str | None = None) -> None:
        self.detail = detail
        if error is not None:
            self.error = error
        super().__init__(detail)


class PdfError(IncognitoError):
    status_code: int = 400
    error: str = "Invalid file type"


class DetectionError(IncognitoError):
    pass


class DetectionNotFoundError(IncognitoError):
    status_code: int = 404
    error: str = "Detection not found"


class RedactionError(IncognitoError):
    pass


class PassphraseError(IncognitoError):
    status_code: int = 400
    error: str = "Invalid passphrase"


class OllamaError(IncognitoError):
    pass


class SessionError(IncognitoError):
    status_code: int = 404
    error: str = "Session not found"


class KeyfileError(IncognitoError):
    pass


class RecoveryError(IncognitoError):
    status_code: int = 422
    error: str = "Recovery failed"
