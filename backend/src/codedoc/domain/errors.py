class CodedocError(Exception):
    """Base for all domain errors."""


class CloneError(CodedocError):
    """Raised when a repository cannot be cloned (bad URL, timeout, size cap, git failure)."""


class RepositoryNotFoundError(CodedocError):
    """Raised when a repository id is not present in the store."""
