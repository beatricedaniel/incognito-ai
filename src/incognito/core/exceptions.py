from __future__ import annotations


class IncognitoError(Exception):
    pass


class PdfError(IncognitoError):
    pass


class DetectionError(IncognitoError):
    pass


class RedactionError(IncognitoError):
    pass


class OllamaError(IncognitoError):
    pass


class SessionError(IncognitoError):
    pass


class KeyfileError(IncognitoError):
    pass


class RecoveryError(IncognitoError):
    pass
