class DomainException(Exception):
    """Base class for all domain exceptions."""
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class EntityNotFoundError(DomainException):
    def __init__(self, entity_name: str, identifier: str):
        super().__init__(f"{entity_name} not found with identifier {identifier}", code="NOT_FOUND")

class BusinessRuleViolationError(DomainException):
    def __init__(self, message: str):
        super().__init__(message, code="BUSINESS_RULE_VIOLATION")

class AuthenticationError(DomainException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code="UNAUTHORIZED")
