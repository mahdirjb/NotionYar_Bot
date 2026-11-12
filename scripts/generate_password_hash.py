import base64
import getpass
import hashlib
import secrets


def main() -> None:
    password = getpass.getpass("Web password: ")
    confirmation = getpass.getpass("Repeat password: ")
    if not password or password != confirmation:
        raise SystemExit("Passwords are empty or do not match.")

    iterations = 600_000
    salt = secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_text = base64.urlsafe_b64encode(digest).decode("ascii")
    print(f"WEB_LOGIN_PASSWORD_HASH=pbkdf2_sha256${iterations}${salt_text}${digest_text}")
    print(f"WEB_SESSION_SECRET={secrets.token_urlsafe(48)}")


if __name__ == "__main__":
    main()
