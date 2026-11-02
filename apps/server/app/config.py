from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["local", "staging", "production"] = "local"
    mongodb_uri: SecretStr | None = None
    mongodb_database: str = "baseball_mental"
    enable_kbo_probe: bool = False

    @model_validator(mode="after")
    def validate_deployed_storage(self):
        if self.app_env == "local":
            return self
        if self.enable_kbo_probe:
            raise ValueError("Historical probe must remain disabled outside local verification")
        if self.mongodb_uri is None:
            raise ValueError("Deployed environments require MONGODB_URI")
        try:
            uri = urlsplit(self.mongodb_uri.get_secret_value())
            options = {key.lower(): values[-1].lower() for key, values in parse_qs(uri.query).items()}
            authenticated = bool(uri.username and uri.password)
            valid_scheme = uri.scheme in {"mongodb", "mongodb+srv"}
        except ValueError:
            raise ValueError("Invalid MongoDB connection configuration") from None
        if not valid_scheme or not authenticated:
            raise ValueError("Deployed MongoDB requires an authenticated MongoDB URI")
        tls = uri.scheme == "mongodb+srv" or options.get("tls", options.get("ssl")) == "true"
        insecure = any(options.get(key) == "true" for key in (
            "tlsinsecure", "tlsallowinvalidcertificates", "tlsallowinvalidhostnames"
        ))
        if not tls or insecure or options.get("tls") == "false" or options.get("ssl") == "false":
            raise ValueError("Deployed MongoDB requires TLS with certificate verification")
        if not self.mongodb_database.strip():
            raise ValueError("MONGODB_DATABASE must not be empty")
        return self
