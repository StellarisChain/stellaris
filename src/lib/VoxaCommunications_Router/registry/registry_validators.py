import re

# https://github.com/Voxa-Communications/VoxaCommunications-Registry/src/util/
def validate_email(email):
    """
    Validates an email address using a regex pattern.
    
    :param email: The email address to validate.
    :return: True if the email is valid, False otherwise.
    """
    # Use a more comprehensive email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password_strength(password):
    """
    Validates password strength using multiple criteria.
    
    :param password: The password to validate.
    :return: (bool, str) A tuple containing whether the password is valid and an error message if not.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    
    # Check for at least one lowercase letter, one uppercase letter, one digit, and one special character
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character."
    
    return True, ""