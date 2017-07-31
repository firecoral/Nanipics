# $Header: //depot/cs/db/Exceptions.py#8 $

class SupportSessionExpired(Exception):
    """Support session failed - where there is no cookie, key, or the
       session_key has expired"""
    def __str__(self):
        return ("Support Session Expired.  Please log in.")

class EcomSessionExpired(Exception):
    """Ecom session failed - where there is no cookie, key, or the
       session_key has expired"""
    def __str__(self):
        return ("Ecom Session Expired")

class DbError(Exception):
    """Provide an exception for database error reporting.
       A tuple should be passed in, including a logable
       error message as the first string and an appropriately
       sanitized message as the second string. Either string
       can be None."""
    pass

class DbKeyInvalid(DbError):
    """Provide an exception for calls to instantiate database
       objects (like a cart), with an invalid key."""
    pass

class CartInvalid(Exception):
    """Thrown when a cart can't progress due to some invalid condition."""
    pass

class CartIncomplete(Exception):
    """Thrown when a cart can't progress due to some missing information 
       from the consumer."""
    pass

class JobInvalid(Exception):
    """Thrown when a job can't progress due to some invalid condition."""
    pass

class AddressInvalid(CartInvalid):
    """Thrown when an address is missing required fields."""
    pass

class AuthError(Exception):
    """Thrown when we fail to authorize a credit card"""
    pass

class ZipImportError(Exception):
    """Thrown when we fail to import a ZIP file."""
    pass

class PromotionInvalid(Exception):
    """Thrown when the promotion code is invalid."""
    pass

