"""Custom exceptions for the LAS Update Installer."""


class DiscoveryException(RuntimeError):
    """Base exception for discovery-related errors."""
    pass


class InstanceInfoExistsException(DiscoveryException):
    """Raised when an instance info already exists in the registry."""
    pass


class InstanceInfoNotFoundException(DiscoveryException):
    """Raised when an instance info is not found in the registry."""
    pass


class InstallException(RuntimeError):
    """Raised when an installation operation fails."""
    pass


class ModuleException(RuntimeError):
    """Base exception for module-related errors."""
    pass


class ModuleExistsException(ModuleException):
    """Raised when a module already exists."""
    pass


class ModuleIllegalStateException(ModuleException):
    """Raised when a module is in an illegal state for the requested operation."""
    pass


class ModuleNotFoundException(ModuleException):
    """Raised when a module is not found."""
    pass
