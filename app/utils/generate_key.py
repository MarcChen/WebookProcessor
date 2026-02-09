import secrets
import string

def generate_secure_key(length=32):
    """Generate a secure random key suitable for API tokens."""
    alphabet = string.ascii_letters + string.digits
    key = ''.join(secrets.choice(alphabet) for _ in range(length))
    return key

if __name__ == "__main__":
    print(f"Generated Key: {generate_secure_key()}")
