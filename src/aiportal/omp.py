"""omp's custom providers, which it only reads from its models.yml.

Unlike opencode, omp can't be given a separate config file, so the launchers add or
update their own providers in models.yml and leave everything else in it as is.
Secrets stay out of the file: a provider's apiKey names an environment variable,
which omp reads.
"""
import json
import os


def models_path():
    agent_dir = os.environ.get("PI_CODING_AGENT_DIR") or os.path.join(
        os.environ.get("PI_CONFIG_DIR") or os.path.expanduser("~/.omp"), "agent")
    for name in ("models.yml", "models.yaml"):
        if os.path.exists(os.path.join(agent_dir, name)):
            return os.path.join(agent_dir, name)
    return os.path.join(agent_dir, "models.yml")


def update_providers(wanted):
    """Add or update the given providers in models.yml; returns its path."""
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    path = models_path()
    config = {}
    if os.path.exists(path):
        with open(path) as f:
            config = yaml.load(f) or {}
    providers = config.setdefault("providers", {})
    if all(json.dumps(providers.get(k), sort_keys=True) == json.dumps(v, sort_keys=True) for k, v in wanted.items()):
        return path
    providers.update(wanted)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        yaml.dump(config, f)
    print(f"Updated the {', '.join(wanted)} provider(s) in {path}")
    return path
