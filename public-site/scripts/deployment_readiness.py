from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "deploy" / "lightsail" / "staging-config.env"


PLACEHOLDER_MARKERS = (
    "YOUR-ORG",
    "YOUR-REPO",
    "example.com",
    "ops@example.com",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def has_real_value(value: str | None) -> bool:
    if value is None:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    return not any(marker in stripped for marker in PLACEHOLDER_MARKERS)


def print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether Lightsail staging deployment inputs are ready."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to the staging config env file.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    values = parse_env_file(config_path)

    required = {
        "REPO_URL": "Git repository URL for the server to clone",
        "DOMAIN": "Staging domain pointed at the server",
    }
    https_required = {
        "CERTBOT_EMAIL": "Email used for Let's Encrypt certificate issuance",
    }
    recommended = {
        "REPO_REF": "Branch or tag to deploy",
        "APP_DIR": "Server install directory",
        "APP_USER": "Linux service account",
        "APP_GROUP": "Linux service group",
        "ENV_FILE": "Server env file path",
        "LIGHTSAIL_INSTANCE_NAME": "Lightsail instance name for rollout tracking",
        "LIGHTSAIL_STATIC_IP_NAME": "Static IP name for rollout tracking",
        "SSH_HOST": "SSH hostname or IP for the server",
        "SSH_USER": "SSH login user",
    }

    missing_required = [key for key in required if not has_real_value(values.get(key))]
    missing_https = [key for key in https_required if not has_real_value(values.get(key))]
    missing_recommended = [
        key for key in recommended if not has_real_value(values.get(key))
    ]

    print(f"config_path={config_path}")
    print(f"config_exists={config_path.exists()}")

    print_section("Required for bootstrap")
    for key, description in required.items():
        status = "OK" if has_real_value(values.get(key)) else "MISSING"
        print(f"{status:8} {key}: {description}")

    print_section("Required for HTTPS")
    for key, description in https_required.items():
        status = "OK" if has_real_value(values.get(key)) else "MISSING"
        print(f"{status:8} {key}: {description}")

    print_section("Recommended values")
    for key, description in recommended.items():
        status = "OK" if has_real_value(values.get(key)) else "MISSING"
        print(f"{status:8} {key}: {description}")

    bootstrap_ready = not missing_required
    https_ready = bootstrap_ready and not missing_https

    print_section("Summary")
    print(f"bootstrap_ready={bootstrap_ready}")
    print(f"https_ready={https_ready}")
    print(f"missing_required={missing_required}")
    print(f"missing_https={missing_https}")
    print(f"missing_recommended={missing_recommended}")

    print_section("Next steps")
    if not config_path.exists():
        print(
            "1. Copy public-site/deploy/lightsail/staging-config.env.example "
            "to public-site/deploy/lightsail/staging-config.env"
        )
    if missing_required:
        print("2. Fill in the required bootstrap values.")
    else:
        print("2. Bootstrap inputs are ready.")
        print("3. On the server, run: bash public-site/deploy/lightsail/run-staging-setup.sh")
    if not missing_https:
        print("4. HTTPS inputs are ready once DNS is pointing at the server.")
    else:
        print("4. Fill in CERTBOT_EMAIL before running the HTTPS step.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
